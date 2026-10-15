"""Live PumpAPI tick ingestor -> early-tape JSONL (VPS-lean paper research).

Connects to wss://stream.pumpapi.io, keeps per-mint early tapes
(first 600s: buys, unique buyers, prices, dips), emits one JSON line
per mint when its window closes, prunes idle mints every 60s.
Bounded run: --secs (default 300). Tiny disk: tapes only, no raw log.

Usage: /home/mdev/Programming/rl_trading/.venv/bin/python -m bot.live_ingest --secs 300 --out data/live_tapes.jsonl
"""
from __future__ import annotations
import argparse
import asyncio
import json
import time

URL = "wss://stream.pumpapi.io"
WINDOW_S = 600.0
PRUNE_S = 60.0
IDLE_S = 7200.0


def tape_features(t, keep_series=False):
    buys = t["buys"]
    px = [b[1] for b in buys]
    ret = px[-1] / px[0] - 1.0 if len(px) >= 2 and px[0] > 0 else 0.0
    dip = min((p / px[0] - 1.0) for p in px) if px else 0.0
    out = {"mint": t["mint"], "t0": t["t0"], "hour_utc": t["hour_utc"],
           "n_buys": len(buys), "n_buyers": len(t["buyers"]),
           "n_sells": t["sells"], "ret10m": round(ret, 6),
           "dip10m": round(dip, 6), "p0": px[0] if px else 0.0,
           "p1": px[-1] if px else 0.0}
    if keep_series:
        out["prices"] = px
        out["buyers_ratio"] = round(len(t["buyers"]) / max(len(buys), 1), 4)
    return out


def is_v2(t) -> bool:
    """Entry-gate pre-check on tape summaries (full guard runs on series)."""
    buys = t["buys"]
    if len(buys) < 2 or not buys[0][1]:
        return False
    ret = buys[-1][1] / buys[0][1] - 1.0
    dip = min(p / buys[0][1] - 1.0 for _, p in buys)
    return (ret >= 0.05 and len(t["buyers"]) / max(len(buys), 1) >= 0.60
            and dip >= -0.05)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=300.0)
    ap.add_argument("--out", default="data/live_tapes.jsonl")
    ap.add_argument("--series", action="store_true",
                    help="keep full buy-price series for v2-passing tapes "
                         "(paper-fill simulation needs single-bar data for "
                         "the bad-tick guard)")
    ap.add_argument("--window", type=float, default=WINDOW_S,
                    help="seconds of early tape per mint before emit")
    a = ap.parse_args()
    import websockets
    WIN = float(a.window)
    mints = {}
    n_raw = n_buy = n_sell = 0
    t_end = time.time() + a.secs
    last_prune = time.time()
    out = open(a.out, "a")
    try:
        async with websockets.connect(URL, max_size=50_000_000) as ws:
            print(f"live_ingest connected, capturing {a.secs:.0f}s", flush=True)
            while time.time() < t_end:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                except asyncio.TimeoutError:
                    continue
                try:
                    e = json.loads(raw)
                except Exception:
                    continue
                n_raw += 1
                act = e.get("action")
                m = e.get("mint")
                if act not in ("buy", "sell") or not m:
                    continue
                ts = int(e.get("timestamp") or int(time.time() * 1000))
                now = time.time()
                t = mints.get(m)
                if t is None:
                    t = mints[m] = {"mint": m, "t0": ts, "hour_utc": time.strftime(
                        "%H", time.gmtime(ts / 1000)), "buys": [], "buyers": [],
                        "sells": 0, "emitted": False}
                if (ts - t["t0"]) / 1000 > WIN:
                    if not t["emitted"]:
                        keep = bool(a.series) and is_v2(t)
                        out.write(json.dumps(tape_features(t, keep_series=keep)) + "\n")
                        t["emitted"] = True
                    continue
                if t["emitted"]:
                    continue
                if act == "buy":
                    px = e.get("price")
                    if px:
                        t["buys"].append([ts, float(px)])
                        n_buy += 1
                    s = e.get("txSigner")
                    if s and s not in t["buyers"]:
                        t["buyers"].append(s)
                else:
                    t["sells"] += 1
                    n_sell += 1
                if now - last_prune > PRUNE_S:
                    cutoff = now * 1000 - IDLE_S * 1000
                    for mk in [k for k, v in mints.items()
                               if v.get("emitted") or v["t0"] < cutoff - WIN * 1000]:
                        if not mints[mk].get("emitted"):
                            tt = mints[mk]
                            keep = bool(a.series) and is_v2(tt)
                            out.write(json.dumps(tape_features(tt, keep_series=keep)) + "\n")
                        del mints[mk]
                    last_prune = now
    finally:
        for t in mints.values():
            if not t.get("emitted") and t["buys"]:
                keep = bool(a.series) and is_v2(t)
                out.write(json.dumps(tape_features(t, keep_series=keep)) + "\n")
        out.close()
    print(f"live_ingest done raw={n_raw} buys={n_buy} sells={n_sell}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
