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
            # /order returns priceImpact (percentage points); the older
            # priceImpactPct is deprecated and fmt_quote ignores it.
            "priceImpact": o.get("priceImpact"),
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
