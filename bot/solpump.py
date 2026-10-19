"""solpump.io (trade.solpump.io) REST + WebSocket data service.

Read-only, best-effort integration for the realtime trader and the
offline forensics tool.  Nothing here signs or executes anything: the
shadow/live loops decide what to do with the data, and fills still only
ever come from the venue quotes.

Surface probed live 2026-10-18/19 (see README_PRODUCT.md "solpump.io"):

REST  /api/v2/...                       what it gives
  token/{q}/{m}                         token header
  token/{q}/{m}/pairs                   every venue pair (isBestPair)
  token/{q}/{m}/safety                  audit + holder concentration
  token/{q}/{m}/candles                 OHLC (1s/1m, price|marketCap)
  token/{q}/{m}/swaps                   trade tape, cursor paging
  token/{q}/{m}/chart-markers           MIGRATION/THESIS/DEV markers
  token/{q}/{m}/dev-tokens              dev deployment history
  token/{q}/{m}/holders                 holder list (cursor)
  token/{q}/{m}/calls                   calls on the token (cursor)
  token/{q}/{m}/top-traders             ranked traders with PnL
  trade/{chain}/fee-estimate            priority fee by tier (AUTO/LOW/MEDIUM/HIGH)
  watchlist/ranking/all                 caller/KOL leaderboard
  scanner/tokens/search                 pair/token lookup
  scanner/tokens/trending/{tf}          trending list (POST)
  scanner/trenches/{new,graduating,graduated}   trenches feeds (POST)

WS  wss://trade.solpump.io/v2/ws
  {"type":"ping"} -> pong (+serverTimestampMs)
  subscribe topic=token:{q}:{m}:{price|stats|safety|holders|swaps|migration|
          top_traders|dev_tokens|chart_markers|candle:<tf>:<mode>}
  subscribe topic=fee-estimate:{chain}
  subscribe topic=scanner:lookup params={"lookup":[{chain,tokenOrPairAddress}]}
  subscribed acks carry subId; events: TOKEN_PRICE, TOKEN_SWAPS, TOKEN_STATS,
  TOKEN_SAFETY, TOKEN_DEV_TOKENS, SCANNER_TOKENS, SCANNER_UPDATE,
  FEE_ESTIMATE, ...
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import time
from collections import deque

import requests

log = logging.getLogger("solpump")

BASE = "https://trade.solpump.io/api/v2"
WS_URL = "wss://trade.solpump.io/v2/ws"
UA = "Mozilla/5.0"
QUOTE = "SOL"
TIMEOUT = float(os.environ.get("SOLPUMP_HTTP_TIMEOUT", "8"))
_HEADERS = {"User-Agent": UA}


def enabled() -> bool:
    """Master switch; the trading loop degrades to v3 when off."""
    return os.environ.get("SOLPUMP_ENABLED", "1") != "0"


# --------------------------------------------------------------------- REST

def _req(method: str, path: str, params: dict | None = None,
         body: dict | None = None) -> dict | None:
    """One best-effort JSON call. Returns None on any failure."""
    url = f"{BASE}{path}"
    try:
        if method == "POST":
            r = requests.post(url, json=body if body is not None else {},
                              params=params or {}, headers=_HEADERS,
                              timeout=TIMEOUT)
        else:
            r = requests.get(url, params=params or {}, headers=_HEADERS,
                             timeout=TIMEOUT)
        if r.status_code != 200:
            log.debug("solpump %s %s -> HTTP %s", method, path, r.status_code)
            return None
        return r.json()
    except Exception as exc:
        log.debug("solpump %s %s failed: %s", method, path, str(exc)[:140])
        return None


def token_info(mint: str, quote: str = QUOTE) -> dict | None:
    return _req("GET", f"/token/{quote}/{mint}")


def pairs(mint: str, quote: str = QUOTE) -> dict | None:
    return _req("GET", f"/token/{quote}/{mint}/pairs")


def safety(mint: str, quote: str = QUOTE) -> dict | None:
    return _req("GET", f"/token/{quote}/{mint}/safety")


def candles(mint: str, timeframe: str = "1s", mode: str = "marketCap",
            count: int = 300, quote: str = QUOTE) -> dict | None:
    return _req("GET", f"/token/{quote}/{mint}/candles",
                {"timeframe": timeframe, "mode": mode, "count": count})


def swaps(mint: str, quote: str = QUOTE, limit: int = 100,
          cursor: str | None = None, side: str | None = None,
          min_usd: float | None = None, max_usd: float | None = None,
          wallet: str | None = None, include_outlier: bool | None = None,
          frm: int | None = None) -> dict | None:
    p: dict = {"limit": min(max(int(limit), 1), 100)}
    if cursor:
        p["cursor"] = cursor
    if side:
        p["side"] = side
    if min_usd is not None:
        p["minUsd"] = min_usd
    if max_usd is not None:
        p["maxUsd"] = max_usd
    if wallet:
        p["walletAddress"] = wallet
    if include_outlier is not None:
        p["includeOutlier"] = "true" if include_outlier else "false"
    if frm is not None:
        p["from"] = int(frm)
    return _req("GET", f"/token/{quote}/{mint}/swaps", p)


def swaps_since(mint: str, floor_s: float, max_pages: int = 6,
                quote: str = QUOTE, **kw) -> list[dict]:
    """Tape walk from the newest swap back to `floor_s` (epoch seconds).

    The endpoint has no upper time bound: pages start at the newest swap
    and move backwards via nextCursor. Stops when a page reaches
    <= floor_s, the cursor repeats, a page is empty, or max_pages.
    Returns whatever it collected (newest-first pages concatenated).
    """
    out: list[dict] = []
    cursor = None
    for _ in range(max(1, max_pages)):
        d = swaps(mint, quote=quote, cursor=cursor, frm=int(floor_s), **kw)
        if not d:
            break
        sw = d.get("swaps") or []
        if not sw:
            break
        out.extend(sw)
        oldest = (sw[-1].get("timestamp") or 0) / 1000.0
        if oldest <= floor_s:
            break
        nc = d.get("nextCursor")
        if not nc or nc == cursor:
            break
        cursor = nc
    return out


def chart_markers(mint: str, frm: int, to: int, min_usd: float = 10.0,
                  curated: bool = False, quote: str = QUOTE) -> dict | None:
    return _req("GET", f"/token/{quote}/{mint}/chart-markers",
                {"from": int(frm), "to": int(to), "minUsd": min_usd,
                 "curated": "true" if curated else "false"})


def dev_tokens(mint: str, quote: str = QUOTE) -> dict | None:
    return _req("GET", f"/token/{quote}/{mint}/dev-tokens")


def holders(mint: str, cursor: str | None = None,
            quote: str = QUOTE) -> dict | None:
    p = {"cursor": cursor} if cursor else None
    return _req("GET", f"/token/{quote}/{mint}/holders", p)


def calls(mint: str, cursor: str | None = None,
          quote: str = QUOTE) -> dict | None:
    p = {"cursor": cursor} if cursor else None
    return _req("GET", f"/token/{quote}/{mint}/calls", p)


def top_traders(mint: str, quote: str = QUOTE) -> dict | None:
    return _req("GET", f"/token/{quote}/{mint}/top-traders")


def fee_estimate(chain: str = "SOL", tier: str = "MEDIUM") -> dict | None:
    return _req("GET", f"/trade/{chain}/fee-estimate", {"type": tier})


def watchlist_ranking(timeframe: str = "30d", rank_by: str = "performanceScore",
                      order_by: str = "desc") -> dict | None:
    return _req("GET", "/watchlist/ranking/all",
                {"timeframe": timeframe, "rankBy": rank_by,
                 "orderBy": order_by})


def scanner_search(lookup: str) -> dict | None:
    """lookup is 'CHAIN:address' (token or pair address)."""
    return _req("GET", "/scanner/tokens/search", {"lookup": lookup})


def scanner_trending(timeframe: str = "5M") -> dict | None:
    return _req("POST", f"/scanner/tokens/trending/{timeframe}")


def scanner_trenches(kind: str = "new") -> dict | None:
    """kind: new | graduating | graduated."""
    return _req("POST", f"/scanner/trenches/{kind}")


# ------------------------------------------------------------------ parsing

def swaps_from_event(data) -> list[dict]:
    """Extract a swaps list from a WS TOKEN_SWAPS data payload.

    Tolerates dict-with-list, bare list, or a single swap object — the
    exact envelope is versioned by the vendor, so parse defensively.
    """
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for k in ("swaps", "items", "trades", "data"):
            v = data.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        if "side" in data:
            return [data]
    return []


def price_from_event(data) -> float | None:
    """Best-effort native price from a TOKEN_PRICE payload."""
    if not isinstance(data, dict):
        return None
    for k in ("priceNative", "price", "priceNativeStr"):
        v = data.get(k)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
    q = data.get("quote")
    if isinstance(q, dict):
        for k in ("priceNative", "priceNativeStr"):
            if q.get(k) is not None:
                try:
                    return float(q[k])
                except Exception:
                    pass
    return None


def swap_sol(v: dict) -> float:
    try:
        return float(v.get("amountNative") or 0.0)
    except Exception:
        return 0.0


def swap_ts(v: dict, now: float) -> float:
    """Swap timestamp in epoch seconds (falls back to now - ageSeconds)."""
    t = v.get("timestamp")
    if t:
        try:
            t = float(t)
            return t / 1000.0 if t > 1e11 else t
        except Exception:
            pass
    age = v.get("ageSeconds")
    if age is not None:
        try:
            return now - float(age)
        except Exception:
            pass
    return now


# ----------------------------------------------------------------- websocket

class Feed:
    """One persistent WS connection with topic set, keepalive, dispatch.

    `on_event(topic, event, data, meta)` runs in the event loop. The feed
    reconnects with capped backoff and resubscribes the wanted topics.
    """

    PING_S = 20.0

    def __init__(self, on_event):
        self._on_event = on_event
        self._want: dict[str, dict | None] = {}
        self._subids: dict[str, str] = {}
        self._outbox: deque[dict] = deque()
        self._task: asyncio.Task | None = None
        self._stop = False
        self._req = 0
        self.last_msg = 0.0
        self.connected = False
        self.reconnects = 0
        self.topics_seen = 0

    # ---- public API (called from the event loop)

    def start(self) -> None:
        if self._task is None:
            self._stop = False
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
            self._task = None

    def subscribe(self, topic: str, params: dict | None = None) -> None:
        if topic in self._want:
            return
        self._want[topic] = params
        self._outbox.append({"type": "subscribe", "topic": topic,
                             **({"params": params} if params else {})})

    def unsubscribe(self, topic: str) -> None:
        if topic not in self._want:
            return
        self._want.pop(topic, None)
        sub = self._subids.pop(topic, None)
        if sub:
            self._outbox.append({"type": "unsubscribe", "subId": sub})

    def status(self) -> dict:
        return {"connected": self.connected, "topics": len(self._want),
                "reconnects": self.reconnects,
                "msg_age_s": round(time.time() - self.last_msg, 1)
                if self.last_msg else None}

    # ---- internals

    async def _send(self, ws, msg: dict) -> None:
        self._req += 1
        msg["requestId"] = f"b_{self._req}"
        await ws.send(json.dumps(msg))

    async def _run(self) -> None:
        import websockets
        backoff = 1.0
        while not self._stop:
            try:
                async with websockets.connect(
                        WS_URL, max_size=50_000_000, ping_interval=None,
                        additional_headers={"User-Agent": UA}) as ws:
                    self.connected = True
                    self.reconnects += 0  # first connect is not a reconnect
                    backoff = 1.0
                    self.last_msg = time.time()
                    last_ping = 0.0
                    for t, prm in list(self._want.items()):
                        m = {"type": "subscribe", "topic": t}
                        if prm:
                            m["params"] = prm
                        await self._send(ws, m)
                    while not self._stop:
                        now = time.time()
                        if now - last_ping > self.PING_S:
                            last_ping = now
                            await self._send(ws, {"type": "ping"})
                        while self._outbox:
                            await self._send(ws, self._outbox.popleft())
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue
                        self.last_msg = time.time()
                        self._dispatch(raw)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.connected = False
                self.reconnects += 1
                log.debug("solpump ws down (%s); retry in %.0fs",
                          str(exc)[:120], backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)
            finally:
                self.connected = False
                self._subids.clear()  # subIds are per-connection

    def _dispatch(self, raw) -> None:
        try:
            j = json.loads(raw if isinstance(raw, str)
                           else raw.decode("utf-8", "replace"))
        except Exception:
            return
        if not isinstance(j, dict):
            return
        t = j.get("type")
        if t in ("pong", "subscribed", "unsubscribed", "error", "auth"):
            if t == "subscribed" and j.get("topic"):
                self._subids[j["topic"]] = j.get("subId") or ""
            elif t == "error":
                log.debug("solpump ws error: %s", str(j)[:180])
            return
        topic = j.get("topic") or ""
        if not topic:
            return
        self.topics_seen += 1
        try:
            self._on_event(topic, str(j.get("event") or j.get("type") or ""),
                           j.get("data") or {}, j.get("meta") or {})
        except Exception as exc:
            log.debug("solpump on_event failed: %s", str(exc)[:140])
