# RL Memecoin Project: Next Steps Plan

*Prepared October 11, 2026 from a review of RL\_MEMECOIN.ipynb (170 cells). The review covered the whole notebook's structure and read the data-audit, modeling and price-analysis cells closely, but it did not read every cell of the AMM-validation block (roughly Steps 63 to 81). Confirm cell-level details before acting on them.*

## 1. Where the project stands

The notebook is a careful data audit followed by a very large reverse-engineering of PumpSwap pricing and fees. It is not yet a reinforcement learning project: there is no environment, no reward, no policy and no training loop. That is a fine place to be. The audit work is the part most trading-ML projects skip, and it already caught real traps. But every next step should be sequenced around one question:

**Does any decision rule earn positive expected return after realistic costs, measured on data it was never tuned on? Only if yes does RL have anything to improve.**

**What is solid today**

- Dataset provenance: the Hugging Face commit SHA is recorded, a frozen parquet snapshot exists, and the cohort (classic launches, SOL-quoted, tape\_replay) is defined explicitly.
- The dataset's known-issue list (KI-11 to KI-14 and others) was read, not ignored.
- PumpSwap AMM math was checked against on-chain transactions: constant-product output, fee fields, the virtual quote reserve, and whether recorded prices are pre-trade or post-trade.
- Chronological splits and shuffled-label controls were used instead of random splits.

**What is not solid yet**

- The headline classifier (AP 0.74, ROC-AUC 0.94) is mostly leakage. Excluding launches where the creator's own buy is at least 80 SOL drops validation AP to 0.10 and test AP to 0.064.
- The October 2 test day has been inspected repeatedly and can no longer serve as a clean test.
- No analysis yet measures returns net of fees, price impact, latency and failed transactions. The existing forward-return tables explicitly exclude all of them.
- The price-path samples are tiny or unrepresentative: one hand-picked high-activity token (HIGGS), and a 100-launch random sample that yielded valid forward returns for only 28, 20, 12 and 4 tokens at the 5, 15, 30 and 60 second horizons.
- A Helius API key is hardcoded in the file, the notebook cannot be run top to bottom, and two cells have unresolved errors.

## 2. Immediate actions (first 48 hours)

1. **Rotate the Helius API key** (it begins 8ae6918d) in the Helius dashboard. It appears 8 times in the notebook: in comments, in two live fallback defaults around Steps 63 to 65, and once in an output. Treat it as compromised even if the file was never shared.
2. **Scrub the notebook** of the key in every cell and output, then clear all outputs (cell 80 alone carries about 393 KB). Keep a local archived copy with outputs, outside any repository.
3. **Tag and archive** the current notebook as the exploration record. Do not keep editing it.
4. **Resolve the two crashed cells**: cell 157 (AttributeError on pool\_position) and cell 165 (KeyError on log\_index). Either fix them or delete them and note why.
5. **Write a one-page problem statement** (Section 3) before writing more code. Most of the wasted effort so far traces to not having one.

## 3. Phase 0: Define the problem before building anything

Write these down and commit them before looking at any new results. Changing them after seeing outcomes is the main way trading research fools itself.

**The decision.** A recommended first framing: *given a newly launched classic SOL-quoted token and only the information available at decision time, should I buy a fixed small size now, and if so, when do I exit?* Start with one position per token, a fixed trade size, and a cap on concurrent positions. Position sizing is a later extension.

**Parameters to fix up front**

- **Universe:** classic launches only, or classic plus mayhem? The notebook compared them in Step 12 but the modeling excluded mayhem. Decide and document why.
- **Decision times:** a launch-time decision only, or repeated decisions at set intervals (for example every few seconds for the first N minutes)? Repeated decisions are closer to real trading but make the data requirements much heavier.
- **Execution assumptions:** trade size in SOL, a latency distribution from observation to landing, slippage tolerance, priority-fee or tip cost per transaction, and a rule for failed transactions.
- **Exit rules in v1:** a fixed hold, a stop and target rule, or a learned exit. Learning only the entry first isolates where the signal is.
- **Objective:** mean net return per trade, log growth of capital, or a tail-aware measure such as CVaR. Memecoin returns are heavy-tailed and the objective changes which policies look good.
- **Success criteria:** the exact gate in Section 6, stated in numbers.
- **Purpose:** live trading, confirmed on October 11, with a 1 SOL balance and 0.05 SOL per trade. Section 3.1 spells out what that implies.

### 3.1 Confirmed constraints and what they imply

You confirmed live trading with a 1 SOL balance and 0.05 SOL per trade. Three consequences shape every later phase.

1. **Fixed costs dominate at this size.** A 0.05 SOL trade pays the same priority fee, tip and token-account rent as a larger one, so a flat per-trade cost is a far bigger share of it. Section 5.4 puts sourced numbers on this: depending on the sending path, the minimum tip alone is 0.01% or 2% of a 0.05 SOL trade, per transaction. Read the fee schedule you will actually pay (the PumpApi fees page, if you use its trade API), measure your priority fee and tip, and put all of it in the simulator before judging any signal.
2. **Your own price impact is small; adverse selection is not.** At 0.05 SOL the impact on a curve holding tens of SOL is tiny, so the non-reactive replay assumption in Section 7.3 is reasonable. The risk is that the trades you can win against faster bots are systematically the worse ones.
3. **Live profit and loss on this account cannot validate an edge quickly.** If per-trade net return has a standard deviation of 40% (illustrative, measure yours), detecting a true +2% mean at 95% confidence takes about 1,500 trades. Statistical evidence has to come from replay and shadow mode. Live trading checks execution: fill rate, latency and fees.

