"""Tally a shadow-run log into close counts / PnL by reason.

Usage: .venv/bin/python -m eval.shadow_report data/shadow_run76.log

Reads only the log (no state files): evidence must be reproducible from
what the run actually printed, including its final summary line.
"""
from __future__ import annotations
import re
import sys

SELL = re.compile(
    r"SHADOW SELL (\S+) (\S+) pnl=([+-][\d.]+) bal=([\d.]+) halted=(\S*)")
BUY = re.compile(r"SHADOW BUY (\S+) epx=(\S+) vpx=(\S+)")
DONE = re.compile(r"shadow done bal=([\d.]+) W=(\d+) L=(\d+) crashed=(\S+)")


def parse(text: str) -> dict:
    out = {
        "buys": 0, "closes": {}, "wins": 0, "losses": 0, "pnl": 0.0,
        "final": None, "entry_skip": {}, "exit_noquote": {},
        "ghost": 0, "entry_sign_failed": 0, "rug_close": 0,
        "sweep_noquote": 0, "throttled": 0, "crashed": None, "done": False,
        "sp_pass": 0, "sp_block": 0, "sp_dump": 0, "sp_marker": 0,
    }
    for ln in text.splitlines():
        if "sp-pass" in ln:
            out["sp_pass"] += 1
            continue
        if "sp-block" in ln:
            out["sp_block"] += 1
            continue
        if "sp-dump" in ln:
            out["sp_dump"] += 1
            continue
        if "sp-marker" in ln:
            out["sp_marker"] += 1
            continue
        m = SELL.search(ln)
        if m:
            why, pnl = m.group(2), float(m.group(3))
            c = out["closes"].setdefault(why, {"n": 0, "pnl": 0.0})
            c["n"] += 1
            c["pnl"] += pnl
            out["pnl"] += pnl
            out["wins" if pnl > 0 else "losses"] += 1
            continue
        if BUY.search(ln):
            out["buys"] += 1
            continue
        if "entry no-quote" in ln:
            r = ln.split(": ", 1)[-1][:40]
            out["entry_skip"][r] = out["entry_skip"].get(r, 0) + 1
            continue
        if "exit no-quote" in ln:
            r = ln.split(": ", 1)[-1][:40]
            out["exit_noquote"][r] = out["exit_noquote"].get(r, 0) + 1
            continue
        if "entry ghost" in ln:
            out["ghost"] += 1
        elif "entry sign failed" in ln:
            out["entry_sign_failed"] += 1
        elif "rug-close" in ln:
            out["rug_close"] += 1
        elif "sweep no-quote" in ln:
            out["sweep_noquote"] += 1
        elif "throttled" in ln:
            out["throttled"] += 1
        m = DONE.search(ln)
        if m:
            out["done"] = True
            out["final"] = {"bal": float(m.group(1)),
                            "W": int(m.group(2)), "L": int(m.group(3)),
                            "crashed": m.group(4)}
    return out


def report(text: str) -> str:
    p = parse(text)
    lines = [f"buys={p['buys']} closes={sum(c['n'] for c in p['closes'].values())} "
             f"W={p['wins']} L={p['losses']} pnl={p['pnl']:+.5f}"]
    for why, c in sorted(p["closes"].items()):
        lines.append(f"  {why}: n={c['n']} pnl={c['pnl']:+.5f}")
    if p["buys"] > sum(c["n"] for c in p["closes"].values()):
        lines.append(f"  OPEN AT END: "
                     f"{p['buys'] - sum(c['n'] for c in p['closes'].values())}")
    lines.append(f"entry: ghost={p['ghost']} sign_failed="
                 f"{p['entry_sign_failed']} noquote="
                 f"{sum(p['entry_skip'].values())}")
    for r, n in sorted(p["entry_skip"].items(), key=lambda kv: -kv[1])[:3]:
        lines.append(f"  noquote {n}x: {r}")
    lines.append(f"exit no-quote={sum(p['exit_noquote'].values())} "
                 f"sweep no-quote={p['sweep_noquote']} rug-close={p['rug_close']}")
    lines.append(f"solpump: passed={p['sp_pass']} blocked={p['sp_block']} "
                 f"dump_flags={p['sp_dump']} markers={p['sp_marker']}")
    for r, n in sorted(p["exit_noquote"].items(), key=lambda kv: -kv[1])[:3]:
        lines.append(f"  exit {n}x: {r}")
    if p["final"]:
        f = p["final"]
        lines.append(f"final: bal={f['bal']:.4f} W={f['W']} L={f['L']} "
                     f"crashed={f['crashed']}")
    else:
        lines.append("NO FINAL SUMMARY LINE (run killed or wrapper lost)")
    return "\n".join(lines)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "data/shadow_run.log"
    with open(path) as fh:
        print(report(fh.read()))


if __name__ == "__main__":
    main()
