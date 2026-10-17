"""Merge per-run fresh OOS result files into one cluster-bootstrap gate.

Usage: python -m eval.merge_oos_results OUT.json IN1.json IN2.json ...

Per-day (per-cluster) value lists are pooled; keys that collide across
inputs get a suffix from the source file tag, so clusters stay distinct.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from eval.gate import gate_g1


def main(out, files):
    per_day = {}
    components = []
    for f in files:
        d = json.loads(Path(f).read_text())
        tag = Path(f).stem.replace("results_oos_", "").replace("_1200000", "")
        components.append({"file": f, "tag": tag, "gate": d.get("gate")})
        for k, v in d["per_day"].items():
            key = k if k not in per_day else f"{k}_{tag}"
            per_day[key] = v
    g = gate_g1(per_day)
    tr = sum(1 for lst in per_day.values() for v in lst if v)
    wins = sum(1 for lst in per_day.values() for v in lst if v > 0)
    res = {
        "gate": g,
        "per_day": per_day,
        "clusters": len(per_day),
        "trades": tr,
        "wins": wins,
        "components": components,
        "note": "fresh OOS, frozen config, merged hour clusters",
    }
    Path(out).write_text(json.dumps(res, indent=1))
    print(f"merged {len(per_day)} clusters, {tr} trades, {wins} wins: "
          f"mean={g['mean']:+.5f} lb={g['lower95']:+.5f} pass={g['pass']} "
          f"-> {out}")
    return res


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
