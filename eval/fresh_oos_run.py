"""Fresh OOS run: frozen config on freshly downloaded hours (no tuning).

Usage: .venv/bin/python -m eval.fresh_oos_run FILE [FILE...]
OOS_MAX_LINES caps lines per file (RAM-lean VPS); the cap is recorded in
the output for honesty. A file that hits MemoryError is skipped, the
others still count.
"""
from __future__ import annotations
import json
import os
import sys

from eval_oos_fresh import eval_file
from eval.gate import gate_g1

MAX_LINES = int(os.environ.get("OOS_MAX_LINES", "300000"))


def main(files):
    by_day = {}
    scanned = {}
    skipped = []
    for f in files:
        try:
            paths, n, a = eval_file(f, max_lines=MAX_LINES)
        except MemoryError:
            skipped.append(f)
            print(f"{f}: SKIPPED (MemoryError at {MAX_LINES} lines)",
                  flush=True)
            continue
        name = f.split("/")[-1].replace(".jsonl.zst", "")
        by_day[name] = [float(x) for x in a]
        scanned[name] = n
        del paths
        t = a[a != 0]
        print(f"{name}: scanned={n} npaths={len(a)} tr={int((a != 0).sum())} "
              f"mean={a.mean():+.5f} "
              f"mean_tr={(t.mean() if len(t) else 0):+.4f} "
              f"win={(float((t > 0).mean()) if len(t) else 0):.2f}",
              flush=True)
    g = gate_g1(by_day)
    out = {"gate": g, "per_day": by_day, "scanned": scanned,
           "max_lines": MAX_LINES, "files": files, "skipped": skipped}
    path = f"eval/results_oos_oct17_{MAX_LINES}.json"
    with open(path, "w") as fh:
        json.dump(out, fh)
    print(f"OOS-G1: mean={g['mean']:+.5f} lb={g['lower95']:+.5f} "
          f"pass={g['pass']} -> {path}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])

