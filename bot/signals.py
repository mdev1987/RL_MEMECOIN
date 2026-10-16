"""Shared trade decisions: ONE entry rule, ONE exit rule set, both modes.

Paper (`paper_loop`) and live (`live_loop`) import from here so a signal
means the same thing in both modes. The modes differ ONLY in the fill path
(simulated bars vs Jupiter execution) and the price source for exits
(closed replay bars vs live marks) — never in the decision logic.

Entry (v3, frozen): bar-10 ret>=5%, buy_ratio>=60%, dip>=-3%, liq>=30 SOL.
Exits: TP +60%, SL -12%, trail -15% off peak, TIME 1h. Same constants both.
"""
from __future__ import annotations

# Frozen v3 decision constants — change only with a new validated config.
ENTRY_MIN_RET = 0.05
ENTRY_MIN_BUY = 0.60
ENTRY_MAX_DIP = -0.03
MIN_LIQ_SOL = 30.0
TAKE_PROFIT = 0.60
STOP_LOSS = 0.12
TRAILING = 0.15
TIME_S = 3600.0

ENTRY_THRESH = (ENTRY_MIN_RET, ENTRY_MIN_BUY, ENTRY_MAX_DIP)


def decide_entry(prices, actions=None, liq_series=None, liq: float = 0.0,
                 thresh=ENTRY_THRESH,
                 min_liq: float = MIN_LIQ_SOL) -> tuple[bool, dict | None]:
    """Shared entry gate. Returns (trade?, features-or-None).

    Order mirrors the cost of evaluation: liquidity first (cheap),
    then momentum filter. No lookahead: bars <=10 only.
    """
    from bot.strategy import early_features, select_entry, entry_liq_ok
    ls = list(liq_series) if liq_series else [float(liq)] * 11
    if not entry_liq_ok(ls, min_liq=min_liq):
        return False, None
    feat = early_features(prices, actions, 10)
    if not select_entry(feat, tuple(thresh)):
        return False, feat
    return True, feat


def decide_exit(entry_val: float, peak: float, mark: float,
                age_s: float, time_s: float = TIME_S) -> str | None:
    """Shared exit rule on live/realized marks. Returns reason or None.

    Priority matches run_selective: stop first (capital protection),
    then trailing, then take-profit, then timeout.
    """
    if entry_val <= 0 or mark <= 0:
        return None
    rr = mark / entry_val
    if rr <= 1 - STOP_LOSS:
        return "stop"
    if peak > 0 and mark <= peak * (1 - TRAILING):
        return "trail"
    if rr >= 1 + TAKE_PROFIT:
        return "take"
    if age_s > time_s:
        return "hold-end"
    return None
