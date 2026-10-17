"""Read-only Jupiter order quotes for paper fills (fail-open, never signs).

Used by the paper loop to attach a live venue quote to Telegram
open/close cards: expected out-amount + price impact + route labels.
Any failure (timeout, no route, bad mint) returns None and the card
sends without the quote line. No /build, no signing, no broadcast.
"""
from __future__ import annotations
import logging
import os

import requests

log = logging.getLogger("jup")

BASE = "https://api.jup.ag/swap/v2"
SOL = "So11111111111111111111111111111111111111112"
LAMPORTS = 1_000_000_000

_decimals_cache: dict[str, int] = {SOL: 9}


def enabled() -> bool:
    return os.environ.get("JUP_QUOTE", "1") != "0"


def token_decimals(mint: str, helius_key: str, timeout: float = 8.0) -> int | None:
    """Decimals via Helius getTokenSupply (cached). None on any failure."""
    if mint in _decimals_cache:
        return _decimals_cache[mint]
    if not helius_key:
        return None
    try:
        r = requests.post(
            f"https://mainnet.helius-rpc.com/?api-key={helius_key}",
            json={"jsonrpc": "2.0", "id": 1, "method": "getTokenSupply",
                  "params": [mint]},
            timeout=timeout).json()
        d = int(r["result"]["value"]["decimals"])
        _decimals_cache[mint] = d
        return d
    except Exception as exc:
        log.debug("decimals miss %s: %s", (mint or "?")[:8], str(exc)[:100])
        return None


def _api_keys(replay: bool = False) -> list[str]:
    """Candidate keys in preference order. Replay workloads prefer
    JUPITER_API_KEY_REPLAY (rate-limit isolation); everything else the
    primary first. The other slot is a 401 fallback — a rotated primary
    must not stall live quoting (seen 2026-10-17)."""
    order = (("JUPITER_API_KEY_REPLAY", "JUPITER_API_KEY") if replay
             else ("JUPITER_API_KEY", "JUPITER_API_KEY_REPLAY"))
    out: list[str] = []
    for name in order:
        k = (os.environ.get(name) or "").strip()
        if k and k not in out:
            out.append(k)
    return out


def order_quote_ex(input_mint: str, output_mint: str, amount_base: int,
                   timeout: float = 10.0,
                   replay: bool = False) -> tuple[dict | None, str]:
    """GET /swap/v2/order (read-only). Returns (quote, failure reason).

    The reason lets callers classify misses honestly (venue has no route
    vs. our own auth/quota/network trouble) instead of treating any
    failure as "the mint is dead".
    """
    keys = _api_keys(replay)
    if not keys:
        return None, "no api key"
    if amount_base <= 0:
        return None, "bad amount"
    try:
        o = None
        for i, k in enumerate(keys):
            o = requests.get(
                f"{BASE}/order",
                params={"inputMint": input_mint, "outputMint": output_mint,
                        "amount": str(int(amount_base)), "slippageBps": "50"},
                headers={"x-api-key": k}, timeout=timeout)
            if getattr(o, "status_code", 200) == 401 and i + 1 < len(keys):
                log.warning("jup quote 401 on key %d — trying fallback key", i)
                continue
            break
        if not o.ok:
            log.debug("jup order HTTP %s: %s", o.status_code, o.text[:120])
            return None, f"order HTTP {o.status_code}: {o.text[:120]}"
        o = o.json()
        if "outAmount" not in o or "routePlan" not in o:
            return None, f"order no quote: {str(o)[:120]}"
        return {
            "inAmount": o.get("inAmount"), "outAmount": o.get("outAmount"),
            # /order returns priceImpact (percentage points); the older
            # priceImpactPct is deprecated and fmt_quote ignores it.
            "priceImpact": o.get("priceImpact"),
            "priceImpactPct": o.get("priceImpactPct"),
            "route": [(s.get("percent"),
                       (s.get("swapInfo") or {}).get("label"))
                      for s in o.get("routePlan", [])],
        }, ""
    except Exception as exc:
        log.debug("jup quote miss: %s", str(exc)[:120])
        return None, f"order error: {str(exc)[:120]}"


def order_quote(input_mint: str, output_mint: str, amount_base: int,
                timeout: float = 10.0, replay: bool = False) -> dict | None:
    """GET /swap/v2/order (read-only). Returns quote dict or None."""
    return order_quote_ex(input_mint, output_mint, amount_base,
                          timeout=timeout, replay=replay)[0]


def fmt_quote(q: dict | None, side: str) -> str | None:
    if not q:
        return None
    try:
        route = ",".join(f"{p}%{lbl}" for p, lbl in (q.get("route") or [])[:3])
        # priceImpact on /order is percentage POINTS (-0.1 = -0.1%);
        # priceImpactPct is deprecated and must not be used.
        return (f"🔮 Jup {side} out `{q['outAmount']}` "
                f"(impact `{q.get('priceImpact', '?')}%` via {route or '?'})")
    except Exception:
        return None


def price_diverges(tape_px: float, venue_px: float,
                   factor: float = 3.0) -> bool:
    """True when a tape price is implausibly far from the venue quote.

    Both are SOL-per-token. A mis-scaled tape (seen live: 337x split)
    would otherwise trigger entries on ghost data; non-positive values
    are always suspect. 3x is generous: real quote-vs-print drift on a
    fast move is well under 2x, and the observed ghost was 337x.
    """
    if tape_px <= 0 or venue_px <= 0:
        return True
    return tape_px > factor * venue_px or tape_px < venue_px / factor
