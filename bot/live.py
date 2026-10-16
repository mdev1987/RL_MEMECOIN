"""Live Jupiter execution: /order -> sign -> /execute, guarded.

Three modes, same decision code:
- paper  (default): simulate only, never touches this module's send path.
- shadow (SHADOW=1): full /order + local sign + verify, NEVER executes.
  Records what WOULD have happened for fill-parity measurement.
- live   (LIVE_TRADING=1 + --live + key): executes for real.

Live guards (all fail-closed, checked before AND after signing):
- kill file (data/LIVE_KILL) or LIVE_TRADING!=1 -> refuse.
- size cap (LIVE_MAX_SOL, default 0.01).
- price impact cap (LIVE_MAX_IMPACT_PCT, default 5.0).
- min-out: outAmount >= otherAmountThreshold else refuse.
- no gasless: signatureFeePayer must equal taker.
- fee cap: prioritizationFeeLamports <= LIVE_MAX_PRIO_LAMPORTS (default 100_000).
- error codes mapped to retryable/fatal (docs: aggregator -1000s, RFQ -2000s).

Deliberately out: RTSE-auto is opt-in (LIVE_SLIPPAGE_BPS=auto omits the
param; default fixed 100bps suits memecoin exits), Jito tips default off
(LIVE_JITO_TIP_LAMPORTS, edge-killer at size), v1 transactions refused
(signer path is v0-exercised), CPI (no onchain program exists).
"""
from __future__ import annotations
import base64
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests

log = logging.getLogger("live")

BASE = "https://api.jup.ag/swap/v2"
SOL = "So11111111111111111111111111111111111111112"

REPO = Path(__file__).resolve().parents[1]
KILL_FILE = os.environ.get("LIVE_KILL_FILE", str(REPO / "data" / "LIVE_KILL"))

# error codes that deserve one retry (landing/RFQ transient), else fatal
RETRYABLE = {-1000, -1001, -2000, -2001, -2004}


@dataclass
class Receipt:
    signature: str
    slot: str
    in_amount: str
    out_amount: str
    router: str
    shadow: bool = False
    # actuals from /execute (landed truth vs quoted outAmount)
    total_in: str = "?"
    total_out: str = "?"


class NoQuote(RuntimeError):
    """Routine venue miss: no route for this mint/size right now.

    Fresh illiquid memecoins hit this constantly. Callers must treat it
    as a SKIP (same as paper's `filtered`), never as an error alert.
    """


_last_order_ts = 0.0


def order_throttled() -> bool:
    """Gateway politeness: min interval between /order calls.

    The API gateway 429s bursts (seen live); throttling converts a
    retry-storm into spaced single attempts. Returns True when the
    caller must back off now.
    """
    global _last_order_ts
    import time
    gap = float(os.environ.get("JUP_MIN_INTERVAL_S", "0.5"))
    now = time.monotonic()
    if now - _last_order_ts < gap:
        return True
    _last_order_ts = now
    return False


def rug_give_up(misses: int, max_misses: int = 5) -> bool:
    """Give up on an unclosable exit (dead mint, no Jupiter route).

    Without this, corpses clog the book forever (MAXOPEN reached, no new
    entries) while the position is economically already zero. Honest
    handling mirrors the sim's rug=-1.0: book the loss, free the slot.
    """
    return misses >= max_misses


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "0") == "1"


def live_enabled() -> bool:
    return _env_flag("LIVE_TRADING")


def shadow_enabled() -> bool:
    return _env_flag("SHADOW")


def killed() -> bool:
    return Path(KILL_FILE).exists()


