"""Realtime shadow trader: live market signals, signed-never-sent fills.

Live PumpAPI ticks -> v3 entry gate (shared signals.decide_entry) ->
SHADOW Jupiter order (full /order + guards + local sign, NEVER executes)
-> paper positions tracked on live marks -> shared exit rule ->
shadow ledger + Telegram cards (via="shadow").

No real orders in any configuration: place_order is always called with
shadow=True, and LIVE_TRADING is never consulted. The funded wallet only
pays nothing; the key signs locally for parity measurement.

Usage: .venv/bin/python -m bot.shadow_loop [--secs 1800]
Deposits: data/shadow_wallet.json, data/shadow_decisions.jsonl
"""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

from bot.replay_eval import is_pump_pool
from bot.wallet import Wallet
from bot.ledger import append as ledger_append, row as ledger_row
from bot.jup import token_decimals, SOL, LAMPORTS
from bot import live as L
from bot import signals as S
from notifier import get_notifier

log = logging.getLogger("shadow_loop")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

REPO = Path(__file__).resolve().parents[1]
URL = "wss://stream.pumpapi.io"
SIZE_SOL = float(os.environ.get("SHADOW_SIZE_SOL", "0.01"))
# Shadow fills go through the live executor's guards (LIVE_MAX_SOL cap);
# keep the default at dust scale so signals never trip the cap.
MAXOPEN = int(os.environ.get("SHADOW_MAXOPEN", "2"))
ENTRY_N = 11  # need entry_lookback+1 buys before the gate can run
PRUNE_S = 60.0
IDLE_DROP_S = 1800.0
MAX_MINTS = 5000
WALLET = str(REPO / "data" / "shadow_wallet.json")
LEDGER = str(REPO / "data" / "shadow_decisions.jsonl")


