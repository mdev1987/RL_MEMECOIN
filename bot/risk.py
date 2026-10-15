"""Risk guards: position caps, daily loss, trade rate, drawdown kill-switch."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class RiskState:
    day_pnl: float = 0.0
    trades_this_hour: int = 0
    halted: bool = False


def check_order(cfg, state: RiskState, side: str, size_sol: float, equity: float, peak: float) -> tuple[bool, str]:
    if state.halted:
        return False, "halted"
    if size_sol > cfg.max_position_sol:
        return False, "position-cap"
    if state.day_pnl <= -cfg.max_daily_loss_sol:
        state.halted = True
        return False, "daily-loss"
    if state.trades_this_hour >= cfg.max_trades_per_hour:
        return False, "rate-limit"
    dd = (peak - equity) / peak * 100 if peak > 0 else 0
    if dd >= cfg.kill_drawdown_pct:
        state.halted = True
        return False, "drawdown"
    return True, "ok"
