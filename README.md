# RL Memecoin Bot — selective-v3 (G1 PASS)

Momentum on PumpAPI replay, PumpSwap only. Enter at bar 10 if `ret10>=5%`, `buy_ratio>=60%`, `dip>=-3%`, `liq>=30 SOL`. Exits: TP 60%, SL 12%, trail 15%. Costs: 1.3% round-trip + swqos, 1-bar worst-fill latency, 2% fail rate. Size 0.05 SOL.

## Run
`python3 -m tests.test_bot` · `python3 -m bot.run --paper` · `python3 eval_oos_fresh.py <files>`
Daemon: `oxmgr apply ./oxfile.toml`

## Result
v3 G1 PASS on 8 fresh hours (Oct 03-05 13/14/15 UTC, 600k lines/file): mean +0.00180/path, lower95 +0.00065, 8/8 positive. See `docs/strategy-v3-report.md`, `configs/selective-v3.json`, `eval/results_v5.json`.
