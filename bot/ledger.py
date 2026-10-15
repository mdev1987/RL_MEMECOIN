"""Forward-validation decision ledger: one JSON line per paper decision.

Appended by the paper loop on every close/fee/rug. The weekly review reads
this file (not the text logs) to track out-of-sample paper PnL.
"""
from __future__ import annotations

import json
import time


def row(ts=None, file="", mint="", reason="", r_net=0.0, pnl_sol=0.0,
        balance_after=0.0, wins=0, losses=0) -> dict:
    return {
        "ts": ts if ts is not None else time.time(),
        "file": file, "mint": mint, "reason": reason,
        "r_net": round(float(r_net), 6), "pnl_sol": round(float(pnl_sol), 6),
        "balance_after": round(float(balance_after), 6),
        "wins": wins, "losses": losses,
    }


def append(path, entry: dict) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")
