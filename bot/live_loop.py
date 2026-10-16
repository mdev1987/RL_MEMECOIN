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
from bot.strategy import entry_liq_ok
from bot.wallet import Wallet
from bot.ledger import append as ledger_append, row as ledger_row
from bot.jup import token_decimals, SOL, LAMPORTS
from bot import live as L
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
ENTRY_THRESH = (float(os.environ.get("ENTRY_MIN_RET", "0.05")),
                float(os.environ.get("ENTRY_MIN_BUY", "0.60")),
                float(os.environ.get("ENTRY_MAX_DIP", "-0.03")))
MIN_LIQ_SOL = float(os.environ.get("MIN_LIQ_SOL", "30.0"))
SLICE = int(os.environ.get("SLICE", "25"))
MAXOPEN = int(os.environ.get("LIVE_MAXOPEN", "2"))
TP, SL, TRAIL = 0.6, 0.12, 0.15
TIME_S = 3600.0
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
    from bot.jup import order_quote
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
        # 1) manage opens on live marks
        poss = load_positions()
        for mint, p in list(poss.items()):
            mark = live_mark(mint, p["qty_base"])
            now = time.time()
            if mark is None:
                if now - p["t"] > STALE_S:
                    log.warning("STALE no-quote %s — keeping, retry next cycle",
                                mint[:8])
                continue
            peak = max(p.get("peak", 0.0), mark)
            p["peak"] = peak
            entry_val = p["size"]
            rr = mark / entry_val if entry_val > 0 else 0.0
            why = None
            if rr <= 1 - SL:
                why = "stop"
            elif peak > 0 and mark <= peak * (1 - TRAIL):
                why = "trail"
            elif rr >= 1 + TP:
                why = "take"
            elif now - p["t"] > TIME_S:
                why = "hold-end"
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
                    else ("SL" if why in ("stop", "trail") else "TIME"),
                    mult=rr, pnl_sol=pnl, hold_s=now - p["t"],
                    entry_px=p.get("entry_px"), exit_px=mark,
                    size_sol=p["size"], balance_before=w.s.balance - pnl,
                    balance_after=w.s.balance, win_rate=w.s.win_rate,
                    dex="jupiter", via=f"live sig {rc.signature[:8]}")
                log.info("LIVE SELL %s %s sig=%s", mint[:8], why,
                         rc.signature[:12])
                del poss[mint]
                save_positions(poss)
            except Exception as exc:
                log.error("LIVE SELL FAILED %s: %s", mint[:8], exc)
                ntf.send_alert("🔴 LIVE SELL FAILED", f"{mint[:8]}: {exc}")
        # 2) entries (skip entirely when killed/halted/capped)
        if not L.killed() and not w.s.halted and len(poss) < MAXOPEN:
            from bot.strategy import early_features, select_entry
            for d in batch:
                if len(load_positions()) >= MAXOPEN:
                    break
                if not entry_liq_ok(d.get("liq_series") or [d.get("liq", 0.0)] * 11,
                                    min_liq=MIN_LIQ_SOL):
                    continue
                ok, _ = w.can_open(SIZE_SOL, d.get("mint", "?"))
                if not ok:
                    continue
                feat = early_features(d["prices"], d.get("actions"), 10)
                if not select_entry(feat, ENTRY_THRESH):
                    continue
                mint = d.get("mint", "?")
                try:
                    rc = L.place_order(SOL, mint,
                                       int(round(SIZE_SOL * LAMPORTS)),
                                       SIZE_SOL)
                    dec = token_decimals(mint, hk) or 6
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
                                  balance_after=w.s.balance,
                                  open_count=len(poss),
                                  max_positions=MAXOPEN, win_rate=w.s.win_rate,
                                  dex="jupiter",
                                  jup=f"🔴 LIVE BUY sig `{rc.signature[:12]}`")
                    log.info("LIVE BUY %s sig=%s", mint[:8],
                             rc.signature[:12])
                except Exception as exc:
                    log.error("LIVE BUY FAILED %s: %s", mint[:8], exc)
                    ntf.send_alert("🔴 LIVE BUY FAILED", f"{mint[:8]}: {exc}")
        time.sleep(POLL_SECS)


if __name__ == "__main__":
    import sys
    if "--live" in sys.argv:
        os.environ["_LIVE_FLAG"] = "1"
    print(f"[{datetime.now(UTC):%H:%M:%S}] live loop starting", flush=True)
    main()
