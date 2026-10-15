# Problem statement (Phase 0, frozen 2026-10-11)
Decision: newly launched classic SOL-quoted token, point-in-time info only —
buy fixed 0.05 SOL now or skip; exit by stop/target/trailing rule (v1, entry-only learning).
Universe: classic only (mayhem excluded; Step 12 regimes differ).
Costs: 0.05 SOL size; priority fee + Jito tip + rent per trade; failed tx pays fee only;
latency sampled, never execute at observed price. Account: 1 SOL, max 3 concurrent,
0.1 SOL fee buffer, daily stop 0.10, total stop 0.30, dedicated wallet, key in env only.
Objective: mean net SOL per trade; tail-aware CVaR reported. Success = Gate G1:
lower 95% cluster-bootstrap (by day) bound on mean net/trade > 0 at 0.05 SOL,
pessimistic costs, walk-forward, stable per-day. No graduation/rug labels in features/reward.
