"""Config for robust RL memecoin bot."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

_DATA = str(Path(__file__).resolve().parents[1] / "data")


@dataclass
class BotConfig:
    # market / execution
    fee_bps_buy: int = 100
    fee_bps_sell: int = 100
    lp_bps: int = 20
    slippage_bps: int = 25
    tip_lamports: int = 5_000
    latency_ms: int = 800
    bundle_ms: int = 3
    # risk
    max_position_sol: float = 0.5
    max_daily_loss_sol: float = 0.2
    max_trades_per_hour: int = 30
    kill_drawdown_pct: float = 15.0
    min_pool_liquidity_sol: float = 20.0
    # RL
    lr: float = 3e-3
    gamma: float = 0.99
    clip_eps: float = 0.2
    entropy_coef: float = 0.01
    seed: int = 42
    # training regime with learnable edge (documented):
    # per-episode drift ~ N(drift_mu, drift_vol) gives momentum episodes
    # where buy-hold can beat ~1.25% round-trip costs.
    drift_mu: float = 0.004
    drift_vol: float = 0.0015
    base_vol: float = 0.012
    # training
    episodes: int = 500
    max_steps: int = 200
    checkpoint_path: str = _DATA + "/rl_bot.npz"

    def fee_lamports(self, gross: int, side: str) -> int:
        bps = self.fee_bps_buy if side == "buy" else self.fee_bps_sell
        return (int(gross) * int(bps) + 9_999) // 10_000
