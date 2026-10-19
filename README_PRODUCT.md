# RL Memecoin Bot — Product Ready (v3 selective, G1 pass)

Validated PumpSwap exec: `effective=raw+virtual`, `buy_exact_in: B*(x-1)//(Q+V+x-1)`,
`buy exact-out: ceil(R*y/(B-y))`, `sell: gross→net of lp+protocol+creator`.

## Strategy (v3, frozen 2026-10-17)
Selective momentum on PumpAPI replay: enter at bar 10 only if
`ret10>=5%`, `buy_ratio>=60%`, `dip>=-3%`, `liq>=30 SOL`, pools `pump/pump-amm` only.
Exits: TP 60%, SL 12%, trailing 15%, TIME 1h, 1.3% round-trip costs. ~2-10% trade rate.
Config: `configs/selective-v3.json` (v1/v2 kept in `selective-v1.json` /
`selective-v2.json` for audit).

Guards: rug total-loss on >90% liq pull; **bad-tick skip** on >20x single-bar
jumps (regression: 2026-10-12 +26154% event is now `bad-tick`, never booked).

## Robust / reliable
- No lookahead (entry uses bars ≤10 only); train/test split by mint hash; time split; 7-file cluster bootstrap.
- Rotation: per-file visit counters guarantee full coverage (`len/gcd(len,25)` period).
  Old global stride visited only 4 offsets for 140-row files and permanently missed tradeables — fixed.
- Observability: every cycle logs `skip={liq-fail, wallet:duplicate, strategy:filtered, ...}`.
- Risk: 0.5 SOL cap, 15% kill-DD, daily-loss halt, rate limit, paper `--paper` default.
- Deterministic seeds; 71 unit tests (`python -m tests` runner).
- Run: `.venv/bin/python -m tests`, `.venv/bin/python -m bot.run --paper`.
- Daemon: `oxmgr apply ./oxfile.toml`, logs `oxmgr logs meme-paper --lines 200`.

## Verified
- **v3 frozen: fresh OOS Oct 14-17 (22 hour-clusters, 339 trades, 1.2M
  lines/hour): G1 mean +0.00090 / lower95 +0.00032 PASS; mixed recent
  hours (3 of the newest 7 negative) keep it honest. Evidence:
  `eval/results_oos_fresh22_1200000.json`.**
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
- Paper forward (recycled replay, realistic costs, `meme-paper` daemon):
  wallet 1.283889 reconciles exactly as 1.0 + the last 34 closes
  (sum +0.2839, W18/L16); the full ledger holds 213 closes +1.3117.
  Same files as in-sample, so this is a sanity check, not independent
  evidence.
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
   Measure fill parity shadow-vs-paper for a week. For exact loop parity
   (venue marks, cycle cadence, isolated `*_shadow.*` state):
   `SHADOW=1 LIVE_TRADING=1 LIVE_CONFIRM=YES python -m bot.live_loop --live`.
2. **Dust**: `LIVE_TRADING=1 LIVE_CONFIRM=YES python -m bot.live_loop --live`
   with `LIVE_SIZE_SOL=0.01`, separate `live_wallet.json`. Kill via
   `touch data/LIVE_KILL`. Risk: total loss of deployed size is assumed.
3. **Scale**: raise `LIVE_SIZE_SOL`/`LIVE_MAXOPEN` only on green dust +
   green shadow parity. Never exceed what a same-day -100% rug costs you.

Key lives in `.env.signer` (600, gitignored); paper daemons never load it.
`meme-live` is NOT registered in oxfile — start by hand, on purpose.

## Reproducing the evidence

All replay/OOS commands run offline (no Jupiter key needed):

