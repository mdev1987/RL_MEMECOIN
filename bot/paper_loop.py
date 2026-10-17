"""Paper trading loop — background daemon with Telegram open/close cards.

Polls PumpAPI replay (or live stream later) through the selective strategy,
sends pro-markdown Telegram cards via notifier.py, console-only when creds missing.
"""
from __future__ import annotations
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # cwd first (lowest priority)
# Repo .env must win over daemon-injected vars (e.g. oxmgr/opencode
# exports its own TELEGRAM_BOT_TOKEN); override=True is load-bearing.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

from bot.replay_eval import load_paths
from bot.strategy import COST_PATHS, entry_liq_ok, run_selective
from bot.wallet import Wallet
from bot.ledger import append as ledger_append, row as ledger_row
from bot.jup import enabled as jup_enabled, fmt_quote, order_quote, token_decimals, SOL, LAMPORTS
from bot import signals as S
from notifier import get_notifier

log = logging.getLogger("paper_loop")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

REPLAY = os.environ.get("REPLAY_PATH", str(Path(__file__).resolve().parents[1] / "data" / "12.jsonl.zst"))
# Colon-separated rotation across replay hours; one file scanned per cycle
# so a 1-CPU box never parses more than max_lines lines per POLL_SECS.
REPLAYS = [p for p in os.environ.get("REPLAY_PATHS", REPLAY).split(":") if p]
POLL_SECS = int(os.environ.get("POLL_SECS", "300"))
SIZE_SOL = float(os.environ.get("SIZE_SOL", "0.05"))
BALANCE = float(os.environ.get("START_BALANCE_SOL", "1.0"))
# Realistic execution (pessimistic fills, venue costs, failed txs).
COST_PATH = os.environ.get("COST_PATH", "swqos")
_COSTS = COST_PATHS.get(COST_PATH, COST_PATHS["swqos"])
LATENCY_BARS = int(os.environ.get("LATENCY_BARS", "1"))
FAIL_RATE = float(os.environ.get("FAIL_RATE", "0.02"))
# Entry filter defaults to the frozen shared rule (env-overridable).
ENTRY_MIN_RET = float(os.environ.get("ENTRY_MIN_RET", str(S.ENTRY_MIN_RET)))
ENTRY_MIN_BUY = float(os.environ.get("ENTRY_MIN_BUY", str(S.ENTRY_MIN_BUY)))
ENTRY_MAX_DIP = float(os.environ.get("ENTRY_MAX_DIP", str(S.ENTRY_MAX_DIP)))
ENTRY_THRESH = (ENTRY_MIN_RET, ENTRY_MIN_BUY, ENTRY_MAX_DIP)
MIN_LIQ_SOL = float(os.environ.get("MIN_LIQ_SOL", str(S.MIN_LIQ_SOL)))
# Forward-validation ledger: every paper decision lands here as JSONL.
LEDGER = os.environ.get("LEDGER_PATH",
                        str(Path(__file__).resolve().parents[1] / "data" / "decisions.jsonl"))
# candidates examined per cycle; the window rotates each cycle so static
# replay files yield fresh mints instead of the same first 25 forever
SLICE = int(os.environ.get("SLICE", "25"))


