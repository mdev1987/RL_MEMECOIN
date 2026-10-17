# RL Memecoin Bot — Product Ready (v2 selective, G1 pass)

Validated PumpSwap exec: `effective=raw+virtual`, `buy_exact_in: B*(x-1)//(Q+V+x-1)`,
`buy exact-out: ceil(R*y/(B-y))`, `sell: gross→net of lp+protocol+creator`.

## Strategy (v2, validated 2026-10-12)
Selective momentum on PumpAPI replay: enter at bar 10 only if
`ret10>=5%`, `buy_ratio>=60%`, `dip>=-5%`, `liq>=20 SOL`, pools `pump/pump-amm` only.
Exits: TP 60%, SL 12%, trail 15%, 1.3% round-trip costs. ~2-10% trade rate.
Config: `configs/selective-v2.json` (v1 kept in `selective-v1.json` for audit).

Guards: rug total-loss on >90% liq pull; **bad-tick skip** on >20x single-bar
jumps (regression: 2026-10-12 +26154% event is now `bad-tick`, never booked).

## Robust / reliable
- No lookahead (entry uses bars ≤10 only); train/test split by mint hash; time split; 7-file cluster bootstrap.
- Rotation: per-file visit counters guarantee full coverage (`len/gcd(len,25)` period).
  Old global stride visited only 4 offsets for 140-row files and permanently missed tradeables — fixed.
- Observability: every cycle logs `skip={liq-fail, wallet:duplicate, strategy:filtered, ...}`.
- Risk: 0.5 SOL cap, 15% kill-DD, daily-loss halt, rate limit, paper `--paper` default.
- Deterministic seeds; 29 unit tests (`python -m tests.test_bot` runner).
- Run: `.venv/bin/python -m tests.test_bot`, `.venv/bin/python -m bot.run --paper`.
- Daemon: `oxmgr apply ./oxfile.toml`, logs `oxmgr logs meme-paper --lines 200`.

## Verified
- v2 swqos (200k lines/file): G1 mean +0.00377 / lower95 +0.00071 PASS, 31 trades, mean_traded +11.8%, win 45%.
- v2 swqos (600k lines/file, full sample): G1 FAIL on both bases — per-path
  mean +0.00224 / lb -0.00028; per-trade mean +0.0637 (+0.0031 SOL/trade, 86 trades)
  / lb -0.00780. 5/7 files positive; `12` + `oct11_11` negative. Entry regimes
  identical across files, so weakness is post-entry drift (regime-dependent).
  Stricter entry (ret 6%/8%) fails worse. See `eval/results_v2.json`,
  `eval/results_v3.json`, `eval/results_v4.json`. No further in-sample tuning
  (overfit); needs fresh out-of-sample data.
- v2 jupiter (+50bps/side, 200k): G1 PASS (lb +0.00037). v2 jito (0.001 SOL tip): FAIL — tip floor not viable at 0.05 size, use swqos.
- Walk-forward: mint-split train +0.00067 / test +0.00673; time-split train +0.00264 / test +0.00530 (test ≥ train, no overfit).
- Paper forward (recycled replay, realistic costs): 1.0316 → ~1.20 (+16%+) since rotation fix; weak evidence (same files).
- **Out-of-sample (frozen v2, never tuned on): 10/12 + 10/13 fresh days from
  replay server — OOS-G1 mean +0.00366 / lower95 +0.00121 PASS, 27 trades,
  win 59%, mean_traded +8%.** Config locked before download; script
  (`eval_oos_fresh.py`) has no tuning knobs. Only 2 clusters, so thin —
  but genuine OOS. See `eval/results_oos.json`.
- Costs: pessimistic fills (worst-of-next-bar), 2% fail rate (fee only), venue costs per path.

## Live trading (real money — staged rollout required)
Paper and live share signals; only the fill path differs (`bot/live.py`:
`/order` → guards → local sign → `/execute` → RPC confirm).

Guards (fail-closed): `data/LIVE_KILL` file, `LIVE_MAX_SOL` cap (default
0.01 dust), price-impact cap (default 5%), min-out threshold, gasless refusal
(`signatureFeePayer == taker`), priority-fee cap, retryable/fatal error map.
Exits run on live Jupiter marks (TP/SL/trail/TIME/STALE), never replay marks.

Rollout (each stage needs a written pass before the next):
1. **Shadow**: `SHADOW=1` — full order + local sign, never executes.
   Requires a funded taker (empty wallet fails closed with code 1).
   Measure fill parity shadow-vs-paper for a week.
2. **Dust**: `LIVE_TRADING=1 LIVE_CONFIRM=YES python -m bot.live_loop --live`
   with `LIVE_SIZE_SOL=0.01`, separate `live_wallet.json`. Kill via
   `touch data/LIVE_KILL`. Risk: total loss of deployed size is assumed.
3. **Scale**: raise `LIVE_SIZE_SOL`/`LIVE_MAXOPEN` only on green dust +
   green shadow parity. Never exceed what a same-day -100% rug costs you.

Key lives in `.env.signer` (600, gitignored); paper daemons never load it.
`meme-live` is NOT registered in oxfile — start by hand, on purpose.

## Update 2026-10-17 — live-path hardening (from shadow-run evidence)

Shadow runs on the live stream (signed-never-sent) surfaced three exit-path
failures; all are now fixed and covered by tests (56 total):

- **Exits could not be built.** Jupiter returned routes without executable
  transactions (`router=metis/dflow code=1`) and the 1% default slippage was
  too tight. Sells now default to `LIVE_EXIT_SLIPPAGE_BPS=2500` and retry
  once at `LIVE_WIDE_RETRY_BPS=5000`; a persistent no-tx is classified as
  `NoQuote` (counted skip + cooldown), so a position can't wedge the loop.
- **Impact cap blocked exits.** `LIVE_MAX_IMPACT_PCT` (5%) applied to sells
  too; a stuck mint with −16% quote impact could never leave. Exits now use
  `LIVE_EXIT_MAX_IMPACT_PCT` (default 100 = no veto); the venue slippage cap
  still bounds execution. Entries keep the 5% cap, and the wide-slippage
  retry never applies to buys.
- **Ghost tape data.** One live print was mis-scaled 337x vs the venue
  quote and produced a fantasy +337x mark (previously booked as +491x on a
  rug). Now: (a) entries require a read-only preflight quote within 3x of
  the tape price (`jup.price_diverges`), in both shadow and live loops;
  (b) suspicious marks (>10x or <0.1x cost) are corroborated with a venue
  quote before they can move peak/PnL — venue value wins when it agrees,
  print is dropped when it doesn't.
- **Politeness:** `/order` calls are throttled (`JUP_MIN_INTERVAL_S=0.5`)
  and throttled responses never count as venue misses; paper cards now show
  real price impact (`priceImpact` field, not the deprecated `priceImpactPct`).

Safety defaults unchanged: shadow never executes; live requires
`LIVE_TRADING=1 LIVE_CONFIRM=YES`; `data/LIVE_KILL` stops everything.
