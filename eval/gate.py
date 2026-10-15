"""Walk-forward eval, cluster bootstrap (by day), cost sweeps, G1 gate."""
from __future__ import annotations
import numpy as np


def cluster_bootstrap_lb(values_by_day, n_boot=2000, seed=0):
    """Lower 95% bound on overall mean, resampling days (clusters)."""
    days = list(values_by_day.keys())
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n_boot):
        pick = rng.choice(days, size=len(days), replace=True)
        vals = [v for d in pick for v in values_by_day[d]]
        means.append(float(np.mean(vals)) if vals else 0.0)
    return float(np.percentile(means, 2.5)), float(np.mean(means))


def cost_sweep(base_ret_fn, fee_mults=(1.0, 2.0), lat_mults=(1.0, 2.0)):
    out = {}
    for f in fee_mults:
        for l in lat_mults:
            out[(f, l)] = base_ret_fn(fee_mult=f, lat_mult=l)
    return out


def gate_g1(values_by_day):
    lb, mean = cluster_bootstrap_lb(values_by_day)
    return {"mean": mean, "lower95": lb, "pass": lb > 0}
