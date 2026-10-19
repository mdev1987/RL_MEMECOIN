"""solpump.io full-surface report for one mint (read-only).

Usage:
  .venv/bin/python scripts/solpump_report.py <mint-or-prefix> [--json]

Covers every confirmed endpoint so a postmortem never needs hand-written
curl: token info, pairs, safety, candles, swaps tape summary, chart
markers, dev tokens, holders, calls, top traders, fee estimates, scanner
search (also resolves an 8-char prefix), trenches and the watchlist
ranking. The shadow loop uses the same client (bot/solpump.py) for its
live data layer.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot import solpump as SP  # noqa: E402
from bot import sp_guards as G  # noqa: E402


def resolve(mint: str) -> str:
    if len(mint) >= 32:
        return mint
    d = SP.scanner_search(f"SOL:{mint}")
    toks = (d or {}).get("tokens") or []
    if toks:
        return toks[0].get("tokenAddress") or mint
    return mint


def _cut(v, n=380):
    s = json.dumps(v, default=str)
    return s if len(s) <= n else s[:n] + "…"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mint")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    mint = resolve(a.mint)
    now = int(time.time())
    rep: dict = {"mint": mint, "generated_s": now}

    rep["token"] = SP.token_info(mint)
    rep["pairs"] = SP.pairs(mint)
    rep["safety"] = SP.safety(mint)
    rep["candles_1s_mcap"] = SP.candles(mint, "1s", "marketCap", 10)
    tape = SP.swaps_since(mint, now - 300, max_pages=3)
    rep["tape_5m"] = G.flow_features(tape, time.time())
    rep["chart_markers_24h"] = SP.chart_markers(mint, now - 86400, now, 10)
    rep["dev_tokens"] = SP.dev_tokens(mint)
    rep["holders"] = SP.holders(mint)
    rep["calls"] = SP.calls(mint)
    rep["top_traders"] = SP.top_traders(mint)
    rep["fee_estimate"] = {t: SP.fee_estimate("SOL", t)
                           for t in ("LOW", "MEDIUM", "HIGH")}
    rep["scanner_search"] = SP.scanner_search(f"SOL:{mint}")
    rep["fee_by_tier"] = rep["fee_estimate"]

    if a.json:
        print(json.dumps(rep, indent=1, default=str))
        return

    print(f"== solpump report {mint}  ({time.strftime('%H:%M:%S')})")
    for key in ("token", "pairs", "safety", "candles_1s_mcap",
                "chart_markers_24h", "dev_tokens", "holders", "calls",
                "top_traders", "fee_estimate", "scanner_search"):
        print(f"\n-- {key}\n{_cut(rep[key])}")
    f = rep["tape_5m"]
    print(f"\n-- tape 5m flow n={f['n']} buys={f['n_buys']} "
          f"sells={f['n_sells']} buy={f['sol_buys']} sell={f['sol_sells']} "
          f"buyers={f['buyers']} s1sell={f.get('s1_sol_sells')} "
          f"s3net={f.get('s3_net')}")
    print("   entry guard:", G.entry_flow_guard(f))
    print("   safety guard:", G.safety_guard(rep["safety"]))
    print("   dev guard:", G.dev_guard(rep["dev_tokens"]))


if __name__ == "__main__":
    main()
