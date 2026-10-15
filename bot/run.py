"""Product CLI: paper trade replay with risk limits. Usage: .venv/bin/python -m bot.run [--hour PATH] [--paper]"""
from __future__ import annotations
import argparse
from pathlib import Path
from .replay_eval import load_paths, split_paths, evaluate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hour", default=str(Path(__file__).resolve().parents[1] / "data" / "12.jsonl.zst"))
    ap.add_argument("--max-lines", type=int, default=600000)
    ap.add_argument("--paper", action="store_true", help="dry-run, no orders sent")
    a = ap.parse_args()
    paths, n = load_paths(a.hour, max_lines=a.max_lines)
    tr, te = split_paths(paths)
    m_tr = evaluate(tr)
    m_te = evaluate(te)
    print(f"scanned={n} train={len(tr)} test={len(te)} paper={a.paper}")
    print("TRAIN", {k: v for k, v in m_tr.items()})
    print("TEST ", {k: v for k, v in m_te.items()})
    print("STRAT v2: ret>=5% buy>=60% dip>=-5% liq>=20 TP60 SL12 trail15 bad-tick>20x")
    print("RISK: max_position 0.5 SOL, kill-DD 15%, liquidity>=20 SOL, pool pump/pump-amm only")


if __name__ == "__main__":
    main()
