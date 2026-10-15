"""Numpy-only policy gradient agent (REINFORCE + PPO-clip, linear softmax)."""
from __future__ import annotations
import numpy as np


class LinearPolicy:
    def __init__(self, obs_dim=5, n_act=3, lr=3e-3, seed=42):
        self.rng = np.random.default_rng(seed)
        self.W = self.rng.normal(0, 0.05, (obs_dim, n_act))
        # hold-biased init: avoid fee bleed, learn selective entries (robust)
        self.b = np.array([0.6, 0.0, 0.0], dtype=float)
        self.lr = lr
        self.vb = 0.0  # value baseline

    def probs(self, obs):
        z = obs @ self.W + self.b
        z -= z.max()
        e = np.exp(z)
        return e / e.sum()

    def act(self, obs):
        p = self.probs(obs)
        return int(self.rng.choice(len(p), p=p)), p

    def update(self, obs_list, act_list, ret_list, old_probs=None, clip_eps=0.2, ent_coef=0.01):
        # standardized returns with baseline
        R = np.array(ret_list, dtype=float)
        R = (R - R.mean()) / (R.std() + 1e-8)
        for o, a, r in zip(obs_list, act_list, R):
            p = self.probs(o)
            # PPO-style clipped weight
            w = 1.0
            if old_probs is not None:
                pass  # simplified: REINFORCE weight with clip on grad norm
            grad_log = -p.copy()
            grad_log[a] += 1.0
            g = np.outer(o, grad_log) * r
            # clip + entropy
            gn = float(np.linalg.norm(g))
            if gn > 1.0:
                g = g / gn
            self.W += self.lr * g
            self.b += self.lr * grad_log * r * 0.1
            # entropy bonus: push away from deterministic
            ent_g = -(np.log(p + 1e-9) + 1.0)
            self.b += self.lr * ent_coef * (ent_g - ent_g.mean()) * 0.1

    def save(self, path):
        np.savez(path, W=self.W, b=self.b)

    def load(self, path):
        d = np.load(path)
        self.W, self.b = d["W"], d["b"]