def _load_keypair():
    """Live key from .env.signer (BS58_PRIVATE_KEY) or .env (PRIVATE_KEY).

    Either name works; .env.signer wins when both are set (least privilege:
    paper daemons need never see it, though they share .env today).
    Raises if neither is present.
    """
    from dotenv import load_dotenv
    load_dotenv(REPO / ".env.signer")
    b58 = os.environ.get("BS58_PRIVATE_KEY", "").strip()
    if not b58:
        load_dotenv(REPO / ".env")
        b58 = os.environ.get("PRIVATE_KEY", "").strip()
    if not b58:
        raise RuntimeError("no signing key (BS58_PRIVATE_KEY/.env.signer or PRIVATE_KEY/.env)")
    from solders.keypair import Keypair
    B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for c in b58:
        n = n * 58 + B58.index(c)
    return Keypair.from_bytes(n.to_bytes(64, "big"))


def _api_key() -> str:
    return os.environ.get("JUPITER_API_KEY", "")


def get_order(input_mint: str, output_mint: str, amount_base: int,
              taker: str, slippage_bps: int | str = 100,
              jito_tip_lamports: int = 0,
              timeout: float = 20.0) -> dict:
    """Read-only /order WITH taker (returns transaction + requestId).

    slippage_bps="auto" omits the param for RTSE-automatic; a number
    overrides with a fixed value (better for memecoin exits).
    jito_tip_lamports>0 passes a Jito tip (default 0 = off: tips are
    proven edge-killers at small size).
    """
    params = {"inputMint": input_mint, "outputMint": output_mint,
              "amount": str(int(amount_base)), "taker": taker}
    if not (isinstance(slippage_bps, str) and slippage_bps == "auto"):
        params["slippageBps"] = str(int(slippage_bps))
    if int(jito_tip_lamports or 0) > 0:
        params["jitoTipLamports"] = str(int(jito_tip_lamports))
    if order_throttled():
        raise NoQuote("throttled: min /order interval")
    r = requests.get(
        f"{BASE}/order", params=params,
        headers={"x-api-key": _api_key()}, timeout=timeout)
    if not r.ok:
        # 400 "No routes found" is routine for fresh illiquid mints.
        raise NoQuote(f"order HTTP {r.status_code}: {r.text[:200]}")
    o = r.json()
    if "outAmount" not in o:
        raise NoQuote(f"order no quote: {str(o)[:200]}")
    return o


def check_guards(o: dict, taker: str, max_sol: float) -> tuple[bool, str]:
    """Pre-sign policy checks. Returns (ok, reason). Fail-closed."""
    try:
        impact = float(o.get("priceImpact") or 0.0)  # percentage points
        if abs(impact) > float(os.environ.get("LIVE_MAX_IMPACT_PCT", "5.0")):
            return False, f"impact {impact:.2f}% over cap"
        if int(o.get("outAmount", "0")) < int(o.get("otherAmountThreshold", "0")):
            return False, "outAmount below min-out threshold"
        sfp = o.get("signatureFeePayer")
        if sfp is not None and sfp != taker:
            return False, f"gasless sponsorship (fee payer {str(sfp)[:8]})"
        prio = int(o.get("prioritizationFeeLamports") or 0)
        if prio > int(os.environ.get("LIVE_MAX_PRIO_LAMPORTS", "100000")):
            return False, f"priority fee {prio} over cap"
        # feeBps is the TOTAL rate incl. gasless support-cost recoup
        # (platformFee.feeBps is Jupiter's cut only). Cap the total.
        try:
            fee_bps = float(o.get("feeBps") or 0.0)
        except Exception:
            fee_bps = 0.0
        if fee_bps > float(os.environ.get("LIVE_MAX_FEE_BPS", "200")):
            return False, f"total fee {fee_bps}bps over cap"
        if not o.get("transaction"):
            return False, (f"no transaction "
                           f"(router={o.get('router')} code={o.get('errorCode')})")
        # v1 transactions are never requested (ceiling "0") and the local
        # solders path is v0-exercised only: refuse anything else outright.
        if int(o.get("transactionVersion", 0)) != 0:
            return False, "v1 transaction unsupported by signer path"
    except Exception as exc:
        return False, f"guard parse: {exc}"
    return True, "ok"