**Starting account limits** (proposals; adjust them, then commit them before any live trade):

- Fixed 0.05 SOL per trade, with no size increase before Gate G4.
- At most 3 concurrent positions (0.15 SOL at risk). The balance could hold 20, but that leaves no buffer for fees or a rug-heavy day.
- Keep at least 0.1 SOL unspent for fees at all times.
- Daily loss stop at 0.10 SOL, and a total drawdown stop at 0.30 SOL that halts trading until you have reviewed it.
- A dedicated trading wallet holding no more than the 1 SOL, with the key outside the notebook and the repository.

## 4. Phase 1: Point-in-time data

### 4.1 Leakage findings that must be fixed

1. **Creator buys that fill the curve.** In the training split, launches with dev\_buy\_sol of at least 80 graduate 1,563 out of 1,563 times (100%); validation shows 427 of 427 and test 394 of 394. This is the label restated, not a predictor. The two launch-time features alone reach top-1% precision of 100%, but that is almost entirely this group.
2. **Early snapshots recorded after migration.** For high f10\_rs launches (50 SOL or more), 2,246 of the graduates have a snapshot age later than their migration time. At f10\_rs of 80 SOL or more, the graduation rate is 99.957%. These features describe the future, not the first ten seconds.
3. **The shuffled-label controls are not behaving like a null.** Cell 19's negative control reaches ROC-AUC 0.74, and cell 22's ten permutations range from 0.18 to 0.67 with a standard deviation of 0.157. With about 30,000 rows and roughly 1,000 positives, a true null should sit near 0.5 with a tiny spread. Likely causes are heavy ties or near-constant model outputs driven by a few extreme feature values. Find the cause before trusting any AUC from this pipeline.
4. **Label semantics.** Per KI-13, rugged and graduated are not complements: 2,574 of 25,550 graduates (10.1%) are also rugged, because the creator-dump branch is judged inside the first 300 seconds. Use rugged\_not\_graduated and rug\_branch\_inferred where available, and never treat rugged as the opposite of graduated.

### 4.2 A feature timestamp contract

Every feature gets an explicit available\_at time and must satisfy available\_at <= decision\_time - latency. Summary columns in the launch table (the f10\_\* and f60\_\* families) have unclear observation times, as Step 21 showed, so do not use them as model inputs. Rebuild equivalent features from the raw event tape with a hard cutoff at decision time minus latency. Add an automated test that fails if any feature column is computed from an event after its cutoff.

### 4.3 Label and outcome policy

- Graduation, rug and curve-completion flags are diagnostics, not training targets or reward terms. They are known only in hindsight and are not what you earn.
- The target is an executable return: simulate buying at decision time and exiting by a stated rule, using the Phase 2 simulator, net of all costs.
- Keep outcome flags available only for post-hoc analysis, such as what fraction of losses came from rugs.

### 4.4 Data hygiene rules from the dataset documentation

- **KI-11:** drop rows with negative timing intervals from timing analyses (11 launches between 13:54:53 and 13:56:26 UTC on 2026-09-09, and one at 14:55:17 UTC).
- **KI-12:** clip peak\_rs at 85.1 SOL or drop the 45 affected rows. Never silently keep them.
- **KI-14:** name, symbol and uri are untrusted creator text and may contain offensive content, scam links and control characters. If these are ever used as features, sanitize them, and never pass raw creator text to an LLM-based component without treating it as hostile input.
- Re-read the documentation revision before each new data pull. The revision recorded in the notebook is 08785081, and the dataset has changed since the first pull (new rugged\_not\_graduated and rug\_branch\_inferred columns appeared from 2026-10-01).

### 4.5 Build real price-path coverage

The event archive is the right source for price paths, but the current samples are far too thin. Plan a collection with these properties:

- Many days and many hours, not a single archive hour. A single hour is both small and highly regime-dependent.
- A stratified, seeded sample. Stratify by day, hour of day, launch activity level, and eventual outcome class, and store each launch's inclusion probability so results can be re-weighted to the full population.
- Do not select tokens by high activity before measuring. Step 41 stratified on observed PumpSwap activity, which conditions on the future. Activity-based sampling is acceptable only if you evaluate on the same conditioning at decision time, which you cannot.
- Explicit handling of price-path breaks at migration (Section 5).
- A consistent, versioned event table (parquet, partitioned by day) with a manifest recording source files and content hashes.

### 4.6 Split protocol

- **Development period:** everything up to a stated date. Free to explore.
- **Validation:** rolling walk-forward folds inside the development period, with an embargo at fold boundaries because tokens live across the midnight cutoff and path-dependent features leak across it.
- **Final holdout:** several days that did not exist when this plan was written. Collect them after fixing the plan, lock them, and look at them exactly once. October 2 does not qualify.
- **Regime checks:** report results per day. Base rates drifted by day in the audit, and a policy that only works on some days is a finding in itself.

### 4.7 Data source: pumpapi.io hourly replay

