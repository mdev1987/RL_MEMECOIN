"""Live trading loop — REAL MONEY. Paper signals, Jupiter fills.

Safety model (all fail-closed):
- Starts ONLY with --live AND LIVE_TRADING=1 AND LIVE_CONFIRM=YES AND key
  present AND no data/LIVE_KILL. Otherwise it refuses loudly.
- Entries: same v3 replay-slice signals as paper; fills via bot.live
  (/order -> guards -> sign -> /execute -> confirm).
- Exits: live Jupiter marks per open position (TP/SL/trail/TIME/STALE),
  closed via bot.live. Replay-simulated exits are NOT used live.
- Risk: separate live_wallet.json ledger, daily-loss/drawdown halts,
  LIVE_MAX_SOL cap (default 0.01 dust), MAXOPEN positions.
- Kill: `touch data/LIVE_KILL` halts entries immediately (opens still exit).

Usage (after shadow validation!):
  LIVE_TRADING=1 LIVE_CONFIRM=YES .venv/bin/python -m bot.live_loop --live
"""
from __future__ import annotations
import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

from bot.replay_eval import load_paths
from bot.wallet import Wallet
from bot.ledger import append as ledger_append, row as ledger_row
from bot.jup import (order_quote, price_diverges, token_decimals, SOL,
                     LAMPORTS)
from bot import live as L
from bot import signals as S
from notifier import get_notifier

log = logging.getLogger("live_loop")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

REPO = Path(__file__).resolve().parents[1]
REPLAYS = [p for p in os.environ.get(
    "REPLAY_PATHS", str(REPO / "data" / "12.jsonl.zst")).split(":") if p]
POLL_SECS = int(os.environ.get("POLL_SECS", "60"))
SIZE_SOL = float(os.environ.get("LIVE_SIZE_SOL",
                                os.environ.get("SIZE_SOL", "0.01")))
ENTRY_THRESH = (float(os.environ.get("ENTRY_MIN_RET", str(S.ENTRY_MIN_RET))),
                float(os.environ.get("ENTRY_MIN_BUY", str(S.ENTRY_MIN_BUY))),
                float(os.environ.get("ENTRY_MAX_DIP", str(S.ENTRY_MAX_DIP))))
MIN_LIQ_SOL = float(os.environ.get("MIN_LIQ_SOL", str(S.MIN_LIQ_SOL)))
SLICE = int(os.environ.get("SLICE", "25"))
MAXOPEN = int(os.environ.get("LIVE_MAXOPEN", "2"))
# Exit thresholds shared with paper via signals (same rule, live marks).
TP, SL, TRAIL = S.TAKE_PROFIT, S.STOP_LOSS, S.TRAILING
TIME_S = S.TIME_S
STALE_S = 600.0
LEDGER = os.environ.get("LEDGER_PATH", str(REPO / "data" / "live_decisions.jsonl"))
POSITIONS = str(REPO / "data" / "live_positions.json")
WALLET = str(REPO / "data" / "live_wallet.json")


def load_positions() -> dict:
    try:
        return json.loads(open(POSITIONS).read())
    except Exception:
        return {}


def save_positions(p: dict) -> None:
    tmp = POSITIONS + ".tmp"
    open(tmp, "w").write(json.dumps(p))
    os.replace(tmp, POSITIONS)


def live_mark(mint: str, qty_base: int) -> float | None:
    """Live SOL value of qty_base via quote (marks to market)."""
    q = order_quote(mint, SOL, qty_base)
    if not q:
        return None
    try:
        return int(q["outAmount"]) / LAMPORTS
    except Exception:
        return None


