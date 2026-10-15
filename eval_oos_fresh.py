"""Frozen v2 out-of-sample validation on fresh replay days. NO TUNING here:
config locked to selective-v2 (entry 0.05/0.60/-0.05, TP60 SL12 trail15,
swqos realistic costs). Fresh files must NEVER enter any threshold search.
Usage: .venv/bin/python eval_oos_fresh.py data/oct12_11.jsonl.zst [more...]
"""
from __future__ import annotations
import sys
import numpy as np
from bot.replay_eval import load_paths
from bot.strategy import run_selective, COST_PATHS
from eval.gate import gate_g1

TH = (0.05, 0.60, -0.05)
C = COST_PATHS["swqos"]
KW = dict(take_profit=0.6, stop_loss=0.12, trailing=0.15, size_sol=0.05,
          latency_bars=1, fail_rate=0.02, extra_bps=C["extra_bps"],
          fixed_cost_sol=C["fixed_sol"], entry_thresh=TH)


def eval_file(path, max_lines=600000):
    paths, n = load_paths(path, max_lines=max_lines)
    vals = []
    for d in paths:
        ls = d.get("liq_series") or [d.get("liq", 0.0)] * 11
        if len(ls) >= 11 and min(ls[:11]) < 20.0:
            vals.append(0.0)
            continue
        r, why, _ = run_selective(d["prices"], d["actions"], fail_seed=d.get("mint", ""),
                                  liq_series=d.get("liq_series"), **KW)
        vals.append(r)
    return paths, n, np.array(vals)


def main(files):
    by_day = {}
    for f in files:
        _, n, a = eval_file(f)
        t = a[a != 0]
        by_day[f] = a
        print(f"{f}: scanned={n} npaths={len(a)} tr={int((a != 0).sum())} "
              f"mean={a.mean():+.5f} mean_tr={(t.mean() if len(t) else 0):+.4f} "
              f"win={(float((t > 0).mean()) if len(t) else 0):.2f} max={a.max():+.3f}",
              flush=True)
    if len(by_day) >= 2:
        g = gate_g1({k.split("/")[-1]: list(v) for k, v in by_day.items()})
        print(f"OOS-G1: mean={g['mean']:+.5f} lb={g['lower95']:+.5f} pass={g['pass']}",
              flush=True)
    else:
        a = list(by_day.values())[0]
        t = a[a != 0] if len(a) else a
        print(f"single-file: no cluster gate possible; mean_tr={(t.mean() if len(t) else 0):+.4f} "
              f"win={(float((t > 0).mean()) if len(t) else 0):.2f} ntr={len(t)}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: eval_oos_fresh.py FILE [FILE...]")
    main(sys.argv[1:])