You pointed to the pumpapi.io Historical Replay as the event source. The notebook currently reads a different archive index (replay.shrine.trade, Step 29), so compare the two before switching. What the [pumpapi.io page](https://pumpapi.io/historical-replay) documents:

- Hourly archives of everything its Data Stream emits, starting April 18, 2026, at `https://replay.pumpapi.io/YEAR/MONTH/DAY/HOUR.jsonl.zst`, named by UTC hour. Directory listings are browsable by year, month and day.
- About 400 MB compressed and about 2 GB decompressed per hour, so a full day is roughly 9.6 GB compressed. Stream and decompress line by line, keep only the columns you need, and write parquet per hour instead of holding hours in memory.
- Each line has the same format as the live Data Stream. For live trading this is a real advantage: the parser and features built on replay run unchanged on the live feed, which removes a whole class of train-serve mismatch.
- An extra localTimestamp field exists only in replay: when the replay server in Frankfurt received the transaction. Do not use it as a feature, since it does not exist live. Use it only to judge latency at a given moment.
- Missing hours return 404. Record gaps in the manifest instead of skipping them silently.
- PumpApi's fee schedule lists both the replay and the live stream as free. The replay page states no download limits, so confirm that before large pulls.

How this changes the plan:

1. **Coverage is solvable.** Archives run from April 18 onward, so you can sample many days, including the post-October 2 days needed for the final holdout. Pre-register the holdout hours with a seeded draw, commit the list to the repository, and do not download or inspect them until Gate G3.
2. **Treat Jito bundles as atomic.** The page says a large share of pump.fun transactions are sent as bundles, bundles are not labeled in the stream, and your simulated trade cannot be inserted inside one. Its rule of thumb is to group transactions on the same token within about 3 ms into one bundled event, and to check doubtful clusters on the Jito explorer. Build this grouping into the event table and the simulator, and validate the 3 ms threshold yourself on a sample.
3. **Add a latency buffer.** The page advises a larger-than-usual latency buffer because real execution is slower than replay. Fold it into the latency distribution in Phase 2 and run the cost sweep with it.
4. **Check older data before pooling it.** Fees and creator-fee mechanics change over time. Start from the same recent window as the launch table, then test whether older months behave differently.
5. **Reconcile schemas.** The launch table and the replay events must join cleanly on mint and timestamp. Re-verify the timestamp units and price conventions you checked in Steps 29 to 31 and Steps 48 to 70 against this source.

## 5. Phase 2: Execution simulator

The notebook's best asset is its AMM validation work. The next step is turning it from analysis cells into a tested library, because every later conclusion depends on it being right.

### 5.1 Components

- **Bonding curve model.** Virtual and real reserves, buy and sell quotes using integer arithmetic, curve completion at about 85 SOL of real reserve, and fee deduction.
- **Migration model.** An explicit regime change when the curve completes and the pool opens. Steps 43 to 45 show price discontinuities at this transition. The environment must say what happens to an open position and what the first pool price and reserves are.
- **PumpSwap pool model.** Constant-product swaps, the fee components you decoded in Steps 65 to 75 (pool, protocol, creator and holder-reward fields as they appear in the events), the virtual quote reserve behavior, and the pre-trade versus post-trade price convention established in Steps 48 to 70.
- **Execution frictions.** None of these exist in the notebook yet, and together they likely decide whether any strategy works:
  - Latency from observation to landing, sampled from a distribution rather than a constant.
  - Price impact of your own order, computed analytically from reserves.
  - Slippage limits and failed transactions, including the fee still paid on failure.
  - Priority fee or tip cost per transaction and any account-creation or rent cost for new token accounts.
  - Competing bots and adverse selection: the trades you can win may be systematically worse than the average observed trade.
  - Intra-slot ordering, which the archive may not fully resolve.

### 5.2 Validation requirements

- **Exact integer match** against logged transactions wherever the program uses integer math. Report any non-zero residual and its size. Steps 80 and 81 left residual formula errors, so first document what remains and whether it matters for the trade sizes you plan to use.
- **Fixtures, not RPC calls.** Save a set of real transactions with pre-state and post-state to disk and test against them offline, so the test suite never depends on a network call or a paid API key.
- **Property tests:** a buy followed by a sell never returns more than was paid once fees are included; output is monotone in input; reserves are conserved; migrating never creates value.
- **Regression tests** for known-awkward cases found in Steps 167 and 168, where recorded start prices produced fake returns of about -99% until corrected to post-state prices.

### 5.3 Interface sketch

Keep the simulator pure and stateless, so it is easy to test:

- quote\_buy(state, sol\_in) returns tokens\_out, fee\_breakdown and new\_state
- quote\_sell(state, tokens\_in) returns sol\_out, fee\_breakdown and new\_state
- apply\_event(state, event) advances state through observed market events
- sample\_latency(rng) and sample\_fill(rng, quote, congestion) represent the execution model

### 5.4 Execution and infrastructure options

At 0.05 SOL the sending path's tip or fee model decides the economics, so choose it before tuning any signal. The figures below come from the vendors' own documentation, fetched October 11, 2026. They change, so re-check them before going live.

| Path | Cost at 0.05 SOL | Landing and routing | Fit |
| --- | --- | --- | --- |
| Your own transaction to the pump.fun or PumpSwap program, sent via [Helius Sender SWQOS-only](https://www.helius.dev/docs/sending-transactions/sender-swqos-only.md) | Minimum tip 0.000005 SOL (0.01% per transaction), plus a priority fee; no API credits | One fast SWQOS path. Helius calls it a good fit for cost-sensitive trading and points contested launches to Sender Max | Best economics. Landing rate is unproven, so measure it in shadow mode |
| Your own transaction via [Helius Sender Max](https://www.helius.dev/docs/sending-transactions/sender-max.md) | Minimum tip 0.001 SOL (2% per transaction, about 4% round trip), plus a priority fee | Multi-path across Helius, Jito, Harmonic, Rakurai and others; supports bundles | Too costly at this size unless the extra landing speed is shown to pay for itself |
| [Jupiter Order and Execute](https://developers.jup.ag/docs/swap/order-and-execute.md) (/order then /execute) | Platform fee of 50 bps for tokens under 24 hours old (about 1% round trip), 10 bps for most other pairs; no SOL tip | Managed landing, automatic slippage estimate, MEV protection; Metis, JupiterZ, Dflow and OKX compete on price; two API calls per swap | Simple, but the fee is steep on fresh launches and the extra calls add latency |
| [Jupiter Build](https://developers.jup.ag/docs/swap/build/index.md) with your own sending, or [tx.jup.ag](https://developers.jup.ag/docs/transaction/submit.md) | No Jupiter swap fee on /build; tx.jup.ag requires a minimum tip of 0.001 SOL (2%) | Metis routing only; you assemble, sign and send the transaction | A fallback router or exit path, paired with the cheap Helius tier |
| [PumpApi trade API](https://pumpapi.io/fees) | 0.25% of trade volume (0.000125 SOL on a 0.05 SOL trade, about 0.5% round trip), plus a priority fee you set per request | Lightning: PumpApi builds, signs and sends (vendor claims 100% landing; needs your key or an API key). Local: you get an unsigned transaction and send it yourself | Half Jupiter's fee on fresh launches. Weigh Lightning's key custody and measure landing in shadow mode |

What the sources imply:

1. **Tips can dwarf the edge.** A 0.001 SOL minimum tip is 2% of a 0.05 SOL buy and about 4% across a buy and a sell. Only the SWQOS-only tier (0.01% per transaction) leaves room for a modest edge. Implement the cost model as a per-path configuration so the cost sweep in Section 6 can swap paths.
2. **Jupiter does cover pump.fun, within limits.** Pump.fun and Pump.fun AMM are listed as eligible for instant routing, with a grace period set by token age. A curve that has not graduated by the end of that period is removed from routing ([Market Listing](https://developers.jup.ag/docs/swap/routing/amm/market-listing.md)). For holds of seconds or minutes this is not a constraint, but keep a direct-program sell path for any position that gets stuck.
3. **Do not compute profit from Jupiter prices.** The Price API V3 returns heuristic, last-swap USD prices. Use it for monitoring only. Compute profit and loss from actual fills and the simulator.
4. **Rate limits and requirements.** Jupiter allows 0.5 requests per second keyless, 1 on a free key and 10 on the $25 per month Developer plan, with /execute in its own larger bucket, so a quote per decision hits the free limit quickly. Helius Sender needs both a tip and a compute-unit-price instruction, and recommends skipping preflight and handling retries yourself with maxRetries set to 0. The opt-in mev-protect=true parameter routes around validators linked to sandwich attacks and can be combined with swqos\_only=true.

**Live data feed and hosting**

- **Use one feed for training and live.** The replay archives use the PumpApi Data Stream format. If live signals come from Helius LaserStream or Parsed Streams instead, the schemas differ, so you need a converter and a parity test on overlapping hours before trusting any trained policy. Helius lists Sender, its Priority Fee API and LaserStream as the trading-bot combination.
- **Backfill gaps with LaserStream replay.** LaserStream gRPC offers up to 48 hours of historical replay. That is enough to fill a gap in a live logger, not to replace the multi-month archive.
- **The faster signal tiers cost real money.** preprocessedSubscribe is on all paid plans (about 8 ms ahead of processed, 0.1 credits per message). Preconfirmations need the Professional plan or higher (10 credits per message, minimum 300 credits per covered slot per subscription). Raw shreds cost $1,000 per month per IP. On a 1 SOL account, treat the top of the latency stack as out of budget until the strategy has shown an edge.
- **Hosting.** Helius Sender has regional endpoints including Frankfurt, Amsterdam and London, Jupiter's gateway has a Frankfurt region, and the PumpApi replay server is in Frankfurt. Frankfurt is a reasonable first host to test. Measure end-to-end latency from the real host instead of trusting this.
- **Gatekeeper.** Swapping the RPC URL to beta.helius-rpc.com keeps the same API key, methods and pricing, and Helius says it removes Cloudflare from the path. The beta label refers to the rollout. Try it and measure.

**Key handling.** The leaked key makes this concrete. Use separate API keys for research and live trading, and scope each to least privilege: Jupiter's portal supports per-key endpoint allow-lists and firewall rules, and Helius has a Protect Your API Keys guide. Keep the signing key out of agent tooling such as Jupiter's trading MCP and CLI. A latency-sensitive, rule-based bot should not route signing through an LLM agent.

Sources, fetched October 11, 2026: [Helius docs index](https://www.helius.dev/docs/llms.txt), [Helius Sender SWQOS-only](https://www.helius.dev/docs/sending-transactions/sender-swqos-only.md), [Jupiter docs index](https://developers.jup.ag/docs/llms.txt), [Jupiter Order and Execute](https://developers.jup.ag/docs/swap/order-and-execute.md), [Jupiter Market Listing](https://developers.jup.ag/docs/swap/routing/amm/market-listing.md).

### 5.5 Chosen architecture: PumpApi stream, Jupiter quote and swap

You chose the PumpApi Data Stream for signals and Jupiter for quoting and swapping. This plan reads that as Swap API V2 `/order` then `/execute`: managed landing, no separate SOL tip, with the platform fee paid inside the swap. If you meant `/build` with your own sending, say so and row 4 of the Section 5.4 table applies instead.

This choice settles the train-serve question from Section 4.7. The stream and the replay archives share one format, so the same parser and feature code run in research and live.

**Live loop**

1. A stream event arrives and updates the in-memory token state: reserves, trailing trade flow, creator-wallet actions.
2. The policy decides from that state alone. It never calls Jupiter to price a token.
3. To act, call `GET /swap/v2/order` with the input and output mints, the amount (0.05 SOL is 50000000 lamports) and the trading wallet as taker. Use no optional parameters at first, so every router stays eligible and slippage is estimated automatically.
4. Sign the returned transaction immediately. The docs warn that quotes go stale, and that `/order` can return an empty transaction with an error code. Handle and log that case.
5. `POST /swap/v2/execute` with the signed transaction and the requestId.
6. Record status, code, signature, input and output amounts and the fee fields, then update position state from the stream.

**What this does to the cost model**

- Jupiter's platform fee is 50 bps per swap for tokens under 24 hours old and 10 bps for most other pairs. On a new token that is about 1% across a buy and a sell, before the underlying pump.fun or PumpSwap fee and your price impact. Make this the default path in the Phase 2 cost configuration and run Gate G1 against it.
- The response separates total feeBps from platformFee.feeBps, because extra charges such as gasless support can be added. Log both and model whichever you actually pay.
- Priority fees are set by Jupiter's landing pipeline. Measure what each swap really costs in SOL from wallet balance changes, and put that figure in the model.
- The fee falls from 50 to 10 bps once a token is 24 hours old, so test a universe of older tokens alongside fresh launches. A policy that only works at the 0.5% fee on fresh launches is fragile.
- Any optional parameter on /order, such as slippageBps, switches it to manual mode and can restrict routing. Use defaults first, then test overrides in shadow mode.

**Rate limits and latency**

- Quote only when acting. Jupiter allows 0.5 requests per second keyless and 1 on a free key, which a quote-per-observation design would exhaust. With at most 3 concurrent positions and decisions driven by the stream, a free key may be enough to start. Move to the Developer plan (10 requests per second) if shadow logs show throttling. /execute has its own, larger bucket.
- Timestamp every stage: stream receive, decision, /order sent and returned, signed, /execute returned, confirmed. Compare your receive time with each event's millisecond timestamp to measure feed delay. This stage-by-stage budget replaces the single latency assumption in the simulator.
- Run the process in Frankfurt first, since Jupiter's gateway and the PumpApi replay server are both there, then measure.

**What replay cannot tell you, and shadow mode must**

- Which router wins, and how often /order fails to build or /execute fails to land. The docs list codes such as -1000 for failed to land and -2003 for an expired RFQ quote.
- How far a quote's output differs from the executed output at your size and latency.
- Whether quotes exist for tokens only seconds old. Pump.fun is listed for instant routing, but verify it on real launches.

In shadow mode, call /order with the trading wallet as taker but never sign or execute, and also with no taker for price-only quotes (the docs say a quote without a taker returns no transaction). Log both against what the stream shows afterwards.

Keep the direct-program sell path from Section 5.4 for stuck positions. Store the Jupiter API key in a secrets manager, with its permission allow-list limited to the Swap endpoints.

### 5.6 PumpApi's own trade API and stream: what the full docs add

PumpApi's [full documentation](https://pumpapi.io/llms-full.txt), fetched October 11, 2026, adds facts that bear on the Jupiter choice. One caveat: the text I received cut off partway through the Jito Bundles page, so the Data Stream event schema and the Trade API reference were not in it. Read those two pages before writing the parser or any order code.

**Fee comparison on a 0.05 SOL trade.** These are platform or API fees only. Each excludes the pump.fun or PumpSwap protocol fee, priority fees and price impact.

| Path | Fee per swap | Per swap in SOL | Round trip in SOL |
| --- | --- | --- | --- |
| [Jupiter Order and Execute](https://developers.jup.ag/docs/swap/order-and-execute.md), token under 24 hours old | 0.50% | 0.00025 | 0.0005 |
| Jupiter Order and Execute, older token | 0.10% | 0.00005 | 0.0001 |
| [PumpApi trade API](https://pumpapi.io/fees), buy or sell | 0.25% | 0.000125 | 0.00025 |
| Your own transaction via [Helius Sender SWQOS-only](https://www.helius.dev/docs/sending-transactions/sender-swqos-only.md) | Minimum tip 0.000005 SOL per transaction | 0.000005 | 0.00001 |

On fresh launches PumpApi's fee is half of Jupiter's. The Helius row has no platform fee, but you build and sign the transaction yourself. Vendor claims such as PumpApi's 100% landing rate for Lightning mode are marketing figures until your shadow logs confirm them.

**Trade-offs between Jupiter and PumpApi for execution**

- **Cost:** PumpApi saves about 0.25% per swap on new tokens, which is 0.5% per round trip. With a thin edge, that can decide the result.
- **Key custody:** Jupiter returns an unsigned transaction and you sign locally. PumpApi's Lightning mode needs your private key or an API key so it can build, sign and send. Its Local mode returns an unsigned transaction instead, but then you must send it yourself, for example through Helius Sender. With a dedicated 1 SOL wallet the exposure is bounded, but a third party would still hold a signing key.
- **Calls and latency:** Lightning is one request, while Jupiter needs /order then /execute. PumpApi says its servers are in Frankfurt, and Jupiter's gateway has a Frankfurt region. PumpApi also says a distant host can lose up to 200 ms. That is the vendor's own claim, so measure it.
- **Routing and protection:** Jupiter adds competing routers, automatic slippage estimation and MEV protection. PumpApi covers pump.fun, PumpSwap and several other venues through one API.

Recommendation: build the executor behind one interface with a Jupiter and a PumpApi implementation, run both in shadow mode, and choose on measured landing rate, slippage and total cost rather than on documentation.

**Stream facts that shape the infrastructure**

- The stream is at wss://stream.pumpapi.io, is free, and needs no account or API key.
- There is a strict limit of one connection per IP address. PumpApi recommends one local relay (ZeroMQ or a local WebSocket) that fans events out to every process. Run one ingest process, and have the live logger and the trading bot both read from the relay.
- Volume is about 300 to 400 transactions per second across all pools plus transfers, according to PumpApi. Size the logger's disk and parser for that.
- Record the live stream yourself from now on. It builds a forward dataset in exactly the live format and gives you holdout days you control.
- The stream and replay also cover Raydium, Meteora and Orca pools, so the universe can widen beyond pump.fun if the first universe shows no edge.

Source, fetched October 11, 2026: [PumpApi full docs](https://pumpapi.io/llms-full.txt).

## 6. Phase 3: Baselines and the go or no-go gate

Build these before any RL. They are cheap, and they tell you whether there is anything for RL to find.

1. **Never trade** (zero return, the benchmark everything must beat).
2. **Random entry** at random decision times with the same hold rule, run many times. This is your null distribution.
3. **Fixed rules** such as enter at launch and hold for N seconds, or buy only when a simple threshold on trailing buy flow is met.
4. **Supervised return model.** Predict the forward net-return distribution (quantile or expected value) from point-in-time features, then trade when predicted edge exceeds cost by a margin. This replaces the graduation classifier.
5. **A contextual bandit** over the same features for the entry decision, once the supervised baseline exists.

### Evaluation statistics

- The unit of analysis is the token, and standard errors must cluster by day, because trades on the same day share market conditions. Use a cluster bootstrap and report the full return distribution: mean, median, 10th and 90th percentiles, win rate, worst trade, and maximum drawdown.
- Count every variant tried and correct for multiple comparisons, or at least report how many configurations were tested to find the best one.
- Run the null checks: shuffled-time and random-entry controls must produce about zero net return. If they do not, the simulator has a bug.
- Run a cost-sensitivity sweep over latency, fees and slippage. A strategy that only works at zero latency is not a strategy.

### Gate G1 (proposed, adjust the numbers before running)

Proceed to RL only if at least one non-RL baseline shows a lower 95% cluster-bootstrap confidence bound on mean net return per trade above zero (in SOL, at 0.05 SOL size, after fixed per-trade costs) on walk-forward validation, across at least a stated number of days, under pessimistic cost assumptions, with results stable across the per-day breakdown. If no baseline passes, the project's honest result is that this setup has no demonstrable edge, which is a useful and publishable outcome. Do not proceed to RL hoping it will find one.

## 7. Phase 4: Reinforcement learning (only after Gate G1)

### 7.1 Environment specification

Implement a Gymnasium-style environment on top of the Phase 2 simulator, replaying recorded event tapes.

- **Episode:** one token's lifecycle from launch (or from the first decision time) to a terminal condition. Terminal conditions are forced liquidation at the horizon cap, migration handling per Section 5, or exit by the agent.
- **Observation:** only point-in-time features (Section 4.2): curve state and price, time since launch, trailing trade-flow statistics at several windows, creator-wallet actions seen so far, holder concentration indicators, and agent state (inventory, entry price, unrealized PnL, time held). Normalize with training-period statistics only.
- **Actions (discrete, v1):** skip or wait, buy a fixed size, hold, sell all. Use action masking so illegal actions, such as selling with no position, are never chosen.
- **Timing:** the action chosen at step t executes at a latency-shifted time drawn from the latency model against the market state at that later time, never at the price the agent saw.
- **Reward:** change in net wealth in SOL (or its log) after every fee, tip and impact. Terminal liquidation uses an executable sell quote, not the last recorded price. Optionally add a risk penalty. No bonus for graduation or any other hindsight label.
- **Truncation:** a hard step limit, and a rule for tokens whose event data ends mid-episode (mark them and exclude them from training rather than inventing an exit price).

### 7.2 Algorithm choices

- Start small: tabular or linear policies and shallow networks. With heavy-tailed rewards and a few hundred thousand tokens, large networks mostly memorize tapes.
- PPO or DQN with discrete actions is the pragmatic first choice. Offline RL methods are appealing because the data is logged, but there is no behavior policy to correct for, and your own trades would change the market in reality, so replay-based online training with a conservative size cap is simpler and easier to validate.
- Run at least 10 seeds per configuration and report the spread. RL results from one seed are anecdotes.

### 7.3 Known pitfalls specific to this problem

- **Non-reactive replay.** Other traders do not react to your orders in a replay. Keep size small enough that the analytic price impact dominates, and state the capacity limit you assume.
- **Overfitting to a finite tape set.** Train and validate on disjoint days, and compare against the best Phase 3 baseline. If RL does not beat it net of costs, prefer the simpler policy.
- **Heavy tails in the reward.** A few 50x tokens can dominate the average. Check results with and without the top 1% of winners, and consider rank or clipped reward during training while still evaluating on raw net return.
- **Survivorship in what you can observe.** Tokens with no trades, no coverage, or broken paths drop out of replay. Quantify what fraction and whether they differ in outcome.
- **Reward hacking in the simulator.** If the agent finds a trick that depends on a simulator quirk, such as a fill at a stale price, treat it as a simulator bug and fix the simulator.

## 8. Phase 5: Final evaluation and live validation

1. **Freeze** the policy, simulator version, data snapshot hash and config. Record them.
2. **Evaluate once** on the locked final holdout days. Report the same distribution statistics as in Phase 3 and compare against all baselines.
3. **Stress tests:** double the fees, double the latency, halve the fill rate, remove the top 1% of winners, and re-run on each day separately.
4. **Shadow mode.** Run the policy live without trading. Log every decision and the simulated fill, then compare against what actually happened to the pool afterwards. Measure real landing latency and failure rates. The gap between simulated and shadow results is the most valuable number in the whole project.
5. **Live with tiny capital only if everything above holds,** with hard caps on position size, daily loss and concurrent positions, an automatic kill switch, and the key stored in a secrets manager with a dedicated low-balance wallet. Starting limits for the 1 SOL account are in Section 3.1.

**A necessary caution.** Memecoin trading is adversarial, fee-heavy and exposed to rugs, front-running and sandwiching. Most participants lose money, and an edge that survives your simulator may still not survive contact with real execution. Only risk money you can lose entirely, and check the regulatory and tax treatment that applies in your jurisdiction. This plan is a research methodology, not financial advice.

## 9. Engineering plan

### 9.1 Repository layout

- data/ (loaders, snapshot manifest, event-table builder, sampling code)
- features/ (point-in-time feature builders with the available\_at test)
- sim/ (bonding\_curve.py, pumpswap.py, fees.py, latency.py, migration.py)
- env/ (the Gymnasium environment and wrappers)
- baselines/ (random entry, fixed rules, supervised return model, bandit)
- eval/ (walk-forward runner, cluster bootstrap, cost sweeps, reporting)
- tests/ (unit, property and fixture-based regression tests)
- configs/ (one file per experiment, versioned)
- notebooks/ (thin, output-stripped, calling library code only)
- docs/ (problem statement, assumptions log, results log)

### 9.2 What to do with the existing notebook

- **Cells 0 to 13 (dataset audit):** convert to a script that produces a dated audit report, so the checks re-run on each data refresh.
- **Cells 14 to 31 (graduation classifier):** archive as a documented leakage case study. Do not carry the model forward. Keep the permutation-test cells as a reusable sanity harness once the odd null behavior is understood.
- **Cells 32 to 60 (event archive and first price paths):** extract the archive reader and event parsing into data/. Re-run the forward-return analyses on corrected post-state prices, since earlier cells used raw recorded prices that Steps 167 and 168 showed are pre-trade.
- **Cells 61 to 168 (AMM validation):** distill into sim/ with fixtures and tests. Many cells are near-duplicate fetch and decode helpers, so consolidate them, then delete the exploratory versions. Keep one short notebook that demonstrates the validation results from cached fixtures.

### 9.3 Tooling

- **Secrets:** environment variables or a secrets manager only, plus a pre-commit secret scanner such as gitleaks or detect-secrets so a key can never be committed again.
- **Reproducibility:** pin dependencies, set and log seeds, record the dataset commit SHA and event-table manifest hash in every result file.
- **Notebook hygiene:** nbstripout in pre-commit, and no network calls inside analysis cells. Cache every RPC response to disk keyed by transaction signature.
- **Testing and CI:** pytest, a linter, and a CI run that executes the simulator tests and a small end-to-end smoke test on fixtures.
- **Experiment tracking:** MLflow, Weights and Biases, or a plain results directory with one JSON per run containing config, git commit, data hashes and metrics.
- **Rate and cost control:** all RPC use goes through a caching client with retry and rate limiting, so a re-run costs nothing.

## 10. Milestones and decision gates

Durations are rough and assume part-time work. Treat the order and the gates as firm and the dates as soft.

- **M0 (days 1 to 2): Cleanup.** Key rotated, notebook scrubbed and archived, crashed cells resolved, problem statement written. *Done when:* the notebook contains no secrets and the problem statement is committed.
- **M1 (week 1): Repository and data contract.** Repo skeleton, secret scanning, snapshot manifest, feature timestamp contract and its test. *Done when:* a leaky feature fails the test.
- **M2 (weeks 2 to 3): Simulator.** Bonding curve, migration, pool and fee code with fixtures and property tests, plus the documented residual from Step 81 and a per-path cost model (Section 5.4). *Done when:* the test suite reproduces logged transactions exactly where integer math applies.
- **M3 (weeks 3 to 4): Coverage.** Stratified multi-day event table built from the hourly replay archives, with sampling probabilities and a pre-registered list of holdout hours (Section 4.7). *Done when:* the sample supports at least hundreds of valid forward returns per horizon.
- **M4 (weeks 4 to 6): Baselines and Gate G1.** Never-trade, random-entry, fixed rules, supervised return model, cost sweeps, cluster-bootstrap results. *Decision:* proceed, redesign, or stop.
- **M5 (weeks 7 to 10, conditional): RL.** Environment, small-policy training with seeds, ablations against the best baseline.
- **M6 (week 11 onward, conditional): Final holdout, shadow mode, and a go or no-go on any live capital.**

**Gates:** G0 is a clean repository with no secrets. G1 is the baseline edge test in Section 6. G2 is RL beating the best baseline on validation days net of costs across seeds. G3 is a single pass on the locked holdout. G4 is shadow results within tolerance of simulated results.

## 11. Risks and open questions

**Risks**

- **There may be no edge.** After costs and latency the realistic expectation for naive entry on memecoin launches is negative. The plan is built so that this is discovered cheaply, in M4, rather than after weeks of RL work.
- **Data coverage and selection bias** could still hide the truth even with a bigger sample. Keep inclusion probabilities and re-weight.
- **Adversarial and changing environment.** Protocol fees, creator-fee mechanics and bot behavior change over time, and the dataset itself is revised. Re-validate the simulator against fresh transactions on a schedule.
- **Simulator error.** An undetected pricing error would make a losing strategy look profitable. This is why the simulator gets the most testing.
- **Operational and security risk** from API keys, wallets and RPC dependencies once anything touches live execution.

**Questions: settled and still open**

- **Settled:** live trading, a 1 SOL balance and 0.05 SOL per trade (Section 3.1).
- **Settled:** replay archives exist from April 18, 2026 onward, so days after October 2 are available (Section 4.7). Pricing is settled: free per PumpApi's fee schedule. Still to confirm: any download limits, which the replay page does not state.
- Which archive is the source of record? The PumpApi stream choice implies pumpapi.io replay, since it shares the live format. Keep replay.shrine.trade (used in the notebook) only as a cross-check, and compare coverage and gaps before dropping it.
- Settled: the PumpApi Data Stream feeds signals and Jupiter handles quote and swap (Section 5.5). The plan assumes /order then /execute rather than /build. Confirm or switch. Section 5.6 suggests also testing PumpApi's own trade API, which charges half Jupiter's fee on new tokens, in shadow mode before committing.
- What latency can you realistically achieve from where the system will run? Measure it from the intended host before fixing the latency distribution.
- Should mayhem launches be included in the universe?
- Where will the trading wallet's key live, and who has access to the host?

## Appendix A: Leakage audit checklist

Run this on every feature and every label before it enters a model or environment.

1. What event or snapshot does this value come from, and what is its timestamp?
2. Is that timestamp at least latency seconds before the decision time? If unknown, the feature is excluded.
3. Could the value be a function of the outcome, such as a creator buy large enough to complete the curve?
4. Does the feature distribution differ by split in a way that suggests a collection change, such as the post-recorder-restart cohort noted in Step 21?
5. Does a shuffled-label or shuffled-time control give about 0.5 AUC or about zero net return? If not, stop and find out why.
6. Does performance collapse when the top few extreme values are removed? If so, the model is mostly learning those values.
7. Is the decision made at time t using prices that would only be knowable after t?

## Appendix B: Draft observation and reward specification

**Observation vector (v1 draft)**

- Time since launch, in seconds, and time remaining to the horizon cap
- Curve progress (real reserve over about 85 SOL) and current quote price
- Trailing buy count, sell count and net SOL flow over several window lengths
- Unique trader count and a simple concentration measure, computed from events up to the cutoff
- Creator-wallet state: bought, sold, or neither, and size relative to supply
- Agent state: position size, entry price, unrealized PnL, time held
- Normalization statistics fixed from the training period

**Reward**

r\_t = (V\_t\_plus\_1 minus V\_t) after all costs, where V is net wealth in SOL, valued at an executable sell quote for any open position. A trade costs the pool and protocol fees plus the priority fee or tip, a failed transaction costs the fee only, and the final step liquidates at the horizon. Optional variants: log wealth, or a mean minus a CVaR penalty. No term depends on graduation, rug flags or any other hindsight label.

## Appendix C: Evidence from the notebook

- **Splits (Step 13):** train 108,231 launches (3.09% graduated), validation (October 1) 30,781, test (October 2) 29,836.
- **Baseline (Step 14):** validation AP 0.7415 and ROC-AUC 0.9381; test AP 0.7308 and ROC-AUC 0.9304.
- **Launch-time only (Step 22):** validation AP 0.5835; test AP 0.5396.
- **Excluding dev\_buy\_sol of at least 80 (Step 26):** validation AP 0.1032 and ROC-AUC 0.7514; test AP 0.0641 and ROC-AUC 0.7366.
- **Snapshot timing (Step 21):** of 4,015 graduates with usable times, 2,246 have a snapshot recorded after migration.
- **Dataset documentation (Step 11):** KI-11 negative intervals, KI-12 peak above curve limit, KI-13 labels not exclusive, KI-14 untrusted creator text.
- **Random sample coverage (Step 38):** 100 sampled launches, with valid forward returns for 28, 20, 12 and 4 tokens at the 5, 15, 30 and 60 second horizons.
- **Price convention (Steps 167 and 168):** recorded prices are pre-trade, and apparent returns near -99% disappear after post-state correction.
- **Security:** one Helius API key, 8 occurrences in the raw notebook file.