def new_tape(mint: str, ts: int):
    return {"mint": mint, "t0": ts, "prices": [], "acts": [],
            "liq": [], "buyers": [], "sells": 0, "last_ts": ts,
            "done": False}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=0.0,
                    help="bounded run seconds (0 = forever)")
    a = ap.parse_args()
    import websockets
    ntf = get_notifier()
    hk = os.environ.get("HELIUS_API_KEY", "")
    try:
        taker = str(L._load_keypair().pubkey())
    except Exception as exc:
        log.error("shadow needs a signing key: %s", exc)
        raise SystemExit(f"shadow needs key: {exc}")
    w = Wallet(path=WALLET, start=1.0, daily_stop=0.10, dd_stop=0.30,
               max_pos=SIZE_SOL)
    ntf.send_startup(f"🕶️ Shadow mode • size {SIZE_SOL:g} SOL • taker {taker[:8]} • "
                     f"live market, signed-never-sent")
    log.info("shadow active taker=%s size=%s", taker[:8], SIZE_SOL)
    mints: dict[str, dict] = {}
    poss: dict[str, dict] = {}
    t_end = time.time() + a.secs if a.secs > 0 else float("inf")
    last_prune = time.time()

    def close_position(mint: str, why: str, mark: float) -> None:
        p = poss.pop(mint)
        pnl = mark - p["size"]
        halted = w.apply_close(mint, pnl)
        ledger_append(LEDGER, ledger_row(
            file="live", mint=mint, reason="shadow-" + why,
            r_net=pnl / p["size"], pnl_sol=pnl,
            balance_after=w.s.balance, wins=w.s.wins, losses=w.s.losses))
        total = w.s.wins + w.s.losses
        ntf.send_close(
            ca=mint, name=mint[:12],
            reason="TP" if why == "take" else ("STOP" if why == "stop"
                    else ("TRAIL" if why == "trail" else "TIME")),
            mult=mark / p["size"] if p["size"] > 0 else 1.0,
            pnl_sol=pnl, hold_s=time.time() - p["t"],
            entry_px=p.get("entry_px"), exit_px=mark, size_sol=p["size"],
            balance_before=w.s.balance - pnl, balance_after=w.s.balance,
            win_rate=100.0 * w.s.wins / total if total else 0.0,
            dex="jupiter", via="shadow")
        log.info("SHADOW SELL %s %s pnl=%+.5f bal=%.4f halted=%s",
                 mint[:8], why, pnl, w.s.balance, halted)

    async def run():
        nonlocal last_prune
        async with websockets.connect(URL, max_size=50_000_000) as ws:
            log.info("shadow stream connected")
            while time.time() < t_end:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                except asyncio.TimeoutError:
                    continue
                try:
                    e = json.loads(raw)
                except Exception:
                    continue
                act = e.get("action")
                m = e.get("mint")
                if act not in ("buy", "sell") or not m:
                    continue
                if not is_pump_pool({"pool": e.get("pool"),
                                     "protocol": e.get("protocol")}):
                    continue
                px = e.get("price")
                if not px or float(px) <= 0:
                    continue
                px = float(px)
                ts = int(e.get("timestamp") or int(time.time() * 1000))
                t = mints.get(m)
                if t is None:
                    if len(mints) >= MAX_MINTS:
                        continue
                    t = mints[m] = new_tape(m, ts)
                t["last_ts"] = ts
                if t["done"]:
                    pass  # still update marks below via poss
                else:
                    # aligned per-print series (buys AND sells), mirroring
                    # replay slot aggregation: one mark per print.
                    t["prices"].append(px)
                    t["acts"].append(act)
                    liq = e.get("quoteInPool")
                    t["liq"].append(float(liq) if liq else 0.0)
                    if act == "buy":
                        s = e.get("txSigner")
                        if s and s not in t["buyers"]:
                            t["buyers"].append(s)
                    else:
                        t["sells"] += 1
                # live mark for open paper positions (last-print marks)
                if m in poss and t["prices"]:
                    p = poss[m]
                    mark = px * p["qty_tokens"]
                    p["peak"] = max(p.get("peak", 0.0), mark)
                    why = S.decide_exit(p["size"], p["peak"], mark,
                                        time.time() - p["t"])
                    if why is None or w.s.halted:
                        continue
                    if time.time() < p.get("cool_until", 0.0):
                        continue  # backing off after a venue miss
                    try:
                        rc = L.place_order(
                            m, SOL, p["qty_base"], p["size"],
                            shadow=True)
                        p.pop("cool_until", None)
                        log.info("SHADOW exit quote out=%s",
                                 rc.out_amount)
                    except L.NoQuote as exc:
                        log.info("SHADOW exit no-quote %s: %s",
                                 m[:8], exc)
                        p["cool_until"] = time.time() + 60.0
                        continue
                    except Exception as exc:
                        log.warning("SHADOW exit sign failed %s: %s",
                                    m[:8], exc)
                        continue
                    close_position(m, why, mark)
                # entry gate on fresh tapes only
                if (not t["done"] and m not in poss and not w.s.halted
                        and len(poss) < MAXOPEN
                        and len(t["prices"]) >= ENTRY_N):
                    t["done"] = True
                    take, _ = S.decide_entry(
                        t["prices"][:ENTRY_N], t["acts"][:ENTRY_N],
                        t["liq"][:ENTRY_N])
                    if not take:
                        continue
                    ok, why_not = w.can_open(SIZE_SOL, m)
                    if not ok:
                        continue
                    try:
                        rc = L.place_order(
                            SOL, m, int(round(SIZE_SOL * LAMPORTS)),
                            SIZE_SOL, shadow=True)
                    except L.NoQuote:
                        continue
                    except Exception as exc:
                        log.warning("SHADOW entry sign failed %s: %s",
                                    m[:8], exc)
                        continue
                    dec = token_decimals(m, hk) or 6
                    try:
                        qty_base = int(rc.out_amount)
                    except Exception:
                        continue
                    if qty_base <= 0:
                        continue
                    poss[m] = {"t": time.time(), "size": SIZE_SOL,
                               "qty_base": qty_base,
                               "qty_tokens": qty_base / (10 ** dec),
                               "entry_px": t["prices"][ENTRY_N - 1],
                               "peak": 0.0, "sig": rc.signature}
                    ntf.send_open(
                        ca=m, name=m[:12], price=t["prices"][ENTRY_N - 1],
                        size_sol=SIZE_SOL, balance_before=w.s.balance,
                        balance_after=w.s.balance - SIZE_SOL,
                        open_count=len(poss),
                        max_positions=MAXOPEN, win_rate=w.s.win_rate,
                        dex="jupiter", buys=len(t["prices"]),
                        jup="🕶️ SHADOW BUY (signed-never-sent)")
                    log.info("SHADOW BUY %s epx=%s", m[:8],
                             t["prices"][ENTRY_N - 1])
                now = time.time()
                if now - last_prune > PRUNE_S:
                    cutoff = now * 1000 - IDLE_DROP_S * 1000
                    for mk in [k for k, v in mints.items()
                               if k not in poss and v["last_ts"] < cutoff]:
                        del mints[mk]
                    last_prune = now

    asyncio.run(run())
    log.info("shadow done bal=%.4f W=%d L=%d",
             w.s.balance, w.s.wins, w.s.losses)


if __name__ == "__main__":
    main()