```
.venv/bin/python -m tests                                # 71 tests
curl -sSLo /tmp/h.jsonl.zst https://replay.pumpapi.io/2026/10/17/05.jsonl.zst
OOS_MAX_LINES=1200000 OOS_TAG=oct17_h05 \
  .venv/bin/python -m eval.fresh_oos_run /tmp/h.jsonl.zst
.venv/bin/python -m eval.merge_oos_results out.json eval/results_oos_fresh17_1200000.json ...
.venv/bin/python -m bot.shadow_loop --secs 4500          # live-stream shadow
.venv/bin/python -m eval.shadow_report data/shadow_runNN.log
# parity soak (isolated *_shadow.* state, replay key):
SHADOW=1 LIVE_TRADING=1 LIVE_CONFIRM=YES REPLAY_PATHS=... \
  timeout 2400 .venv/bin/python -m bot.live_loop --live
```

## Update 2026-10-17 — live-path hardening (from shadow-run evidence)

Shadow runs on the live stream (signed-never-sent) surfaced three exit-path
failures; all are now fixed and covered by tests (71 total; the full
finding log follows):

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
  Replay workloads (paper daemon, `SHADOW=1` parity runs) use
  `JUPITER_API_KEY_REPLAY` when set, keeping the primary key's rate budget
  for the live-stream shadow and real-money paths.

### run75 findings (same day) — two more, fixed

- **Exit starvation by our own throttle.** An exit whose 2500bps route had
  no executable tx retried at 5000bps milliseconds later, hit our own 0.5s
  politeness gap, and the caller read "throttled" (backoff 2s, no miss):
  147 logged in 63 minutes, zero closes, two positions wedged the whole run.
  Exits now bypass the politeness throttle (`get_order(critical=True)` for
  sells); the per-position cooldowns (2s/60s + miss counting + rug-give-up)
  bound the rate instead. Test: `test_exit_retry_never_throttled`.
- **Unbounded tape memory.** Tapes were marked `done` only when the entry
  gate could run; with `MAXOPEN` full for an hour no tape ever finished and
  print arrays grew without bound — the run process died at 06:52 with no
  traceback (OOM). Tapes now close after the 11-print window (`push_print`),
  and the entry gate fires exactly on the window-completing print, so a
  slot freeing up never buys a stale setup. Test: `test_shadow_tape_bounded`.
- Entry `NoQuote` skips are logged (were silent); a crash now logs a
  traceback and a final balance summary line.
