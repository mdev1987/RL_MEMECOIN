# Assumptions log
- 0.05 SOL/trade; non-reactive replay valid at this size (impact << reserves).
- Priority fee + Jito tip + rent modeled as flat costs; failed tx pays fee only.
- Jito bundles atomic: same-token events within 3ms grouped (bot/data.group_bundles).
- Recorded archive prices are pre-trade (Steps 167-168); backtest uses post-state where audited, slot-aggregated per pool-block otherwise.
- buyback = floor(protocol/2), cashback = 0 in fixtures; holder_rewards informational.
- October 2 test day burned (over-inspected); holdout = unseen mints + hour13.
