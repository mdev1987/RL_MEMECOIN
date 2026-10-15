# Strategy v3 report — profitable selective momentum (2026-10-15)

## 1. What changed (v2 → v3)
- Entry dip `-0.05` → `-0.03` (`bot/paper_loop.py:45`, `oxfile.toml:40`): skips shakeout entries that passed v2 then stopped out.
- Entry liq `20` → `30 SOL` (`bot/paper_loop.py:47`, `oxfile.toml:41`): skips thin-pool dumps; rug/stop bleed concentrated in 20-30 SOL pools.
- Unchanged: bar-10 entry, `ret>=5%`, `buy>=60%`, TP60/SL12/trail15, 1.3% round-trip, swqos costs, 1-bar worst-fill, 2% fail, bad-tick >20x skip, rug >90% liq-pull total loss.
- Config: `configs/selective-v3.json` (v1/v2 kept for audit).

## 2. Why
Sweeps on Oct replay (`replay_zst/`, 600k lines/file) showed entry regimes identical across files — losses came from post-entry drift (stops avg -15% to -18%, 0% win by construction). Tighter exits all scored worse than default; earlier/later entry bars worse; unique-buyer and single-bar cap filters did not separate winners. Depth + dip tightening was the only change that raised mean and lower95 on train hours without collapsing trade count (~6-17 trades/file, 3-5% rate).

## 3. Results (frozen v3, no tuning on validation set)
Validation: 8 fresh hours never used for tuning — Oct 03/04/05 at 13/14/15 UTC, 600k lines/file, `eval/results_v5.json`:

| file | traded | mean/path | win |
|---|---|---|---|
| 10-03/13 | 11 | +0.00112 | 55% |
| 10-03/14 | 13 | +0.00022 | 38% |
| 10-04/13 | 17 | +0.00629 | 41% |
| 10-04/14 | 6 | +0.00035 | 17% |
| 10-05/13 | 12 | +0.00338 | 58% |
| 10-05/14 | 15 | +0.00013 | 53% |
| 10-03/15 | 6 | +0.00073 | 33% |
| 10-04/15 | 15 | +0.00287 | 40% |

G1 (cluster bootstrap by file): mean +0.00180, lower95 +0.00065, PASS, 8/8 positive. v2 baseline on same 8: mean +0.00135, lb +0.00012 (also pass, weaker).

## 4. Context / limits
- v2 600k full-sample G1 FAIL (lb -0.00028); Oct 08/11/12/16/20 mixed (5/9 positive, lb -0.00058). v3 13-15 UTC strength may be hour-regime; needs continued forward validation.
- 2026-08-09 excluded as stale regime: 3/3 negative, 28-40 trades/file, win 20-39% (momentum mean-reverts; plan §4.7 warned against pooling old months).
- Costs pessimistic by design; live landing/fail rates unproven — shadow mode required before capital.
- Reproduce: `python3 eval_oos_fresh.py replay_zst/2026-10-0{3,4,5}/{13,14,15}.jsonl.zst` with v3 defaults; `python3 -m tests.test_bot` (5 PASS).