- **Key death is not a rug.** A 401/403/429/5xx or network error never
  counts toward rug-give-up (only venue-level "no route / no executable
  tx" does), so a dead API key can never blind-rug-close the book. A
  dead primary key degrades to `JUPITER_API_KEY_REPLAY` on 401 with a
  one-time Telegram alert (2026-10-17: the primary key was revoked
  mid-session; before this, exits would have missed-into-rug-close).
  Tests: `test_venue_miss_classification`, `test_get_order_key_failover`,
  `test_jup_quote_key_failover`. 64 tests total.

### run76b (same day) — false rugs in shadow, and why shadow exits are quote-fills

- **Sells cannot be built in shadow.** The wallet signs buys but never
  broadcasts, so it never holds the tokens: every sell build fails with
  `Insufficient funds` (masked as "no executable tx, router=metis"), and
  5 such misses booked two positions at -100% while the venue quoted
  85-105% of their cost. Shadow exits are now **quote-fills**: the exit
  value comes from the read-only `/order` quote (the same estimator paper
  uses) and the position closes at that value. The token-dependent build
  path is exercised in dust with real fills. Test: `test_shadow_quote_fill_helpers`.
- Failure reasons are classified: only venue no-route (`HTTP 400 failed
  to get quotes`, `order no quote`) counts toward rug-give-up; auth/quota/
  network ("ours") back off and never zero a position.
- Live exits additionally retry once at 98% size when the venue reports
  `Insufficient funds` (real balance vs quoted amount), and live positions
  now use the executed buy's actual received tokens (`totalOutputAmount`)
  as `qty_base` instead of the quote. Test:
  `test_live_exit_insufficient_funds_shaves`.
- **Fresh OOS (frozen config, Oct 14-17 2026, 22 hour-clusters, 339 trades,
  1.2M lines/hour): mean +0.00090, lower95 +0.00032 → gate pass.**
  All seven Oct-17 hours (03:00-09:00) were downloaded after every
  parameter was frozen; individually they are mixed (+0.00170, +0.00051,
  +0.00135, +0.00214, -0.00136, -0.00044, -0.00108). The newest hours are
  weaker, so the fresh edge is smaller than in-sample — but still positive
  and significant. Evidence: `eval/results_oos_fresh22_1200000.json`.
  In-sample pooled-14 was +0.00196: the edge is smaller on fresh data but
  still positive and significant. Evidence: `eval/results_oos_fresh15_1200000.json`.

67 tests total.

### parity soak (same day) — live-loop findings

`SHADOW=1 live_loop` over a fresh replay hour found four live-path issues
before any real money moved:

- `Wallet(start=0.0)` crashed the loop on its first tradeable signal
  (`dd_stop / start` divide-by-zero). Start-unset ledgers now use the
  absolute `dd_stop` below the high-water mark.
  Test: `test_wallet_live_start0_no_crash`.
- Successful opens were never recorded, so `can_open`'s dedup and hourly
  rate limit never bound (the same mint was bought 4x in 40 minutes).
  `Wallet.apply_open` marks the mint seen and clocks the hour.
  Test: `test_wallet_apply_open_dedup_and_rate`.
- Routine pre-trade guard rejections (impact cap, gasless fee payer) were
  logged as "LIVE BUY FAILED" with a Telegram alert; they are counted
  skips now (`skip["live:guard"]`), like paper's `filtered`.
- Live exit PnL/ledger now uses the executed `totalOutputAmount` (real
  proceeds), falling back to the tape mark only in SHADOW parity runs.

### shadow run77 (same day, quote-fill exits) — first clean live round trips

75 min on the live pump.fun stream: 5 buys / 5 legitimate closes
(3 stop, 2 time), 0 rugs, 0 exit no-quotes, no fantasy marks, bounded
memory (80MB RSS vs run75's unbounded growth), clean final line. Net
-0.00319 SOL on 0.05 SOL deployed — a thin sample, mostly stop-losses;
the fresh replay OOS gate remains the profitability measure. The entry
filter vetoed 15 ghost tapes and 5 impact-guard candidates (fail-closed).
Evidence: `eval/shadow_run77_report.txt`.

### shadow run78/79 + parity soaks 2/3 (same day) — in-loop shadow exits

- Parity soak 2 booked a **false −100% rug**: the live loop's SHADOW sell
  build fails with "Insufficient funds" (the shadow wallet never holds
  tokens) and five of those counted as venue misses. Fixed: `insufficient
  funds` is our side (never a venue miss), and SHADOW exits close at the
  read-only quote via `shadow_exit_receipt` (shadow_loop semantics).
  Soak 3 (18 cycles): **0 rug-closes**, 0 errors, 1 buy, 3 counted guard
  skips. Tests: `test_venue_miss_insufficient_funds_is_ours`,
  `test_shadow_exit_receipt_uses_quote`.
- Shadow run78 was killed early by a host restart (1h09m, 5 closes,
  partial, net −0.0041). **Shadow run79 ran the full 90 min on the live
  stream: 8 buys / 7 closes (4 stale, 2 stop, 1 trail), 0 rugs, 0 exit
  failures, clean final line, net −0.00328 SOL on 0.07 SOL deployed.**
  Thin live samples (5-10 closes) swing on fat tails; the replay OOS gate
  remains the profitability measure.
  Evidence: `eval/shadow_run79_report.txt`,
  `eval/parity_soak3_report.txt`.

### realtime entry postmortem (same day) — shadow gated late windows

Tape reconstruction of all 23 live shadow entries (gate print located by
exact price match against the logged `epx`; ages from `create` events
where in range):

- **21 of 23 gates fired 3-3522 prints into the mint's life**, not at
  birth: the 5,000-tape table saturated (completed tapes lingered 30
  min), so prints of new mints were silently dropped and the "first 11
  prints" window became an arbitrary mid-life slice. Those slices are
  micro-bursts (span 1-60 s, +5..+65 %); buying their tops is why stops
  filled in 9-275 s. Ages at entry (lower bounds): most ≥ 1 h,
  `8Jef1ow6` 67 min, several ≥ 9 h.
- Case study `EmoRR2DM`: first 10 prints dropped; birth window ran
  **+3966 %**; the gate fired at a +9 % micro-spike 26 s after birth
  (its last print a sell) and stopped at −11.2 % in 9.3 s; price then
  recovered to +33.5 % above the entry within 5 min.
- Fix (correctness only; gate/exits/size frozen): `tape_should_start` —
  a tape starts only for mints whose `create` event we saw (verified on
  the live stream by probe: ~0.44 creates/s), **one tape per mint
  ever**; completed non-position tapes are popped immediately; creates
  TTL 1 h; taped-registry soft cap; cap-hit warning. Test:
  `test_shadow_tape_birth_anchor`.
- This reframes the earlier live samples: their P&L (−6.2 %/trade over
  17 closes) measured a mis-anchored variant, not the v3 early window.
  `data/shadow_run80_curve.tsv` holds the partial run80 baseline; the
  fresh 24 h birth-anchored shadow (run82, after the quote-asset filter
  below) is the realtime verdict now.

### quote-asset filter (run81 follow-up, same day)

run81 opened with 22 gate-passes and 0 trades in 45 min. Forensics on
the hour-14 public tape: pump now also launches pairs quoted in **USDC
or other meme tokens**, and live taped them all. Their tape prices are
in quote-asset units (BATMAN/USDC `4Ud6oKbe`: tape 4.7e-6 vs venue
4.6e-8 SOL ≈ SOL at 103 USD — self-consistent), the v3 liq filter is
SOL-denominated, and the SOL venue route cannot act on them. 8 of the
11 checked gate passes were such pairs — correctly ghost-skipped, but
they crowded out the real ones. Replay/OOS only ever admitted
quoteMint==SOL (`load_paths`); live now matches via `tradable_event`
(creates + prints). Test: `test_shadow_sol_quote_filter`.

The remaining 3 SOL-quoted gates were all blocked by the entry impact
cap (−6..−100 % quoted: Jupiter's first-seconds quote for a new pool is
its least reliable moment) — two of them then ran +365 % / +120 % after
the gate. The shadow run therefore enters with
`LIVE_MAX_IMPACT_PCT=100` and fills at the quoted price, logging every
gate (`SHADOW gate … vpx/impact/route`) so the realtime P&L stays
quote-honest and auditable; live/dust keep the 5 % default.

73 tests total.

Safety defaults unchanged: shadow never executes; live requires
`LIVE_TRADING=1 LIVE_CONFIRM=YES`; `data/LIVE_KILL` stops everything.

### run82 — 24 h realtime verdict (2026-10-18)

First clean 24 h realtime sample on the frozen v3 rule: birth-anchored,
SOL-quoted only, fills at read-only Jupiter round-trip quotes, size
0.01 SOL, never executed. `crashed=no`, clean final line.

- **20 gates → 20 shadow fills → 20 closes, 5W/15L, net −0.00889 SOL
  (−4.5 %/trade on stake).** Ledger 0.9989 → 0.9900 (shared paper
  ledger 1.0000 → 0.9900 incl. run81's final tail stop −0.00112).
- **Execution quality is now clean:** 0 ghosts, 0 entry no-quotes,
  0 sign failures, 0 impact blocks, 0 exit no-quotes, 0 rug-closes,
  0 warnings. SOL-quote filter: run81 28 ghosts → run82 0.
- Buckets: take 2 = +0.01288 (avg +64.4 %), **stop 11 = −0.02202
  (avg −20.0 %)**, trail 6 = −0.00021, stale 1 = +0.00046 (25 min,
  tape silent >600 s → exited at venue quote).
- **The loss is stop gap-through.** At the nominal −12 % trigger the
  11 stops would have cost −0.0132; realized −0.0220; the ~−0.0088
  excess is the whole net. 7/11 stops filled worse than −12 %
  (worst −80.9 % rug at 86 s: +34.9 % at 38 s, then collapsed; then
  −29.5, −22.2, −20.3, −19.7, −16.0, −11.8 %). Most gap-throughs
  happen within 3 s on thin pools.
- Entry fills: venue premium over tape −1.2..−1.6 % at 17/20 gates,
  −2.3 %/−3.5 % at two, +17.4 % at one (venue cheaper than a
  stale-high tape). All fills at the quoted venue price.
- **The legacy 5 % `priceImpact` cap would block 14/20 gates** —
  both +60 % takes (−16.6, −75.3) and the worst rug (−22.3) included.
  The field is uncorrelated with outcome at birth: replace it with a
  vpx-vs-tape / round-trip-cost check, do not tune it. Removed
  2026-10-19 — see the guard section below.
- No trade reached the 1 h TIME rail (max hold 25 min, median 23 s) —
  TIME is untested live.
- **Verdict: not profitable in realtime at this sample.** The take
  bucket works (+64 % avg, 2 hits); the stop gap-through is the lever.
  Not fundable until exit execution (gap control) and/or entry pool
  selection (pre-entry round-trip quote test) improves, and a longer
  run confirms.
- Contrast with the replay sim daemon (stopped 2026-10-18):
  +16.9 %/trade modeled vs −4.5 %/trade realtime. The sim fills stops
  at the bar minimum and overstates the take hit rate (22.6 % vs
  10 %). Replay is background only; realtime shadow is the verdict.
  Curve: `data/shadow_run82_curve.tsv`.

### 2026-10-19 — run82 fixes (entry quality, venue exits, liveness)

Implemented after the run82 verdict, before run83:

- **`priceImpact` cap retired** (`live.check_guards`). It would have
  blocked 14/20 run82 gates with no outcome correlation. Entry price
  sanity is measured directly instead:
  - **deviation guard** — `|tape_px/venue_px − 1| ≤
    LIVE_MAX_DEVIATION_PCT` (default 5 %). Run82 gates were 1.2–1.6 %;
    the one 17.4 % stale-tape entry stopped out −20 % in 3 s.
  - **round-trip guard** — after the buy preflight quote, immediately
    quote the sell side for the same base amount; skip when sell-back
    costs more than `LIVE_MAX_ROUNDTRIP_PCT` (default 8 %) or has no
    route. Pools where an immediate exit already gaps through the stop
    are exactly the run82 stop bucket (11 stops, −20 % avg). Both
    values are logged on every gate (`dev=… rt=…`).
- **Venue-confirmed shadow exits.** Stop/trail/take triggers are
  re-evaluated on the executable sell quote (`venue_exit_reason`); a
  tape print the venue does not corroborate is vetoed (5 s cooldown).
  Time-based exits (TIME/STALE) are never vetoed. Two run82 "stops"
  filled at −2.7 %/−3.5 % on tape blips while the venue was fine.
  Live exits already mark to venue quotes, so both modes now share the
  same executable-reality exit semantics.
- **Heartbeat + silence watchdog.** Every 5 min:
  `SHADOW heartbeat prints=… creates=… gates=… buys=… open=… uptime=…`;
  warn at 60 s without a frame, end the run at 10 min (a half-open
  socket must not fake a 24 h run). Tunables: `SHADOW_HEARTBEAT_S`,
  `SHADOW_SILENT_WARN_S`, `SHADOW_SILENT_EXIT_S`.
- Tests: 76/76 (deviation, round-trip cost, venue confirmation, and
  the retired impact cap).

Environment defaults for run83/dust: `LIVE_MAX_DEVIATION_PCT=5`,
`LIVE_MAX_ROUNDTRIP_PCT=8`; `LIVE_MAX_IMPACT_PCT` is no longer read.