def main() -> None:
    ntf = get_notifier()
    log.info("paper loop start (enabled=%s) replays=%s", ntf.enabled, REPLAYS)
    ntf.send_startup(f"Paper mode • size {SIZE_SOL:g} SOL • balance {BALANCE:.2f} SOL\n"
                     f"realistic: path={COST_PATH} latency={LATENCY_BARS}bar fail={FAIL_RATE:g}\n"
                     f"filter: ret>={ENTRY_MIN_RET:g} buy>={ENTRY_MIN_BUY:g} dip>={ENTRY_MAX_DIP:g} liq>={MIN_LIQ_SOL:g}")
    w = Wallet(path=str(Path(__file__).resolve().parents[1] / "data" / "paper_wallet.json"),
               start=BALANCE, daily_stop=0.10, dd_stop=0.30, max_pos=SIZE_SOL)
    balance, wins, losses = w.s.balance, w.s.wins, w.s.losses
    if w.s.halted:
        ntf.send_alert("Wallet halted", w.s.halted)
    cycle = 0
    # Per-file visit counters: the old global-cycle stride
    # (off=((cycle-1)*SLICE)%len) visited only a fixed subset of offsets
    # per file (e.g. 4 of ~140 rows for 13.jsonl.zst) and permanently
    # blinded the bot to tradeable mints. Per-file strides guarantee full
    # coverage with period len/gcd(len,SLICE).
    visits: dict[str, int] = {p: 0 for p in REPLAYS}
    try:
        while True:
            if w.s.halted:
                log.warning("halted=%s sleeping", w.s.halted)
                time.sleep(POLL_SECS)
                continue
            replay = REPLAYS[cycle % len(REPLAYS)]
            cycle += 1
            try:
                paths, n = load_paths(replay, max_lines=200000)
            except (FileNotFoundError, OSError) as exc:
                log.warning("replay missing=%s (%s) sleeping %ds", replay, exc, POLL_SECS)
                time.sleep(POLL_SECS)
                continue
            log.info("scanned=%d paths=%d file=%s", n, len(paths), Path(replay).name)
            off = (visits[replay] * SLICE) % len(paths) if paths else 0
            visits[replay] += 1
            batch = (paths + paths)[off:off + SLICE] if paths else []
            log.info("slice off=%d n=%d visit=%d", off, len(batch), visits[replay])
            import collections as _collections
            skip = _collections.Counter()
            closed_before = wins + losses
            for d in batch:
                if not entry_liq_ok(d.get("liq_series") or [d.get("liq", 0.0)] * 11,
                                    min_liq=MIN_LIQ_SOL):
                    skip["liq-fail"] += 1
                    continue
                ok, why_not = w.can_open(SIZE_SOL, d.get("mint", "?"))
                if not ok:
                    if why_not in ("daily-loss", "drawdown"):
                        ntf.send_alert("Wallet halted", why_not)
                        log.warning("halt: %s", why_not)
                        break
                    if why_not == "rate-limit":
                        log.warning("hourly rate limit reached, ending cycle")
                        skip["rate-limit"] += 1
                        break
                    skip[f"wallet:{why_not}"] += 1
                    continue
                r, why, exit_px = run_selective(
                    d["prices"], d["actions"], take_profit=0.6,
                    size_sol=SIZE_SOL, latency_bars=LATENCY_BARS,
                    fail_rate=FAIL_RATE, fail_seed=d.get("mint", "?"),
                    extra_bps=_COSTS["extra_bps"],
                    fixed_cost_sol=_COSTS["fixed_sol"],
                    liq_series=d.get("liq_series"),
                    entry_thresh=ENTRY_THRESH)
                if why in ("filtered", "too-short", "bad-tick") or r == 0.0:
                    skip[f"strategy:{why}"] += 1
                    continue
                if why == "failed-tx":
                    fee = -r * SIZE_SOL  # fixed costs only, no position
                    w.apply_fee(d.get("mint", "?"), fee)
                    balance = w.s.balance
                    ledger_append(LEDGER, ledger_row(
                        file=Path(replay).name, mint=d.get("mint", "?"),
                        reason="failed-tx", r_net=r, pnl_sol=-fee,
                        balance_after=balance, wins=wins, losses=losses))
                    log.info("failed-tx %s fee=%.6f bal=%.4f",
                             (d.get("mint", "?") or "?")[:12], fee, balance)
                    continue
                name = (d.get("mint", "?") or "?")[:12]
                ca = d.get("mint", "?")
                # Live venue quote for the fill (fail-open: card sends regardless)
                jup_line = None
                if jup_enabled():
                    _q = order_quote(SOL, ca, int(round(SIZE_SOL * LAMPORTS)),
                                     replay=True)
                    jup_line = fmt_quote(_q, "buy")
                    if jup_line:
                        log.info("jupq buy %s", jup_line)
                # OPEN card (after = capital committed to the position)
                ntf.send_open(ca=ca, name=name, price=float(d["prices"][10]),
                              size_sol=SIZE_SOL, balance_before=balance,
                              balance_after=balance - SIZE_SOL, dex="pump-amm",
                              liq_usd=d.get("liq", 0.0) * 150.0, jup=jup_line)
                # simulate hold duration ~ bars
                hold_s = float(len(d["prices"]) * 2)
                pnl = r * SIZE_SOL
                halted = w.apply_close(d.get("mint", "?"), pnl)
                balance, wins, losses = w.s.balance, w.s.wins, w.s.losses
                total = wins + losses
                wr = 100.0 * wins / total if total else 0.0
                # CLOSE card (mult is net of costs; exit is the actual exit price)
                jup_close = None
                if jup_enabled():
                    import os as _os2
                    _hk2 = _os2.environ.get("HELIUS_API_KEY", "")
                    _dec = token_decimals(ca, _hk2)
                    _epx = float(d["prices"][10])
                    if _dec is not None and _epx > 0:
                        _qty = int(SIZE_SOL / _epx * (10 ** _dec))
                        _qc = order_quote(ca, SOL, _qty, replay=True)
                        jup_close = fmt_quote(_qc, "sell")
                        if jup_close:
                            log.info("jupq sell %s", jup_close)
                ntf.send_close(ca=ca, name=name,
                               reason="TP" if why == "take" else ("STOP" if why == "stop" else ("TRAIL" if why == "trail" else ("RUG" if why == "rug" else "TIME"))),
                               mult=1.0 + r, pnl_sol=pnl, hold_s=hold_s,
                               entry_px=float(d["prices"][10]),
                               exit_px=float(exit_px) if exit_px is not None else float(d["prices"][-1]),
                               size_sol=SIZE_SOL, balance_before=balance - pnl,
                               balance_after=balance, win_rate=wr, dex="pump-amm",
                               via="paper", jup=jup_close)
                log.info("%s %s r=%+.2f%% bal=%.4f", why, name, r * 100, balance)
                ledger_append(LEDGER, ledger_row(
                    file=Path(replay).name, mint=ca, reason=why, r_net=r,
                    pnl_sol=pnl, balance_after=balance,
                    wins=wins, losses=losses))
            if wins + losses > closed_before:
                ntf.send_summary(0, wins + losses, 100.0 * wins / max(wins + losses, 1), balance - BALANCE)
            else:
                log.info("cycle done bal=%.4f skip=%s (no closes, summary suppressed) sleeping %ds",
                         balance, dict(skip), POLL_SECS)
                time.sleep(POLL_SECS)
                continue
            log.info("cycle done bal=%.4f skip=%s sleeping %ds",
                     balance, dict(skip), POLL_SECS)
            time.sleep(POLL_SECS)
    except KeyboardInterrupt:
        ntf.send_stopped(0, wins + losses, 100.0 * wins / max(wins + losses, 1), balance - BALANCE)


if __name__ == "__main__":
    print(f"[{datetime.now(UTC):%H:%M:%S}] paper loop starting", flush=True)
    main()
