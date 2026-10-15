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


def order_quote(input_mint: str, output_mint: str, amount_base: int,
                timeout: float = 10.0) -> dict | None:
    """GET /swap/v2/order (read-only). Returns quote dict or None."""
    api_key = os.environ.get("JUPITER_API_KEY", "")
    if not api_key or amount_base <= 0:
        return None
    try:
        o = requests.get(
            f"{BASE}/order",
            params={"inputMint": input_mint, "outputMint": output_mint,
                    "amount": str(int(amount_base)), "slippageBps": "50"},
            headers={"x-api-key": api_key}, timeout=timeout)
        if not o.ok:
            log.debug("jup order HTTP %s: %s", o.status_code, o.text[:120])
            return None
        o = o.json()
        if "outAmount" not in o or "routePlan" not in o:
            return None
        return {
            "inAmount": o.get("inAmount"), "outAmount": o.get("outAmount"),
            "priceImpactPct": o.get("priceImpactPct"),
            "route": [(s.get("percent"),
                       (s.get("swapInfo") or {}).get("label"))
                      for s in o.get("routePlan", [])],
        }
    except Exception as exc:
        log.debug("jup quote miss: %s", str(exc)[:120])
        return None


def fmt_quote(q: dict | None, side: str) -> str | None:
    if not q:
        return None
    try:
        route = ",".join(f"{p}%{lbl}" for p, lbl in (q.get("route") or [])[:3])
        return (f"🔮 Jup {side} out `{q['outAmount']}` "
                f"(impact `{q.get('priceImpactPct', '?')}%` via {route or '?'})")
    except Exception:
        return None
