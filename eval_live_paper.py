"""Offline live-paper simulation over captured tapes with full series.

Reads tapes JSONL (needs --series captures), runs the frozen v2 strategy
(entry 0.05/0.60/-0.05, TP60 SL12 trail15, swqos costs, bad-tick guard)
on each tape's buy-price series, prints per-reason PnL. No tuning knobs.

Note: live tapes have buys only (no sells/liq series); exits run on the
buy tape with liq_series=None (rug guard off — conservative gap noted).
Usage: .venv/bin/python eval_live_paper.py data/live_tapes2.jsonl
"""
from __future__ import annotations
import json
import sys
import numpy as np
from bot.strategy import run_selective, COST_PATHS

C = COST_PATHS["swqos"]
KW = dict(take_profit=0.6, stop_loss=0.12, trailing=0.15, size_sol=0.05,
          latency_bars=1, fail_rate=0.0, extra_bps=C["extra_bps"],
          fixed_cost_sol=C["fixed_sol"], entry_thresh=(0.05, 0.60, -0.05),
          liq_series=None)


def main(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    with_series = [t for t in rows if t.get("prices")]
    print(f"tapes={len(rows)} with_series={len(with_series)}", flush=True)
    rets, reasons = [], {}
    for t in with_series:
        px = [float(p) for p in t["prices"]]
        acts = ["buy"] * len(px)
        r, why, _ = run_selective(px, acts, **KW)
        if r == 0.0:
            reasons[why] = reasons.get(why, 0) + 1
            continue
        rets.append(r)
        reasons[why] = reasons.get(why, 0) + 1
    rets = np.array(rets)
    print(f"reasons={reasons}", flush=True)
    if len(rets):
        print(f"traded={len(rets)} win={float((rets > 0).mean()):.2f} "
              f"mean_tr={rets.mean():+.4f} sum={rets.sum():+.4f} "
              f"pnl_sol={rets.sum() * 0.05:+.5f}", flush=True)
    else:
        print("no trades", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/live_tapes2.jsonl")
