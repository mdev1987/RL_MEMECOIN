"""Latency- and bundle-aware trading environment (numpy only, no lookahead)."""
from __future__ import annotations
import numpy as np
from .config import BotConfig
from pumpswap_sim import predict_buy_exact_in, predict_sell_gross


class PumpSwapEnv:
    """One episode = one token price path. Actions: 0=hold,1=buy,2=sell."""

    def __init__(self, cfg: BotConfig | None = None):
        self.cfg = cfg or BotConfig()
        self.rng = np.random.default_rng(self.cfg.seed)
        self.reset()

    def _obs(self):
        q, b = float(self.q_eff), float(self.b_res)
        price = q / max(b, 1)
        logp = float(np.log(price / self.p0)) if self.p0 > 0 else 0.0
        inv = self.tokens / max(self.max_tokens, 1.0)
        cash_r = self.cash / self.start_cash
        return np.array([logp, inv, cash_r, self.step_i / self.max_steps,
                         (q - self.q0) / self.q0], dtype=np.float64)

    def reset(self, price_path=None, q0=368_955_755_953, b0=47_821_746_268_213):
        self.q0, self.b0 = int(q0), int(b0)
        self.q_eff, self.b_res = int(q0), int(b0)
        self.p0 = self.q0 / self.b0
        self.cash = 1.0  # SOL
        self.start_cash = 1.0
        self.tokens = 0.0
        self.max_tokens = 1.0
        self.step_i = 0
        self.peak = 1.0
        self.halted = False
        # synthetic path with per-episode momentum (learnable edge, documented)
        # no lookahead: drift sampled at reset, revealed only via price moves
        if price_path is None:
            drift = float(self.rng.normal(self.cfg.drift_mu, self.cfg.drift_vol))
            drift = float(max(min(drift, 0.008), -0.002))
            rets = self.rng.normal(drift, self.cfg.base_vol, self.cfg.max_steps)
            self.path = 1.0 * np.cumprod(1 + rets)
            self.ep_drift = drift
        else:
            self.path = np.asarray(price_path, dtype=float)
            self.ep_drift = 0.0
        self.max_steps = len(self.path)
        self.equity = 1.0
        return self._obs()

    def _apply_latency(self, ref_price):
        # conservative: shift execution against trader by slippage + latency drift
        slip = self.cfg.slippage_bps / 10_000.0
        return ref_price * (1 + slip)

    def step(self, action: int):
        assert action in (0, 1, 2)
        done = False
        reward = 0.0
        ref = float(self.path[min(self.step_i, len(self.path) - 1)])
        # risk: kill switch on drawdown
        dd = (self.peak - self.equity) / self.peak * 100 if self.peak > 0 else 0
        if dd >= self.cfg.kill_drawdown_pct:
            self.halted = True
        if self.halted:
            action = 0
        prev_eq = self.equity
        if action == 1 and self.cash > 1e-6:  # buy with capped size
            spend = min(self.cash, self.cfg.max_position_sol)
            # convert SOL -> lamports input, exact-in formula on reserves
            x_lam = int(spend * 1_000_000_000)
            # scale reserves to current ref price move (keeps sim consistent)
            scale = ref / self.p0 if self.p0 else 1.0
            q = int(self.q_eff * scale)
            tok_raw = predict_buy_exact_in(self.b_res, q, x_lam)
            tok = tok_raw / 1e6
            fee = self.cfg.fee_lamports(x_lam, "buy") / 1e9 + self.cfg.tip_lamports / 1e9
            exec_p = self._apply_latency(ref)
            # tokens credited at exec price conservatively
            tok = min(tok, spend / exec_p) if exec_p > 0 else 0
            self.cash -= (spend + fee)
            self.cash = max(self.cash, 0.0)
            self.tokens += tok
            self.max_tokens = max(self.max_tokens, self.tokens)
            # pool moves
            self.q_eff = q + x_lam + int(x_lam * self.cfg.lp_bps / 10_000)
            self.b_res -= tok_raw
        elif action == 2 and self.tokens > 1e-9:
            t_raw = int(self.tokens * 1e6)
            scale = ref / self.p0 if self.p0 else 1.0
            q = int(self.q_eff * scale)
            gross_lam = predict_sell_gross(q, self.b_res, t_raw)
            fee = self.cfg.fee_lamports(gross_lam, "sell") / 1e9 + self.cfg.tip_lamports / 1e9
            proceeds = gross_lam / 1e9 - fee
            exec_p = ref * (1 - self.cfg.slippage_bps / 10_000.0)
            proceeds = min(proceeds, self.tokens * exec_p)
            self.cash += max(proceeds, 0.0)
            self.q_eff = q - gross_lam + int(gross_lam * self.cfg.lp_bps / 10_000)
            self.b_res += t_raw
            self.tokens = 0.0
        # mark to market at ref (no lookahead: uses current step price only)
        self.equity = self.cash + self.tokens * ref
        self.peak = max(self.peak, self.equity)
        reward = float(np.log(max(self.equity, 1e-9) / max(prev_eq, 1e-9)))
        self.step_i += 1
        if self.step_i >= len(self.path):
            done = True
            # forced flat at end
            if self.tokens > 0:
                self.equity = self.cash + self.tokens * ref * 0.999
        return self._obs(), reward, done, {"equity": self.equity, "halted": self.halted}