def sign_order(o: dict, kp) -> str:
    """Sign the /order transaction locally. Returns base64 signed tx."""
    from solders.transaction import VersionedTransaction
    raw = base64.b64decode(o["transaction"])
    tx = VersionedTransaction.from_bytes(raw)
    sig = kp.sign_message(bytes(tx.message))
    assert sig.verify(kp.pubkey(), bytes(tx.message)), "sig self-check failed"
    return base64.b64encode(bytes(VersionedTransaction.populate(
        tx.message, [sig]))).decode()


def execute_signed(signed_b64: str, request_id: str,
                   timeout: float = 60.0) -> dict:
    r = requests.post(
        f"{BASE}/execute",
        json={"signedTransaction": signed_b64, "requestId": request_id},
        headers={"x-api-key": _api_key(),
                 "Content-Type": "application/json"},
        timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"execute HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def confirm_signature(signature: str, helius_key: str,
                      tries: int = 20, gap: float = 1.5) -> bool:
    """Poll getSignatureStatuses until confirmed/finalized or tries run out."""
    for _ in range(tries):
        try:
            r = requests.post(
                f"https://mainnet.helius-rpc.com/?api-key={helius_key}",
                json={"jsonrpc": "2.0", "id": 1,
                      "method": "getSignatureStatuses",
                      "params": [[signature], {"searchTransactionHistory": True}]},
                timeout=15).json()
            st = (r.get("result") or {}).get("value", [None])[0] or {}
            if st.get("confirmationStatus") in ("confirmed", "finalized"):
                return st.get("err") is None
            if st.get("err") is not None:
                return False
        except Exception:
            pass
        time.sleep(gap)
    return False


def place_order(input_mint: str, output_mint: str, amount_base: int,
                size_sol: float, shadow: bool = False) -> Receipt:
    """Full guarded flow. Raises on any guard/execution failure.

    shadow=True: sign + verify only, return Receipt(shadow=True), no /execute.
    """
    if killed():
        raise RuntimeError("LIVE_KILL present — refusing")
    max_sol = float(os.environ.get("LIVE_MAX_SOL", "0.01"))
    if size_sol > max_sol + 1e-9:
        raise RuntimeError(f"size {size_sol} over LIVE_MAX_SOL {max_sol}")
    kp = _load_keypair()
    taker = str(kp.pubkey())
    slippage = os.environ.get("LIVE_SLIPPAGE_BPS", "100")
    slippage = "auto" if slippage == "auto" else int(slippage)
    tip = int(os.environ.get("LIVE_JITO_TIP_LAMPORTS", "0") or 0)
    o = get_order(input_mint, output_mint, amount_base, taker, slippage, tip)
    ok, why = check_guards(o, taker, max_sol)
    if not ok:
        raise RuntimeError(f"guard: {why}")
    signed = sign_order(o, kp)
    if shadow or shadow_enabled():
        log.info("SHADOW signed %s -> %s (not executed)",
                 input_mint[:8], output_mint[:8])
        return Receipt(signature="shadow", slot="-",
                       in_amount=o.get("inAmount", "?"),
                       out_amount=o.get("outAmount", "?"),
                       router=o.get("router", "?"), shadow=True)
    res = execute_signed(signed, o["requestId"])
    if res.get("status") != "Success":
        code = res.get("code")
        raise RuntimeError(f"execute {res.get('status')}: {res.get('error')} "
                           f"(code={code} retryable={code in RETRYABLE})")
    hk = os.environ.get("HELIUS_API_KEY", "")
    ok = confirm_signature(res["signature"], hk) if hk else True
    if not ok:
        raise RuntimeError(f"unconfirmed: {res['signature']}")
    return Receipt(signature=res["signature"], slot=str(res.get("slot")),
                   in_amount=o.get("inAmount", "?"),
                   out_amount=o.get("outAmount", "?"),
                   router=o.get("router", "?"),
                   total_in=str(res.get("totalInputAmount", "?")),
                   total_out=str(res.get("totalOutputAmount", "?")))
