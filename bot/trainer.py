"""Train + backtest runners with metrics."""
from __future__ import annotations
import numpy as np
from .config import BotConfig
from .env import PumpSwapEnv
from .policy import LinearPolicy


def train(cfg: BotConfig | None = None, verbose=True):
    cfg = cfg or BotConfig()
    env = PumpSwapEnv(cfg)
    pol = LinearPolicy(lr=cfg.lr, seed=cfg.seed)
    rets = []
    for ep in range(cfg.episodes):
        obs = env.reset()
        ob, ac, rw, oldp = [], [], [], []
        done = False
        while not done:
            a, p = pol.act(obs)
            ob.append(obs)
            ac.append(a)
            oldp.append(p[a])
            obs, r, done, _ = env.step(a)
            rw.append(r)
        # discounted returns
        G, disc = [], 0.0
        for r in reversed(rw):
            disc = r + cfg.gamma * disc
            G.append(disc)
        G = list(reversed(G))
        pol.update(ob, ac, G, clip_eps=cfg.clip_eps, ent_coef=cfg.entropy_coef)
        ep_ret = float(np.exp(sum(rw)) - 1)
        rets.append(ep_ret)
        if verbose and (ep + 1) % 100 == 0:
            print(f"ep {ep+1}/{cfg.episodes} ret {ep_ret:+.3%} avg50 {np.mean(rets[-50:]):+.3%}")
    pol.save(cfg.checkpoint_path)
    return pol, rets


def backtest(pol: LinearPolicy, cfg: BotConfig | None = None, n_ep=100, seed=123):
    cfg = cfg or BotConfig()
    eq_curve, wins, dds = [], 0, []
    for i in range(n_ep):
        env = PumpSwapEnv(cfg)
        env.rng = np.random.default_rng(seed + i)
        obs = env.reset()
        done = False
        peak = 1.0
        while not done:
            p = pol.probs(obs)
            a = int(np.argmax(p))
            obs, _, done, info = env.step(a)
            peak = max(peak, info["equity"])
        eq_curve.append(env.equity)
        if env.equity > 1.0:
            wins += 1
        dds.append((peak - env.equity) / peak * 100)
    rets = np.array(eq_curve) - 1.0
    sharpe = float(rets.mean() / (rets.std() + 1e-9) * (252 ** 0.5)) if len(rets) > 1 else 0.0
    return {"mean_ret": float(rets.mean()), "win_rate": wins / n_ep,
            "max_dd": float(np.max(dds)), "sharpe": sharpe, "n": n_ep}