def main(require_live_flag: bool = True) -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.parse_args()
    ntf = get_notifier()
    problems = []
    if require_live_flag and os.environ.get("_LIVE_FLAG") != "1":
        problems.append("missing --live (re-run with --live)")
    if not L.live_enabled():
        problems.append("LIVE_TRADING!=1")
    if os.environ.get("LIVE_CONFIRM") != "YES":
        problems.append("LIVE_CONFIRM!=YES")
    if L.killed():
        problems.append("LIVE_KILL present")
    try:
        kp = L._load_keypair()
        taker = str(kp.pubkey())
    except Exception as exc:
        problems.append(f"key: {exc}")
        taker = "?"
    if problems:
        msg = "LIVE REFUSED: " + "; ".join(problems)
        log.error(msg)
        ntf.send_alert("🔴 LIVE REFUSED", "; ".join(problems))
        raise SystemExit(msg)
    hk = os.environ.get("HELIUS_API_KEY", "")
    w = Wallet(path=WALLET, start=0.0, daily_stop=0.05, dd_stop=0.10,
               max_pos=SIZE_SOL)
    ntf.send_alert("🔴 LIVE TRADING ACTIVE",
                   f"taker {taker[:8]} size {SIZE_SOL:g} SOL maxopen {MAXOPEN}")
    log.info("LIVE active taker=%s size=%s", taker[:8], SIZE_SOL)
    visits: dict[str, int] = {p: 0 for p in REPLAYS}
    cycle = 0
    while True:
        if L.killed() or w.s.halted:
            log.warning("halted/killed — exits only")
        replay = REPLAYS[cycle % len(REPLAYS)]
        cycle += 1
        try:
            paths, _ = load_paths(replay, max_lines=200000)
        except (FileNotFoundError, OSError):
            time.sleep(POLL_SECS)
            continue
        off = (visits[replay] * SLICE) % len(paths) if paths else 0
        visits[replay] += 1
        batch = (paths + paths)[off:off + SLICE] if paths else []
        import collections as _collections
        skip = _collections.Counter()
        # 1) manage opens on live marks (same exit rule as paper)
        poss = load_positions()
        for mint, p in list(poss.items()):
            mark = live_mark(mint, p["qty_base"])
            now = time.time()
            if mark is None:
                if now - p["t"] > STALE_S:
                    log.warning("STALE no-quote %s — keeping, retry next cycle",
                                mint[:8])
                    skip["live:no-quote"] += 1
                continue
            if now < p.get("cool_until", 0.0):
                continue  # backing off after a venue miss
            peak = max(p.get("peak", 0.0), mark)
            p["peak"] = peak
            entry_val = p["size"]
            rr = mark / entry_val if entry_val > 0 else 0.0
            why = S.decide_exit(entry_val, peak, mark, now - p["t"])
            if why is None:
                continue
            try:
                rc = L.place_order(mint, SOL, p["qty_base"], p["size"])
                pnl = mark - p["size"]
                w.apply_close(mint, pnl)
                ledger_append(LEDGER, ledger_row(
                    file="live", mint=mint, reason="live-" + why,
                    r_net=pnl / p["size"], pnl_sol=pnl,
                    balance_after=w.s.balance, wins=w.s.wins,
                    losses=w.s.losses))
                ntf.send_close(
                    ca=mint, name=mint[:12], reason="TP" if why == "take"
                    else ("STOP" if why == "stop"
                          else ("TRAIL" if why == "trail" else "TIME")),
                    mult=rr, pnl_sol=pnl, hold_s=now - p["t"],
                    entry_px=p.get("entry_px"), exit_px=mark,
                    size_sol=p["size"], balance_before=w.s.balance - pnl,
                    balance_after=w.s.balance, win_rate=w.s.win_rate,
                    dex="jupiter", via=f"live sig {rc.signature[:8]}")
                log.info("LIVE SELL %s %s sig=%s", mint[:8], why,
                         rc.signature[:12])
                log.info("LIVE actuals in=%s out=%s (quoted %s)",
                         rc.total_in, rc.total_out, rc.out_amount)
                del poss[mint]
                save_positions(poss)
            except L.NoQuote as exc:
                # routine venue miss (illiquid mint): skip like paper's
                # `filtered` — counted, never alerted; cool down retries.
                # After repeated misses the exit is unclosable (dead mint):
                # book the rug so the corpse can't clog the book.
                if "throttled" in str(exc):
                    poss[mint]["cool_until"] = time.time() + 2.0
                    save_positions(poss)
                    log.info("LIVE skip no-quote %s: %s", mint[:8], exc)
                    continue
                skip["live:no-quote"] += 1
                poss[mint]["cool_until"] = time.time() + 60.0
                misses = poss[mint].get("misses", 0) + 1
                poss[mint]["misses"] = misses
                save_positions(poss)
                log.info("LIVE skip no-quote %s: %s", mint[:8], exc)
                if L.rug_give_up(misses):
                    # Dead mint, no venue will quote it: economically zero.
                    # Book the rug (mirrors sim rug=-1.0) and free the slot.
                    log.warning("LIVE rug-close %s after %d misses",
                                mint[:8], misses)
                    pnl = -poss[mint]["size"]
                    w.apply_close(mint, pnl)
                    ledger_append(LEDGER, ledger_row(
                        file="live", mint=mint, reason="live-rug",
                        r_net=-1.0, pnl_sol=pnl,
                        balance_after=w.s.balance, wins=w.s.wins,
                        losses=w.s.losses))
                    ntf.send_close(
                        ca=mint, name=mint[:12], reason="RUG", mult=0.0,
                        pnl_sol=pnl, hold_s=time.time() - poss[mint]["t"],
                        entry_px=poss[mint].get("entry_px"), exit_px=0.0,
                        size_sol=poss[mint]["size"],
                        balance_before=w.s.balance - pnl,
                        balance_after=w.s.balance, win_rate=w.s.win_rate,
                        dex="jupiter", via="live-rug")
                    del poss[mint]
                    save_positions(poss)
            except Exception as exc:
                log.error("LIVE SELL FAILED %s: %s", mint[:8], exc)
                ntf.send_alert("🔴 LIVE SELL FAILED", f"{mint[:8]}: {exc}")
        # 2) entries (skip entirely when killed/halted/capped) — same
        # entry gate as paper, Jupiter fills instead of simulation.
        if not L.killed() and not w.s.halted and len(poss) < MAXOPEN:
            for d in batch:
                if len(load_positions()) >= MAXOPEN:
                    break
                take, _ = S.decide_entry(
                    d["prices"], d.get("actions"), d.get("liq_series"),
                    liq=d.get("liq", 0.0), thresh=ENTRY_THRESH,
                    min_liq=MIN_LIQ_SOL)
                if not take:
                    skip["strategy:filtered"] += 1
                    continue
                ok, why_not = w.can_open(SIZE_SOL, d.get("mint", "?"))
                if not ok:
                    skip[f"wallet:{why_not}"] += 1
                    continue
                mint = d.get("mint", "?")
                # data-quality preflight BEFORE spending real SOL: the
                # read-only quote must agree with the tape the signal used
                # (a mis-scaled tape must never trigger a real buy).
                dec = token_decimals(mint, hk) or 6
                tape_px = float(d["prices"][10])
                pq = order_quote(SOL, mint, int(round(SIZE_SOL * LAMPORTS)))
                if not pq or not pq.get("outAmount"):
                    skip["live:no-quote"] += 1
                    continue
                try:
                    vpx = SIZE_SOL / (int(pq["outAmount"]) / (10 ** dec))
                except Exception:
                    skip["live:no-quote"] += 1
                    continue
                if price_diverges(tape_px, vpx):
                    skip["live:ghost"] += 1
                    log.warning("LIVE entry ghost %s tape_px=%s venue_px=%s "
                                "(skipped)", mint[:8], tape_px, vpx)
                    continue
                try:
                    rc = L.place_order(SOL, mint,
                                       int(round(SIZE_SOL * LAMPORTS)),
                                       SIZE_SOL)
                    qty = int(int(rc.out_amount) if str(rc.out_amount).isdigit()
                              else 0)
                    poss = load_positions()
                    poss[mint] = {"t": time.time(), "size": SIZE_SOL,
                                  "qty_base": qty, "decimals": dec,
                                  "entry_px": float(d["prices"][10]),
                                  "peak": 0.0, "sig": rc.signature}
                    save_positions(poss)
                    ntf.send_open(ca=mint, name=mint[:12],
                                  price=float(d["prices"][10]),
                                  size_sol=SIZE_SOL,
                                  balance_before=w.s.balance,
                                  balance_after=w.s.balance - SIZE_SOL,
                                  open_count=len(poss),
                                  max_positions=MAXOPEN, win_rate=w.s.win_rate,
                                  dex="jupiter",
                                  jup=f"🔴 LIVE BUY sig `{rc.signature[:12]}`")
                    log.info("LIVE BUY %s sig=%s", mint[:8],
                             rc.signature[:12])
                except L.NoQuote as exc:
                    skip["live:no-quote"] += 1
                    log.info("LIVE skip no-quote %s: %s", mint[:8], exc)
                except Exception as exc:
                    log.error("LIVE BUY FAILED %s: %s", mint[:8], exc)
                    ntf.send_alert("🔴 LIVE BUY FAILED", f"{mint[:8]}: {exc}")
            log.info("cycle done skip=%s sleeping %ds",
                     dict(skip), POLL_SECS)
        time.sleep(POLL_SECS)


if __name__ == "__main__":
    import sys
    if "--live" in sys.argv:
        os.environ["_LIVE_FLAG"] = "1"
    print(f"[{datetime.now(UTC):%H:%M:%S}] live loop starting", flush=True)
    main()
