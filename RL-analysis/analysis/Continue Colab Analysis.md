> From: https://chatgpt.com/c/6ac9d232-8640-83ed-b25f-37cb35a0b2f5

# you asked

Read the file. Let continue the code. output of last cell in colab  df["day"] = df["launched_dt"].dt.date

# 1) What share of each column is blank (null), day by day?
cols = ["graduated", "rugged", "curve_complete", "decoder_complete", "terminal_rs", "f10_rs"]
print("Share of blank values per day:")
print(df.groupby("day")[cols].agg(lambda s: s.isna().mean()).round(3))
print()

# 2) Rates per day (averages ignore blanks)
print("Rates per day:")
print(df.groupby("day")[["graduated", "rugged", "mayhem"]].mean().round(4))
print()

# 3) Do 'graduated' and 'rugged' overlap? (-1 means unknown)
print("Graduated (rows) vs rugged (columns); -1 = unknown:")
print(pd.crosstab(df["graduated"].fillna(-1), df["rugged"].fillna(-1)))
print()

# 4) The new columns
for c in ["features_basis", "quote_asset", "rug_branch_inferred"]:
    print(f"{c}:")
    print(df[c].value_counts(dropna=False).head(10))
    print()

print(df[["silence_3s", "silence_60s", "create_lag_s"]].describe().T)

---

# chatgpt response

I've read the file. We're at **Step 2, Cell 4** of your Colab notebook. The goal is to understand missing data, graduation and rug labels, and the new features before we start building the RL environment. <FileCite ref_id="turn0file0" line_range_start={644} line_range_end={679} />

The code you pasted is the **cell's source code, not its execution output**. Let's finish this step before adding anything else, as planned.

### What to do in Colab

1. Run Cell 4 exactly as shown in your file.
2. Copy the actual printed output, including all tables and the final statistics.
3. Also share the two lines from Cell 3 showing the dataset commit and last-modified date, if you have them.

**Why this matters:** We need to determine whether missing outcomes are concentrated among recent launches, whether `graduated` and `rugged` overlap, and how the feature columns are populated. Those findings will guide our next step and help prevent misleading training results.

Don't change the code or run another cell yet. Once you send the output, we'll analyze it and proceed to the next step, one cell at a time.

---

# chatgpt response

I opened `RL_MEMECOIN.ipynb` and checked the output of Cell 4. You've completed the data snapshot and initial audit successfully. We can continue from your existing Colab notebook without restarting it.

## Step 2 — What your results tell us

**1. Your snapshot is saved.**

<box border radius="lg" padding={3} gap={2}>
  <row align="center" gap={2}>
    <icon name="check-circle" color="success" size="lg"/>
    <box flex="1" gap={1}>
      **Dataset version recorded**

      <text color="secondary" size="sm">Commit: `21be6aeb5d66721e3d40e34b09141f408e1e0ca0`</text>
    </box>
  </row>
  <row align="center" gap={2}>
    <icon name="check-circle" color="success" size="lg"/>
    <box flex="1" gap={1}>
      **Snapshot copied to Google Drive**

      <text color="secondary" size="sm">`MyDrive/memecoin_rl/launches_snapshot.parquet`</text>
    </box>
  </row>
</box>

**2. Graduation and rug labels are not mutually exclusive.**

Your known-label graduation rate is approximately **2.18%**, while the dataset's `rugged` label rate is approximately **72.60%**. These are rates among rows with known labels, not necessarily the true rates for every launch.

Your crosstab also shows 575 launches marked both graduated and rugged. Therefore, we must not treat graduation and rug status as opposite outcomes.

**3. Missing values are not automatically failures.**

Some rows have unknown graduation or rug outcomes. Missingness varies by launch day, and September 30 has particularly high missingness for several fields. We should retain unknown outcomes as unknown rather than converting them to zero.

**4. Two things deserve closer inspection.**

- `features_basis` includes 620 `harness_sample` rows. We should examine them separately before using the data for modeling.
- Only 241,683 rows have `quote_asset = sol`; the rest include other quote-asset categories. We should measure how these groups differ before selecting our training universe.

One important distinction: this dataset has one row per launch rather than a full sequence of trading states and prices. It helps us investigate token selection and outcome prediction, but it is not sufficient by itself to train a meaningful PPO trading agent. <FileCite ref_id="turn0file0" line_range_start={420} line_range_end={447}/>

---

#y.round(4))
print()

# 3) Compare the recorded feature sources
print("=== Results by features_basis ===")

basis_summary = df.groupby("features_basis", dropna=False).agg(
    launches=("mint", "size"),
    graduation_coverage=("graduated", lambda s: s.notna().mean()),
    graduation_rate=("graduated", "mean"),
    rug_coverage=("rugged", lambda s: s.notna().mean()),
    rug_rate=("rugged", "mean"),
    f10_coverage=("f10_rs", lambda s: s.notna().mean()),
)

print(basis_summary.round(4))
</CodeBlock>

### How to read the output

| Column | Meaning |
|---|---|
| `Duplicate mint rows` | Whether a token appears in multiple rows. |
| `graduation_coverage` | Fraction of launches with a known graduation label. |
| `graduation_rate` | Graduation rate among launches with known labels. |
| `rug_coverage` | Fraction with a known rug label. |
| `rug_rate` | Rate of the dataset's rug label among known labels. |
| `f10_coverage` | Fraction with the `f10_rs` feature available. |

Coverage is expressed as a fraction from `0` to `1`; for example, `0.90` means 90%.

**Don't filter rows or train a model yet.** Paste the complete output of Step 3 here, and we'll interpret it before moving to the next cell.

---

# you asked

=== Mint integrity ===
Total rows: 269538
Unique mints: 269538
Missing mint values: 0
Duplicate mint rows: 0

=== Results by quote_asset ===
             launches  unique_mints  graduation_coverage  graduation_rate  \
quote_asset                                                                 
other           16716         16716                  0.0              NaN   
sol            241683        241683                  1.0           0.0218   
stock            7698          7698                  0.0              NaN   
usdc             3434          3434                  0.0              NaN   
NaN                 7             7                  1.0           0.0000   

             rug_coverage  rug_rate  f10_coverage  
quote_asset                                        
other              0.0000       NaN        0.0000  
sol                0.9843     0.726        0.9402  
stock              0.0000       NaN        0.0000  
usdc               0.0000       NaN        0.0000  
NaN                0.8571     0.000        1.0000  

=== Results by features_basis ===
                launches  graduation_coverage  graduation_rate  rug_coverage  \
features_basis                                                                 
harness_sample       620               0.9258           0.0192        0.9161   
tape_replay       268918               0.8966           0.0218        0.8825   

                rug_rate  f10_coverage  
features_basis                          
harness_sample    0.8292        0.6387  
tape_replay       0.7258        0.8436

---

# chatgpt response

Good. This output gives us a useful result: **all 269,538 rows have unique mint addresses**, so we have no duplicate-token problem in this snapshot.

## Step 3 — Interpretation

<box border radius="lg" padding={3} gap={3}>
  <row align="start" gap={3}>
    <icon name="check-circle" color="success" size="xl" />
    <box flex="1" gap={1}>
      **Mint integrity: passed**

      <text color="secondary" size="sm">269,538 rows, 269,538 unique mints, zero duplicates, zero missing mint values.</text>
    </box>
  </row>
  <divider color="subtle" />
  <row align="start" gap={3}>
    <icon name="database" size="xl" color="secondary" />
    <box flex="1" gap={1}>
      **The labeled dataset is effectively SOL-only**

      <text color="secondary" size="sm">All 241,683 rows with `quote_asset = sol` have a graduation label. The `other`, `stock`, and `usdc` groups have no graduation or rug labels and no `f10_rs` features. We should not mix them into our initial modeling dataset.</text>
    </box>
  </row>
  <divider color="subtle" />
  <row align="start" gap={3}>
    <icon name="search" size="xl" color="secondary" />
    <box flex="1" gap={1}>
      **Investigate `harness_sample`**

      <text color="secondary" size="sm">These 620 rows have an 82.92% rug-label rate, versus 72.58% for `tape_replay`. Their lower feature coverage could indicate int("Rows:", len(h))
print("Unique mints:", h["mint"].nunique())
print("First launch:", h["launched_dt"].min())
print("Last launch: ", h["launched_dt"].max())
print()

print("Harness launches per day:")
print(h.groupby(h["launched_dt"].dt.date).size().to_string())
print()

# 3) Inspect 10 representative rows
cols = [
    "mint",
    "launched_at",
    "quote_asset",
    "mayhem",
    "graduated",
    "rugged",
    "features_basis",
    "f10_rs",
    "f60_rs",
    "create_lag_s",
    "silence_3s",
    "silence_60s",
]

print("=== Example harness rows ===")
print(
    h[cols].sample(n=min(10, len(h)), random_state=42)
    .to_string(index=False)
)
```

### What we are looking for

The date range will help us determine whether these rows are concentrated in a particular period. The examples may reveal differences in missing values or feature patterns, though they cannot establish by themselves that the data is synthetic.

For now, **do not start training PPO**. We first need a defensible data population and a clear understanding of which fields are trustworthy.

Paste the complete output of Step 4 here. We'll analyze it before proceeding to the next cell.

---

# you asked

=== Feature source vs quote asset ===
quote_asset     <missing>  other     sol  stock  usdc     All
features_basis                                               
harness_sample          0     30     574      4    12     620
tape_replay             7  16686  241109   7694  3422  268918
All                     7  16716  241683   7698  3434  269538

=== Harness sample overview ===
Rows: 620
Unique mints: 620
First launch: 2026-09-27 00:00:02.844000+00:00
Last launch:  2026-09-27 00:18:32.404000+00:00

Harness launches per day:
launched_dt
2026-09-27    620

=== Example harness rows ===
                                        mint                 launched_at quote_asset  mayhem  graduated  rugged features_basis   f10_rs   f60_rs  create_lag_s  silence_3s  silence_60s
3pcW7ZdgJ5QpSKsoDidjTy2J8wJXWH1ETyrWvWxqpump 2026-09-27T00:00:51.842000Z         sol       1        0.0     1.0 harness_sample      NaN      NaN           NaN         NaN          NaN
Ac2JGoS3CMVp1Q9ZKKekpMBX6Zb7KsPAqDQEqFWUpump 2026-09-27T00:17:23.773000Z         sol       1        0.0     1.0 harness_sample      NaN      NaN           NaN         NaN          NaN
AF36firMVvc5UxfV6Y3WeFqkDJ1WcLsHammxEx3TeJsi 2026-09-27T00:01:25.059999Z         sol       0        0.0     1.0 harness_sample 2.037068 4.499031           NaN         NaN          NaN
7ZDhzC2Qff4Hjf4yCDFmo82xgUkbR3w8eWTuoeHUpump 2026-09-27T00:07:20.934999Z         sol       0        0.0     1.0 harness_sample 1.843040      NaN           NaN         NaN          NaN
J6quXVhTok7hfYwTZxKnP2pGjscfVUfkR8ZNRe1Bpump 2026-09-27T00:02:07.295000Z         sol       0        0.0     1.0 harness_sample 0.004531      NaN           NaN         NaN          NaN
DtsASYEfwhuXELoEW8AbtcazRLcbCXBY1QJAFzAhpump 2026-09-27T00:18:10.384000Z         sol       0        0.0     1.0 harness_sample 0.710564      NaN           NaN         NaN          NaN
AyWnC7eVBGqKcWmoTb8GnMQ39DpbiBWpsSpU222zpump 2026-09-27T00:06:26.342999Z         sol       0        0.0     0.0 harness_sample 0.006261      NaN           NaN         NaN          NaN
36hzDTd7Dtvd4FKgUWeuAins5XocXYonDTKttBj4pump 2026-09-27T00:08:58.894000Z         sol       1        0.0     1.0 harness_sample 0.217360      NaN           NaN         NaN          NaN
HYs3UpS6wUqw4PvPevKGmtz9KoBG3rnGrf8NxYJApump 2026-09-27T00:08:10.242000Z         sol       0        0.0     NaN harness_sample 4.289019      NaN           NaN         NaN          NaN
28cbuCAcAb1mmrG9VLMvQGo89mXGefoLnEkmiwXsS7hs 2026-09-27T00:14:52.714999Z         sol       0        0.0     0.0 harness_sample 0.604417      NaN           NaN         NaN          NaN

---

# chatgpt response

This is useful. We have enough evidence to separate the main dataset from the harness sample before proceeding.

## Step 4 — Interpretation

**The 620 `harness_sample` rows should remain separate for now.**

They all occur within the first 18 minutes and 30 seconds of September 27, 2026. Several fields, including `create_lag_s`, `silence_3s`, and `silence_60s`, are entirely missing in your examples. This makes the group unsuitable for mixing into our primary analysis until we understand how it was collected.

The main cohort is much larger:

<box border radius="lg" padding={3} gap={3}>
  <row align="center" gap={3}>
    <box flex="1" gap={1}>
      <text color="secondary" size="sm">Main cohort candidates</text>
      <title size="xl" color="default">241,109</title>
      <text color="secondary" size="xs">SOL-quoted tokens from `tape_replay`</text>
    </box>
    <icon name="database" size="2xl" color="success" />
  </row>
  <divider color="subtle" />
  <text size="sm">We'll use this cohort for the next audit, without deleting or changing any rows in the original `df`.</text>
</box>

## Step 5 — Audit the main cohort's features

**Goal:** Find out which feature_cols if c in sol_replay.columns]

missing = sol_replay[feature_cols].isna().mean()

print("\n=== Feature availability ===")
print(
    pd.DataFrame({
        "missing_rows": sol_replay[feature_cols].isna().sum(),
        "missing_pct": (missing * 100).round(2),
        "available_pct": ((1 - missing) * 100).round(2),
    }).sort_values("missing_pct", ascending=False).to_string()
)
</CodeBlock>

### What to send back

Paste the complete output. We'll use it to decide which columns are candidates for the initial observation space and which need to be excluded or investigated.

We are still in the data-audit stage; we haven't trained PPO or established that this dataset contains a profitable trading signal.

---

# you asked

=== Main cohort ===
Rows: 241109
Unique mints: 241109
First launch: 2026-09-27 00:19:00.184000+00:00
Last launch:  2026-10-02 23:59:56.721999+00:00

=== Launches per day ===
day
2026-09-27    34371
2026-09-28    38349
2026-09-29    38186
2026-09-30    43755
2026-10-01    44526
2026-10-02    41922

=== Outcome labels ===

graduated:
graduated
0.0    235859
1.0      5250

rugged:
rugged
0.0     65072
1.0    172238
NaN      3799

curve_complete:
curve_complete
0.0    234121
1.0      6988

decoder_complete:
decoder_complete
1    241109

=== Feature availability ===
                    missing_rows  missing_pct  available_pct
f10_rep_rug                82347        34.15          65.85
f10_rep_grad               82347        34.15          65.85
f60_age                    14264         5.92          94.08
f10_age                    14264         5.92          94.08
f10_dev_share              14264         5.92          94.08
f10_insider_share          14264         5.92          94.08
f10_rep_n                  14264         5.92          94.08
f10_bundle_wallets         14264         5.92          94.08
f10_rs                     14264         5.92          94.08
f10_n_buys                 14264         5.92          94.08
f60_rs                     14264         5.92          94.08
f60_insider_share          14264         5.92          94.08
dev_buy_sol                    0         0.00         100.00
mayhem                         0         0.00         100.00
dev_share                      0         0.00         100.00
create_lag_s                   0         0.00         100.00
silence_3s                     0         0.00         100.00
silence_60s                    0         0.00         100.00

---

# chatgpt response

Your main cohort looks structurally clean: **241,109 unique tokens, no missing values in the basic launch features, and complete graduation labels.** But we have two important findings before building an RL environment.

- `decoder_complete` is always `1`, so it provides no predictive information and should not be an observation feature.
- `f10_rep_rug` and `f10_rep_grad` are missing in 34.15% of rows, while `f10_rep_n` and most other early features are available in 94.08%. We need to understand this difference before handling missing values.

The graduation rate is $5,250/241,109 \approx 2.18\%$. The `rugged` label is missing for 3,799 tokens, so we must calculate its rate only among known labels.

## Step 6 — Audit outcomes and missing representative features

**Goal:** Check whether graduation and rug labels overlap, how outcomes vary by day, and whether missing representative-wallet statistics have a clear explanation.

Run this as **one new cell** in Colab.

<Codg"})
    .round(3)
)
</CodeBlock>

### What we're learning

The overlap table tests whether tokens can be labelled both graduated and rugged. The daily table helps us spot changes in outcomes or data coverage across this short six-day period. The final table tests whether missing representative-wallet statistics are associated with having zero or an unknown number of representative wallets.

One important limitation remains: these are **launch-level records, not a complete sequence of executable prices and trades**. Even if this audit passes, it does not yet establish that we can train PPO directly on this dataset. We will decide what the data can support after examining the results.

Paste the complete output of Step 6 here, and we'll interpret it before moving on.

---

# you asked

=== Overall outcome audit ===
Launches: 241109
Graduation rate: 2.177%
Rug label coverage: 98.424%
Rug rate among known labels: 72.579%
Curve completion rate: 2.898%

=== Graduated vs rugged ===
rugged (-1 = unknown)     -1.0    0.0     1.0
graduated (-1 = unknown)                     
0.0                       3786  60408  171665
1.0                         13   4664     573

=== Daily outcome audit ===
            launches  graduation_rate  rug_label_coverage  rug_rate_known  f10_coverage
day                                                                                    
2026-09-27     34371           0.0207              0.9952          0.7331        0.9652
2026-09-28     38349           0.0237              0.9933          0.7064        0.9828
2026-09-29     38186           0.0214              0.9879          0.7221        0.9734
2026-09-30     43755           0.0210              0.9413          0.7376        0.8468
2026-10-01     44526           0.0219              0.9966          0.7397        0.9298
2026-10-02     41922           0.0220              0.9953          0.7145        0.9628

=== Representative feature availability ===
f10_rep_n values:
count    226845.000
mean        377.088
std         928.670
min           0.000
25%           0.000
50%          18.000
75%         265.000
max        9323.000
Name: f10_rep_n, dtype: float64

f10_rep_rug missingness by f10_rep_n status (row fractions):
f10_rep_rug        rep_rug_present  rep_rug_missing
row_0                                              
missing                       0.00             1.00
positive_or_other             0.95             0.05
zero                          0.00             1.00

---

# chatgpt response

The main finding is that missing representative-wallet statistics are **structural, not random**: `f10_rep_rug` is missing for every row where `f10_rep_n` is zero or missing. Also, September 30 has an unusually sharp dip in both rug-label coverage and `f10` feature coverage. Next we should check **when each feature could have become available**, before treating any column as a model input.

Step 6 is complete. We found two important data-quality issues before moving toward PPO.

**First, the outcome labels overlap.** Of the 5,250 graduated tokens, 573 are also marked `rugged`. That is about 10.9% of graduates. We should preserve both labels until we understand their definitions rather than forcing them into mutually exclusive classes. The dataset documentation describes its labels as heuristics, not guarantees. ([Glama](https://glama.ai/mcp/servers/gosadu/loophole-tape/tree))
**Second, September 30 remains an anomaly.** Rug-label coverage fell to 94.13%, and `f10` coverage fell to 84.68%. We should investigate this before deciding how to handle missing values.

The representative-wallet fields also have structural missingness: `f10_rep_rug` is always missing when `f10_rep_n` is zero or missing. We should not automatically replace those values with zero.

## Step 7 — Inspect timestamps and potential data leakage

**Goal:** Understand which fields describe information available early in a token's life and which record events that happened later.

This distinction is crucial: if the agent sees a future rug event, final curve reserve, or eventual graduation status while deciding whether to buy, the backtest will be misleading.

Run this as one new cell in Colab.

<C_string(index=False)
)
</CodeBlock>

### What this step tells us

We are checking the actual timestamp formats and the distributions of event times before making assumptions about the fields.

For now, treat `graduated`, `rugged`, `migrate_dt_s`, `rug_dt_s`, `dev_first_sell_dt_s`, `peak_rs`, and `terminal_rs` as **potential outcome or future-information fields**, not RL observations. Some early features may eventually be usable, but their availability must match the exact decision time.

One important constraint remains: this dataset gives us one summary row per launch, not a complete sequence of trading states and executable prices. That means it may support a launch-selection model, but we have not established that it can support a faithful PPO trading environment on its own.

Paste the complete Step 7 output here. We'll interpret the timing fields before deciding the next step.

---

# you asked

=== Timestamp columns ===

t0
dtype: float64
missing: 0
examples:
[1790468340.184, 1790468375.464, 1790468381.115, 1790468386.548, 1790468387.775]

launched_at
dtype: object
missing: 0
examples:
['2026-09-27T00:19:00.184000Z', '2026-09-27T00:19:35.463999Z', '2026-09-27T00:19:41.115000Z', '2026-09-27T00:19:46.548000Z', '2026-09-27T00:19:47.775000Z']

curve_read_at
dtype: float64
missing: 0
examples:
[1790815204.2341704, 1790815204.2341704, 1790815204.2341704, 1790815204.2341704, 1790815204.2341704]

=== Timing field distributions ===

migrate_dt_s
Available: 6528 / 241109
count      6528.000
mean       1585.647
std       11843.120
min           0.000
1%            0.001
25%           0.008
50%          25.355
75%         341.357
99%       36098.392
max      337340.025

rug_dt_s
Available: 172238 / 241109
count    172238.000
mean        225.541
std        3729.801
min           0.000
1%            0.202
25%           9.003
50%          26.517
75%          77.144
99%        1289.184
max      274892.010

dev_first_sell_dt_s
Available: 189150 / 241109
count    189150.000
mean        344.344
std        4268.466
min           0.000
1%            0.189
25%           5.411
50%          23.020
75%          94.866
99%        3555.344
max      277918.409

create_lag_s
Available: 241109 / 241109
count    241109.000
mean          2.471
std          25.500
min          -0.011
1%            0.003
25%           0.035
50%           0.061
75%           0.099
99%          59.360
max        1174.365

silence_3s
Available: 241109 / 241109
count    241109.000
mean          0.008
std           0.126
min           0.000
1%            0.000
25%           0.000
50%           0.000
75%           0.000
99%           0.000
max           2.994

silence_60s
Available: 241109 / 241109
count    241109.000
mean          0.268
std           2.545
min           0.000
1%            0.000
25%           0.000
50%           0.000
75%           0.000
99%           3.852
max          59.006

f10_age
Available: 226845 / 241109
count    226845.000
mean          1.544
std           1.183
min           0.000
1%            0.020
25%           0.490
50%           1.050
75%           3.000
99%           3.000
max           3.000

f60_age
Available: 226845 / 241109
count    226845.000
mean         14.430
std           9.189
min          10.000
1%           10.000
25%          10.000
50%          10.490
75%          13.460
99%          54.570
max          60.000

=== Example outcome records ===
                                        mint                 launched_at  migrate_dt_s  rug_dt_s  dev_first_sell_dt_s   peak_rs  terminal_rs  graduated  rugged  curve_complete
CwEewAPjXrSDwL3qx1UdVPqHm9V9h4ppiBqHEa1cpump 2026-09-28T12:54:12.966000Z           NaN    27.962               27.962 10.699163 2.748170e-04        0.0     1.0             0.0
FQo1ie9LgiXDPfrBnye3RhUNG3fHxJTcuuRHv3M27YsA 2026-10-02T17:11:53.739000Z           NaN       NaN                  NaN  0.000000 0.000000e+00        0.0     0.0             0.0
DcF698i33AS4BKAfzXZq6mPSytuxiuLik5uPTHvrpump 2026-10-01T00:39:30.868000Z           NaN       NaN                  NaN  2.958395 1.954334e-01        0.0     0.0             0.0
2ST1soSuuYiHBcLsyo7wdWiyJwD3aXVgMRhVjppPk6uY 2026-09-29T20:04:24.443000Z           NaN       NaN                  NaN       NaN          NaN        0.0     NaN             0.0
8UjhZScVx3unKKFvRiLPg5fhJDM4PzeU8xsoyXkApump 2026-09-29T14:28:57.331000Z           NaN    61.929               61.929  0.592187 0.000000e+00        0.0     1.0             0.0
28vtko7bkPMGEsyJNHUTVoirMjR2ygkuyu6mR9NLpump 2026-09-30T06:26:41.318000Z           NaN     3.826                3.826  0.080824 1.000000e-09        0.0     1.0             0.0
B36YyWosQ5KuGiaqCF2CVz66xgJ9AjJJRnG98eiRpump 2026-09-30T02:56:28.266000Z           NaN    24.691               24.691  0.585695 2.398028e-02        0.0     1.0             0.0
9g7ZqFw3AzghEi12NgisJQVYJ6o1sTKyvZKygMpwpump 2026-10-01T08:41:19.680000Z           NaN   204.498              204.498 56.227768 9.786847e-02        0.0     1.0             0.0
4wEW44UUo88eXYQ3bcaRUUHz6WjafupV4JrF3t4Spump 2026-09-29T19:41:01.595000Z           NaN       NaN              377.823  0.495552 1.544242e-02        0.0     0.0             0.0
HHB5zPDFW11jm9kCJA1iCkdqvJZFnEajYaM6AbyZpump 2026-09-27T06:54:46.598999Z           NaN    56.091               56.091  0.364745 0.000000e+00        0.0     1.0             0.0

---

# chatgpt response

The timing audit reveals an important issue we need to resolve before choosing model inputs.

## Step 7 — Interpretation

**1. `t0` and `launched_at` agree.** The Unix timestamp `1790468340.184` corresponds to `2026-09-27 00:19:00.184 UTC`, matching the ISO timestamp. This is a good sign.

**2. `curve_read_at` needs investigation.** The example value `1790815204.234` corresponds to October 1, 2026, at 00:40:04 UTC. Yet our dataset contains launches through October 2. If that timestamp is intended to record when a curve was actually read, it cannot represent a post-launch reading for tokens launched after that time. We need to quantify this rather than assume the column is reliable.

**3. Event timing fields should not be model inputs yet.** `rug_dt_s`, `migrate_dt_s`, and `dev_first_sell_dt_s` appear to describe elapsed time until events. They are useful for outcome analysis but could leak future information into a model.

**4. The dataset remains a research starting point, not yet a PPO environment.** We still need point-in-time observations and price paths to simulate decisions and exits realistically. The dataset listing also warns of known issues, reinforcing the need to validate the schema. <Cite refs={["turn199312search0"]}/>

## Step 8 — Verify timestamp consistency

Run this single new cell in your existing Colab notebook. It checks whether `curve_read_at` is actually consistent with each token's launch time and whether rug timing coincides with the creator's first   int(delta_s.gt(0.001).sum()))
</CodeBlock>

### Send me the output

Paste all three sections. In particular, the percentage of curve reads occurring before launch will tell us whether the timestamp is usable as recorded or needs clarification from the dataset schema.

We will not filter rows or train anything yet. The next decision depends on these reslts.

---

# you asked

=== Launch timestamp consistency ===
Unique t0 timestamps: 241003
Rows differing by more than 1 second: 0
Maximum absolute difference (seconds): 9.98e-07

=== Curve-read timestamp audit ===
Unique curve_read_at timestamps: 2693
Earliest curve_read_at: 2026-10-01 00:40:04.234170437+00:00
Latest curve_read_at:   2026-10-06 06:50:37.862548828+00:00

Curve read before launch: 0
Curve read at or after launch: 241109
Percentage read before launch: 0.00%

Curve-read time minus launch time (seconds):
count    241109.00
mean     319882.94
std       26660.87
min      261692.07
1%       267280.82
25%      297819.65
50%      316919.67
75%      341788.24
99%      369094.27
max      370203.08

=== Rug and creator-sell timing ===
Rows with both timestamps: 168206
Exactly equal: 118726
Within 1 millisecond: 119255
Median difference (seconds): 0.0
Rug time earlier than creator first sell: 5914
Rug time later than creator first sell: 43037

---

# chatgpt response

The timestamp check resolves one concern and raises another: `t0` matches `launched_at` to within a microsecond, but `curve_read_at` is a later collection/read timestamp—roughly 3–4 days after launch for every row. The rug and creator-sell times also match exactly in many cases, so we should treat those fields as related label evidence, not independent signals. I’m checking the dataset’s published schema/issues before deciding the next small Colab check.

Step 8 is complete. The launch timestamps are consistent, but the other findings affect how we should prepare the data for modeling.

## What the results mean

**1. Launch time is reliable.** `t0` and `launched_at` agree to within one microsecond. The 106 repeated timestamp values do not indicate duplicate tokens: all 241,109 mints are unique.

**2. Exclude `curve_read_at` from the observation features for now.** Its median is about 3.67 days after launch, and the column has only 2,693 distinct timestamps across 241,109 rows. It appears to represent a later data-read or collection process, not a token's state at the moment you could have traded. I could not verify its exact semantics from the published schema, so we should not assume more than the output supports.

**3. Treat rug timing as potential label leakage.** In 118,726 rows, `rug_dt_s` and `dev_first_sell_dt_s` are exactly equal. That strong overlap suggests the fields may be related to the same events or labeling logic. Neither should be used as an input to predict whether a token will rug.

The dataset publisher describes this as a launch/outcome dataset with early features and explicitly warns that its labels are heuristic. That makes it useful for research, but we still need to verify which information would have been available at each decision time. <Cite refs={["turn680888search0"]}/>

## Step 9 — Check whether missing features introduce selection bias

**Goal:** Determine whether tokens with missing early features have different graduation and rug rates from tokens whose features are available.

This matters because simply deleting rows with missing values could bias the training set toward a particular type of token.

Run this as **one new cell** in your existing Colab notep_summary.round(4).to_string())
</CodeBlock>

### What we're looking for

If the graduation or rug rates differ sharply between available and missing groups, that tells us the missingness is associated with the observed outcomes. It does not prove the missing data caused those outcomes, but it warns us against blindly dropping rows.

After this check, we'll have a better basis for deciding whether to build a **supervised prediction baseline first** or move on to finding sequential data for the PPO environment. This dataset has one row per launch, not a complete series of trading states and executable prices, so it cannot yet support a faithful PPO trading simulation by itself.

Run Step 9 and paste its complete output. We'll analyze those results before adding another ell.

---

# you asked

=== Outcomes by f10_rs availability ===
                launches  graduation_coverage  graduation_rate  rug_coverage  rug_rate_known
feature_status                                                                              
available         226845                  1.0           0.0218        0.9839          0.7258
missing            14264                  1.0           0.0212        0.9899          0.7259

=== Outcomes by f60_rs availability ===
                launches  graduation_coverage  graduation_rate  rug_coverage  rug_rate_known
feature_status                                                                              
available         226845                  1.0           0.0218        0.9839          0.7258
missing            14264                  1.0           0.0212        0.9899          0.7259

=== Outcomes by f10_rep_rug availability ===
                launches  graduation_coverage  graduation_rate  rug_coverage  rug_rate_known
feature_status                                                                              
available         158762                  1.0           0.0059        0.9852          0.7715
missing            82347                  1.0           0.0523        0.9824          0.6375

=== Outcomes by f10_rep_n status ===
              launches  graduation_rate  rug_coverage  rug_rate_known
rep_n_status                                                         
missing          14264           0.0212        0.9899          0.7259
positive        167204           0.0058        0.9851          0.7416
zero             59641           0.0668        0.9805          0.6812

---

# chatgpt response

## Step 9 — Interpretation

The most important finding is that **missing representative-wallet features are strongly associated with token outcomes**. We should preserve that distinction when designing our model rather than filling every missing value with zero or deleting all incomplete rows.

### 1. Missing price-ratio features do not show much outcome bias

| Feature availability | Graduation rate | Rug rate among known labels |
|---|---:|---:|
| `f10_rs` available | 2.18% | 72.58% |
| `f10_rs` missing | 2.12% | 72.59% |

The rates are almost identical. That's reassuring, although it doesn't prove that missingness is harmless for every other feature or period.

### 2. Representative-wallet features tell a different story

<box border radius="lg" padding={3} gap={3}>
  <title size="md">Graduation rate by `f10_rep_n` status</title>
  <box gap={1}>
    <row align="center" justify="between">
      <text>Zero representative count</text>
      <title size="sm" color="default">6.68%</title>
    </row>
    <box background="surface-tertiary" radius="md" height="8px" clip>
      <box background="#0D9488" width="100%" height="8px" radius="md" />
    </box>
  </box>
  <box gap={1}>
    <row align="center" justify="between">
      <text>Missing representative count</text>
      <title size="sm" color="default">2.12%</title>
    </row>
    <box background="surface-tertiary" radius="md" height="8px" clip>
      <box background="#64748b" width="31.7%" height="8px" radius="md" />
    </box>
  </box>
  <box gap={1}>
    <row align="center" justify="between">
      <text>Positive representative count</text>
      <title size="sm" color="default">0.58%</title>
    </row>
    <box background="surface-tertiary" radius="md" height="8px" clip>
      <box background="#64748b" width="8.7%" height="8px" radius="md" />
    </box>
  </box>
  <text color="secondary" size="xs">These are observed rates, not evidence that the feature itself causes graduation.</text>
</box>

Tokens with a positive `f10_rep_n` have a much lower observed graduation rate than tokens with a zero count. A missing count forms a separate group with an intermediate rate.

This could reflect meaningful early trading activity, how representative wallets are defined, or dies
    if any(
        word in Path(f).name.lower()
        for word in [
            "readme",
            "issue",
            "schema",
            "datasheet",
            "manifest",
        ]
    )
    and Path(f).suffix.lower() in [".md", ".txt"]
]

print("=== Documentation files found ===")
for name in docs:
    print(name)
print()

# Read the dataset card and any separate issue documentation
selected = [
    f for f in docs
    if Path(f).name.lower() == "readme.md"
    or "issue" in Path(f).name.lower()
]

for name in selected:
    print("=" * 70)
    print("FILE:", name)
    print("=" * 70)

    local_path = hf_hub_download(
        repo_id=repo_id,
        filename=name,
        repo_type="dataset",
    )

    with open(local_path, "r", encoding="utf-8") as file:
        content = file.read()

    # Keep notebook output manageable
    print(content[:15000])

    if len(content) > 15000:
        print("\n[Output truncated; remaining characters:", len(content) - 15000, "]")

    print()
</CodeBlock>

### What to send me

Paste the output, especially any sections about known issues, label definitions, feature timing, and collection gaps.

**Our next objective is to establish a leakage-safe supervised baseline** using the launch-level dataset. We'll then decide what additional sequential price data is required for the PPO environment. This lets us learn whether the early features have predictive value before investing effort in reinforcement learning.

---

# chatgpt response

I've read the Colab output, including the dataset's `README.md` and `KNOWN_ISSUES.md`. We found several important issues that affect how we should prepare the data for machine learning.

## What we've learned

**1. Your current cohort is the right starting point for the next audit.** It contains 241,109 unique, SOL-quoted tokens from the `tape_replay` subset. The dataset documentation confirms that `tape_replay` features are reconstructed offline for launches in the covered days. <FileCite ref="turn1file0" line_range_start={200} line_range_end={228} />

**2. Mayhem and classic tokens need separate analysis.** Mayhem-mode tokens have very different graduation and rug-label rates. Moreover, a completed mayhem curve does not necessarily mean the token graduated. <FileCite ref="turn1file0" line_range_start={60} line_range_end={66} />

**3. September 30 has an outcome-data problem.** The maintainer documents a curve-path closure restart that left many launches unresolved, particularly during the early hours of September 30. For analyses using `rugged`, `peak_rs`, or `terminal_rs`, the documentation recommends excluding September 30 or explicitly modeling the missingness. <FileCite ref="turn1file0" line_range_start={105} line_range_end={115} />

**4. Missing early features require careful treatment.** A missing `f10_rep_rug` does not necessarily mean zero rug history. It can indicate that the creator has no earlier resolved launches, that the launch was not sampled, or that the snapshot is incomplete. <FileCite ref="turn1file0" line_range_start={257} line_range_end={273} />

One limitation: the output you pasted was truncated after issue KI-10. The documentation declares 17 issues, so we should read the remaining seven before designing the baseline.

## Step 1ting the document at KI-10.
start = issues_text.find("## KI-11")

if start == -1:
    print("Could not find KI-11. Please check the downloaded file.")
else:
    print(issues_text[start:])
</CodeBlock>

### What happens next?

After you paste the output, we'll finish the data audit and identify a defensible feature set for a **supervised baseline**. That lets us test whether launch-level information predicts outcomes before investing in PPO.

We still need sequential prices and realistic trade execution to train a meaningful RL trading agent. This launch dataset alone does not provide that complete environment.

---

# you asked

Documentation revision: 21be6aeb5d66721e3d40e34b09141f408e1e0ca0

## KI-11 negative_intervals

Columns: `rug_dt_s`, `migrate_dt_s`, `dev_first_sell_dt_s`, `f10_age`.

12 rows have a negative interval: `rug_dt_s` (5 rows, as low as -138 s), `migrate_dt_s` (1, -69 s), `dev_first_sell_dt_s` (4, -138 s), `f10_age` (8, -161 s). All fall on 2026-09-09: 11 of them are launches between 13:54:53 and 13:56:26 UTC and one at 14:55:17 UTC. Events for these mints carry times earlier than the `t0` the table holds: either the launch time was recorded late or the event times are early. We did not establish which.

What to do: drop these rows from timing analyses.

## KI-12 peak_above_curve_limit

Column: `peak_rs`.

A curve stops at about 85 SOL of real reserve. 31 rows have `peak_rs` above 85.1 SOL (23 above 86, maximum 89.95); a curve cannot hold that, so these peaks are measurement errors of unknown cause.

What to do: clip at 85.1 or drop.

## KI-13 labels_are_not_exclusive

Columns: `graduated`, `rugged`.

The DEV DUMP branch of the rug rule is judged inside the first 300 s of the launch, so a launch can be rugged and still graduate later. In this release 2,465 of the 24,606 graduated launches (10.0%) are also rugged. 22 graduated launches have a null `migrate_dt_s` (no migration or pool sighting was recorded for them).

Since 2026-10-01 two columns make this explicit: `rugged_not_graduated` (1 exactly for the rugged launches that did not graduate) and `rug_branch_inferred` (`drain` on 232,379 of the 671,283 rugged rows, `dev_dump_or_recovered` on 438,904: most rugs are creator dumps on small curves, not drained pools). The branch is inferred from the stored terminal state, because the launch table keeps the flag without its branch.

What to do: do not use `rugged` as the opposite of `graduated`; decide which one your question needs, and read `rug_branch_inferred` before calling a rug a drained pool.

## KI-14 creator_text_is_untrusted

Columns: `name`, `symbol`, `uri`.

These fields are text that token creators wrote on-chain. We did not filter or review them, apart from the e-mail addresses removed in KI-17: expect offensive language, advertising and links to scams. In this release: 40 empty names and 54 empty symbols; control characters in 6 names and 3 symbols; line breaks in 316 names and 202 symbols; non-ASCII characters in 22,609 names (2.0%) and 15,001 symbols; a link (http, www or t.me) inside 78 names and 39 symbols; `uri` null on 5,963 rows (0.5%) and empty on 134, otherwise up to 200 characters (schemes: https 1,119,480, ipfs 1,964, http 1,070, data 30, none recognised 239). At least 20 names read as instructions to an AI assistant (found with a simple pattern, so there may be more); for example one of them begins with "IGNORE ALL". The fields also carry third-party identifiers that the creators published themselves: @handles in 374 names and 204 symbols, and an x.com or twitter.com link in 22 names (simple patterns, so the counts are lower bounds); these are kept. 7 names were an e-mail address; they are replaced by `[e-mail removed]` in this copy (KI-17).

What to do: never pass these fields to a language model as instructions or inside a prompt without delimiting them as data; filter or review them and escape them before display; do not fetch `uri` without sandboxing.

## KI-15 curve_account_read_on_2026-09-30

Columns: `curve_complete`, `mayhem` (where the account was read), `quote_asset`, `quote_mint`, `holder_reward`, `creator_fee_bps`, `curve_read_at`.

The curve accounts were read between 2026-09-30 15:07:29 UTC and 2026-10-06 06:50:37 UTC (each row carries its own read time, `curve_read_at`), so these columns describe the state at the read, not at launch. The quote asset, the layout and the mayhem flag do not change after launch; `complete` can change from 0 to 1 later for a curve that was still open at the read. Every launch of this release was at least 3 days old at the read, which leaves few such curves; we have not counted them. 19 rows were not read.

What to do: use `curve_read_at` when you need the time of the read.

## KI-16 two_files_rewritten

The day files of 2026-08-31 and 2026-09-01 store the all-null early-feature columns as the arrow `null` type in the API's copies, which the Hugging Face loader cannot merge with the float columns of the other days. The files in this repository were rewritten with those columns as float64; every value is the same (checked column by column against the API's files). Their sha256 differs from the API's for these two files. The day files of KI-17 differ from the API's too; the other 27 day files are byte for byte the API's.

What to do: nothing.

## KI-17 email_addresses_removed

Column: `name`.

7 `name` values were nothing but an e-mail address. In this copy each of them is replaced by `[e-mail removed]`. This is the one edit made to creator-written text: every other value of these rows, and every other row, is as in the API's day files. The rows (mint, launch day):

- `5P31ydUZQhitm7imucSA2nKgzfFnpQ92pAxWNYLDpump` (launched 2026-09-03)
- `4YzKoZivG5jc2gDLWAS6CHCXiMj1EN3sViUonhaNpump` (launched 2026-09-03)
- `q8n6JSjFBhczgfgH3aw8LRTLuWhxmHX5FHhsKKUpump` (launched 2026-09-05)
- `98EE8oTFxbZCncJEgS5oAudQ7t7wawnq6VJvXhhWpump` (launched 2026-09-05)
- `2Gx3KNFRy3UxdrLSdKQ91hznYz3t9EZUaFJXGrbSpump` (launched 2026-09-05)
- `nEvRFGEdvVWh5vHMXZnZz3RAoorF9kYfNwSJkKSpump` (launched 2026-09-24)
- `9q9je5Vht4QYXVWG2BL8bMNqVtYw2J7itzaig5CKpump` (launched 2026-09-25)

The sha256 of the day files 2026-09-03 (2 rows), 2026-09-05 (3 rows), 2026-09-24 (1 row) and 2026-09-25 (1 row) therefore differs from the API's files; the API's files and the chain keep the original text, so a join by mint with the API's data shows these 7 names as different. The addresses were found with a standard e-mail pattern (`name@domain.tld`); obfuscated forms such as "name at domain dot com" are not caught. `symbol` and `uri` hold no e-mail address in this release.

What to do: nothing; read `[e-mail removed]` as a missing name.

## graduation_pools

- P-1 coverage window: the recorder's store begins at 2026-09-23 11:10:21 UTC, so pools of earlier graduations have no row, and 2026-09-23 is a partial day (599 pools on 2026-09-23 against 1,085 on 2026-09-24). A pool opened but not followed for its 30 minutes would show `complete` = 0; every row here is 1.
- P-2 `open_reserve_lam` is the SOL reserve after the first trade the recorder saw inside the 30 minutes, not at the migration; `reserve_30m_lam` is the reserve after the last trade inside the window, not a snapshot at minute 30. `price_ratio_30m` is the price at that last trade over the price at the first trade. 3,034 pools opened with under 50 SOL and 113 have fewer than 5 trades; the full-pool filter drops them, and their price ratios are noisy.
- P-3 `pool` is null on 399 rows (3.5%): the migration record had no pool address. We did not establish why.
- P-4 `open_t` changes meaning on 2026-09-29 at 10:56:23 UTC (KI-07). This release ends 2026-10-02.
- P-5 `drain70_t` is set when the reserve first stands at or below 70% of its own running peak, which happens in 6,659 of the 8,305 full pools (80.2%): it is a fact about the reserve path, not a signal. The project's own look at the relation between that flag and later collapse used nine cells and is not validated; do not read it as a forecast.

## Notes for modelling

- The two subsets are two recorder regimes. Use `launches` (decoder complete) for buy-derived features and the inputs of the rug rule; use either subset for launch counts, creators, outcomes and the graduation label; do not pool them without `decoder_complete`.
- Split by time, never at random. There are 254,630 creators; the largest has 6,915 launches, the top 100 creators launched 14.3% of all rows, and 189,995 creators launched once.
- Know which columns are outcomes. Known at or just after launch: `creator`, `t0`, `name`, `symbol`, `uri`, `mayhem`, `quote_asset`, `quote_mint`, `holder_reward`, `creator_fee_bps`, `dev_buy_sol`, `dev_share`. Early features, with their age given: `f10_*`, `f60_*`. Outcomes and later reads, never features: `graduated`, `migrate_dt_s`, `rugged`, `rug_dt_s`, `dev_first_sell_dt_s`, `peak_rs`, `terminal_rs`, `curve_complete`, `curve_read_at`.
- Pick the label for your question: `graduated`, `curve_complete`, `rugged`, `rug_dt_s <= 300` answer different questions (KI-04, KI-09, KI-13).
- Rows with features and rows without them are different populations (KI-01); report both.
- Run the checks of KI-08 and KI-11 before any timing or rug-rate result on the first days of September.

---

# chatgpt response

Excellent. We've now read all 17 documented issues, and we can make a more defensible plan for the first model.

## Step 11 — Final conclusions from the documentation

The documentation confirms several important decisions. <FileCite ref="turn1file0" line_range_start={278} line_range_end={285} />

- **Use `graduated` as our first prediction target.** It measures graduation under the dataset's rules. It is different from `curve_complete`, which is read from the chain later and can change.
- **Separate classic launches from mayhem launches.** The maintainer reports very different graduation rates between them, so combining them could obscure the patterns we're trying to learn. <FileCite ref="turn1file0" line_range_start={60} line_range_end={66} />
- **Keep outcomes out of the input features.** This includes `graduated`, `rugged`, `rug_dt_s`, `migrate_dt_s`, `peak_rs`, `terminal_rs`, and `curve_complete`.
- **Split training and testing chronologically**, not randomly. Repeated creators can otherwise appear in both sets and make the model appear more general than it is. <FileCite ref="turn1file0" line_range_start={289} line_range_end={291} />

Our current cohort is useful because it contains post-decoder-fix launches from September 27 through October 2, 2026. We should now check the graduation base rate separately for classic and mayhem tokens.

## Step 12 — Compare classic versus mayhem launches

**Goal:** Establi,
        sol_replay["rugged"].fillna(-1),
        rownames=["mayhem", "graduated"],
        colnames=["rugged (-1 = unknown)"],
    ).to_string()
)
</CodeBlock>

### What to send back

Paste the complete output. Then we'll decide whether to build the first supervised baseline on classic launches only and choose a chronological train/validation/test split.

We're not training PPO yet. First, we need to determine whether the launch features carry a useful signal for even the simpler graduation-prediction problem.

---

# you asked

=== Cohort verification ===
Rows: 241109
Decoder versions:
decoder_complete
1    241109

=== Outcome rates by launch type ===
                    launches  graduations  graduation_rate  rug_label_coverage  rug_rate_known  f10_coverage
Classic (mayhem=0)    168848       5241.0           0.0310              0.9820          0.6514        0.9391
Mayhem (mayhem=1)      72261          9.0           0.0001              0.9895          0.8984        0.9450

=== Graduation vs rug label by launch type ===
rugged (-1 = unknown)  -1.0    0.0     1.0
mayhem graduated                          
0      0.0             3028  53146  107433
       1.0               13   4658     570
1      0.0              758   7262   64232
       1.0                0      6       3

---

# chatgpt response

Great. This result confirms that **we should start with classic launches only** for our first supervised baseline.

## Step 12 — Interpretation

<box border radius="lg" padding={3} gap={3}>
  <row align="center" gap={3}>
    <box flex="1" gap={1}>
      <text color="secondary" size="sm">Classic launches</text>
      <title size="2xl" color="default">168,848</title>
      <text color="secondary" size="sm">5,241 graduated · 3.10%</text>
    </box>
    <icon name="check-circle" color="success" size="xl" />
  </row>
  <divider color="subtle" />
  <row align="center" gap={3}>
    <box flex="1" gap={1}>
      <text color="secondary" size="sm">Mayhem launches</text>
      <title size="2xl" color="default">72,261</title>
      <text color="secondary" size="sm">9 graduated · 0.012%</text>
    </box>
    <icon name="git-compare" size="xl" color="secondary" />
  </row>
</box>

Three conclusions follow.

**First, separate the market regimes.** Mayhem launches have a very different outcome distribution. We'll exclude them from our initial graduation model, rather than expecting a single model to learn both behaviors.

**Second, graduation is a rare event.** About 97 out of every 100 classic launches do not graduate. A model that predicts “no graduation” for every token would achieve roughly 96.9% accuracy. Therefore, accuracy alone will be a misleading metric.

**Third, graduation is only our first prediction target.** Predicting graduation does not necessarily mean predicting a profitable trade. Later we will need to evaluate entry price, exit price, transaction costs and the opportunity to sell.

The dataset documentation also confirms that `graduated` and `rugged` are independent labels, so we will not combine them into a single success/failure target. <FileCite ref="turn1file0" line_range_start={278} line_range_end={285} />

## Step 13 — Prepare the chronological split

**Goal:** Define the first tsol",
    "dev_share",
    "f10_rs",
    "f10_n_buys",
    "f10_insider_share",
    "f10_bundle_wallets",
    "f10_rep_n",
    "f10_rep_rug",
    "f10_rep_grad",
    "f10_age",
]

feature_cols = [
    c for c in feature_cols if c in classic.columns
]

missing_pct = (
    classic.groupby("split", sort=False)[feature_cols]
    .agg(lambda s: s.isna().mean() * 100)
    .round(2)
)

print("=== Feature missingness by split (%) ===")
print(missing_pct.to_string())
print()

# 4) Confirm that every row belongs to exactly one intended split
print("Unassigned rows:", (classic["split"] == "unassigned").sum())
print("Unique mints:", classic["mint"].nunique())
print("Duplicate mints:", classic["mint"].duplicated().sum())
</CodeBlock>

### What I need from you

Paste the complete output of Step 13. We'll verify the class balance and feature coverage across the splits before building the first baseline.

We will begin with a simple supervised model and compare it against the always-negative baseline. Only after that test is sound should we move toward a PPO environment.

---

# you asked

=== Split summary ===
            launches  known_labels  graduations  graduation_rate  label_coverage
split                                                                           
train         108231        108231       3348.0           0.0309             1.0
validation     30781         30781        973.0           0.0316             1.0
test           29836         29836        920.0           0.0308             1.0

=== Daily graduation rates ===
            launches  graduations  graduation_rate
day                                               
2026-09-27     24165        712.0           0.0295
2026-09-28     27914        903.0           0.0323
2026-09-29     26946        816.0           0.0303
2026-09-30     29206        917.0           0.0314
2026-10-01     30781        973.0           0.0316
2026-10-02     29836        920.0           0.0308

=== Feature missingness by split (%) ===
            dev_buy_sol  dev_share  f10_rs  f10_n_buys  f10_insider_share  f10_bundle_wallets  f10_rep_n  f10_rep_rug  f10_rep_grad  f10_age
split                                                                                                                                       
train               0.0        0.0    6.38        6.38               6.38                6.38       6.38        47.02         47.02     6.38
validation          0.0        0.0    7.50        7.50               7.50                7.50       7.50        42.95         42.95     7.50
test                0.0        0.0    3.60        3.60               3.60                3.60       3.60        39.87         39.87     3.60

Unassigned rows: 0
Unique mints: 168848
Duplicate mints: 0

---

# chatgpt response

Your split looks good for a first experiment. The graduation rate is remarkably stable across the six days: **2.95%–3.23%** for classic launches. Feature coverage also varies by day, so we need to measure model performance separately on validation and test.

We'll now train our **first supervised baseline**, before PPO.

## Step 14 — Train a first graduation-prediction model

<text color="secondary" size="sm">Objective: predict whether a classic SOL-quoted token will graduate, using only launch-time and early-life features.</text>

We'll use `HistGradientBoostingClassifier` from scikit-learn. It handles missing numeric values natively, so we don't need to discard tokens just because their early snapshots are incomplete.

We'll deliberately leave out `f10_rep_rug` and `f10_rep_grad` for now. We need to verify their point-in-time availability before relying on previous creator outcomes as model inputs. We'll also exclude all final outcome fields and collection diagnosti X_val, y_val)
evaluate_model("Test — October 2", X_test, y_test)
</CodeBlock>

### How to understand the results

**Average precision (AP)** is especially important because only about 3% of these tokens graduate. Compare the model's AP with the no-skill reference, approximately the graduation rate.

**ROC-AUC** measures how well the model ranks graduates above non-graduates. A score around 0.5 indicates no useful ranking ability.

**Top 1%, 3% and 5% precision** measure the graduation rate among the model's highest-ranked tokens. Lift compares that rate with the overall graduation rate. For example, 2× lift means twice as many graduates per selected token as the baseline rate.

Remember, these metrics evaluate graduation prediction, **not trading profitability**. A token that graduates can still be a poor trade at your entry price.

The validation and test results should be broadly consistent before we trust the signal. Because the test covers only one day, we should treat it as an initial check rather than definitive out-of-sample proof.

Run Step 14 and paste the complete output. We'll interpret the metrics before deciding whether to improve the baseline or investigate additional data.

---

# you asked

=== Training setup ===
Features: ['dev_buy_sol', 'dev_share', 'f10_rs', 'f10_n_buys', 'f10_insider_share', 'f10_bundle_wallets', 'f10_rep_n', 'f10_age']
Train rows: 108231
Validation rows: 30781
Test rows: 29836
Training graduation rate: 3.093%

Model training complete.

=== Validation — October 1 ===
Graduation rate: 3.161%
Average precision (AP): 0.7415
ROC-AUC: 0.9381
Brier score (lower is better): 0.01173
No-skill AP reference: 0.0316
No-skill ROC-AUC reference: 0.5000

Top 1%: precision=100.000%, recall=31.655%, lift=31.64x
Top 3%: precision=70.563%, recall=67.009%, lift=22.32x
Top 5%: precision=45.909%, recall=72.662%, lift=14.52x

=== Test — October 2 ===
Graduation rate: 3.084%
Average precision (AP): 0.7308
ROC-AUC: 0.9304
Brier score (lower is better): 0.01232
No-skill AP reference: 0.0308
No-skill ROC-AUC reference: 0.5000

Top 1%: precision=100.000%, recall=32.500%, lift=32.43x
Top 3%: precision=67.746%, recall=65.978%, lift=21.97x
Top 5%: precision=45.643%, recall=74.022%, lift=14.80x

---

# chatgpt response

These are exceptionally strong results for a problem where only about 3% of tokens graduate. The model achieved **0.7308 average precision on October 2**, compared with a 0.0308 no-skill reference. It also selected a top 1% group with 100% observed graduation precision on both validation and test.

That's promising, but we must investigate before trusting it. One plausible explanation is that `f10_rs` reveals how far a token's bonding curve has already progressed toward graduation. That could be legitimate early information, but it would not necessarily translate into a profitable entry. The dataset defines `f10_*` as early-life snapshot features, generally recorded within the first 10 seconds. <FileCite ref="turn1file0" line_range_start={257} line_range_end={267} />

## Step 15 — Sanity-check the model

**Goal:** Find out whether the performance comes from early reserve information, other features, or a possible implementation problem.

We will compare three models on the same validation day:

- **Launch-only:** `dev_buy_sol` and `dev_share`.
- **Without `f10_rs`:** all other features from our current model.
- **Full model:** all eight original features.

We'll also train a negative-control model using shuffled training labels. It should perform close to random on validation data.

Run }")
print("Expected no-skill ROC-AUC: approximately 0.5000")
</CodeBlock>

### How we'll interpret the results

If removing `f10_rs` causes performance to collapse, the model relies heavily on early reserve information. That could be a real signal, but we must examine whether it is actionable at the time represented by the snapshot.

If launch-only features perform well, the initial creator-buy characteristics may carry useful predictive information even before early trading activity is observed.

The shuffled-label control should have average precision near the validation graduation rate and ROC-AUC near 0.5. If it does not, we'll investigate the implementation before continuing.

**Important:** October 2 has already been used for evaluation, so we should reserve a genuinely later period for a final test when we obtain more data. We will not train PPO yet; first we need to establish that this predictive signal is real and available before a trading decision.

Run Step 15 and paste the complete output.

---

# you asked

=== Validation baseline ===

Prior baseline
Average precision: 0.0316
ROC-AUC: 0.5000
Brier score: 0.03061

Launch-only
Average precision: 0.5835
ROC-AUC: 0.8604
Brier score: 0.01734

Without f10_rs
Average precision: 0.7427
ROC-AUC: 0.9365
Brier score: 0.01171

Full model
Average precision: 0.7415
ROC-AUC: 0.9381
Brier score: 0.01173

Shuffled-label negative control
Average precision: 0.3457
ROC-AUC: 0.7431
Brier score: 0.03038

Validation graduation rate: 3.1610%
Expected no-skill ROC-AUC: approximately 0.5000

---

# chatgpt response

The ablation results are promising, but **we have a failed sanity check, so we must not trust the model yet**.

The problem is the shuffled-label control:

| Validation metric | Prior baseline | Shuffled-label model |
|---|---:|---:|
| Average precision | 0.0316 | **0.3457** |
| ROC-AUC | 0.5000 | **0.7431** |
| Brier score | 0.03061 | 0.03038 |

A model trained on genuinely randomized labels should not achieve that ranking performance on the untouched validation labels. We don't know the cause yet; we should check the permutation and data alignment before drawing conclusions.

The ablation results themselves are interesting: removing `f10_rs` barely changes performance, while launch-only features already achieve AP of 0.5835. But those results remain provisional until the control passes.

## Step 16 — Fix and repeat the negative control

We'll use NumPy's explicit random permutation, reset the DataFrame indexes, and repeat the experiment with three independent random seeds. This helps rule out a notebook-state or row-alignment problem.

Run this as **one new cell** in Colab.

<CodeBlock lang  print()
</CodeBlock>

### What we expect

Each seed should produce a label correlation close to zero, validation AP reasonably close to the 3.16% graduation rate, and ROC-AUC around 0.5. Small variations are normal.

If the results again show high AP or high ROC-AUC, we should investigate further rather than continuing to optimize the model.

Paste the complete output. We'll resolve this before moving on to feature engineering or PPO.

---

# you asked

=== Data alignment ===
Training feature rows: 108231
Training labels: 108231
Validation feature rows: 30781
Validation labels: 30781
Original training graduation rate: 3.0934%
Validation graduation rate: 3.1610%

=== Shuffled-label control: seed 11 ===
Shuffled training graduation rate: 3.0934%
Correlation: original vs shuffled labels: -0.00048
Validation average precision: 0.0415
Validation ROC-AUC: 0.5521

=== Shuffled-label control: seed 42 ===
Shuffled training graduation rate: 3.0934%
Correlation: original vs shuffled labels: -0.00233
Validation average precision: 0.0286
Validation ROC-AUC: 0.3220

=== Shuffled-label control: seed 2026 ===
Shuffled training graduation rate: 3.0934%
Correlation: original vs shuffled labels: 0.00291
Validation average precision: 0.0294
Validation ROC-AUC: 0.3818

---

# chatgpt response

The shuffled-label check is partly reassuring, but **we haven't fully cleared the sanity check yet**.

Your permutation worked: the original and shuffled training labels have correlations close to zero. The average precision scores are also close to the 3.16% validation graduation rate, so the negative-control models aren't showing consistent predictive skill.

However, ROC-AUC varies from **0.322 to 0.552** across the three random seeds. That is unusually inconsistent. It doesn't automatically prove data leakage, but we should understand the score distributions before trusting the original model's AP of 0.7415.

## Step 17 — Inspect the control model's predictions

We'll inspect one shuffled-label model and compare it with truly random ranking scores. This will help us distinguish unusual model behavior from a problem with the metric calculations.

Run this as one new cell in Colab.

<mean(random_aucs)), 4))
</CodeBlock>

### What we'll check

The independent random rankings should average close to the validation prevalence for AP and 0.5 for ROC-AUC. The shuffled-label model should not show consistent predictive skill.

Paste the complete output. We'll resolve this diagnostic before moving on to the model's feature importance or any trading simulation.

---

# you asked

=== Model and probability checks ===
Model classes: [0 1]
Validation prevalence: 0.03161
Mean predicted probability: 0.03095
Min / median / max probability: [0.021178 0.031133 0.074237]
Distinct probabilities (rounded to 8 decimals): 558

=== Scores against the real validation labels ===
Average precision: 0.0286
ROC-AUC: 0.322
ROC-AUC with reversed score: 0.678

Mean prediction for actual graduates: 0.030113
Mean prediction for actual non-graduates: 0.030977

=== Independent random-ranking reference ===
Random-ranking AP values: [0.0321 0.0315 0.0315 0.0332 0.0314]
Random-ranking ROC-AUC values: [0.5078 0.4973 0.5004 0.5086 0.4953]
Mean random-ranking AP: 0.0319
Mean random-ranking ROC-AUC: 0.5019

---

# chatgpt response

The metric implementation looks correct: five independent random rankings produced AP near 0.0319 and ROC-AUC near 0.502. The unusual result is specifically the model trained on shuffled labels.

For that control, the model assigns **lower scores to actual graduates than to non-graduates**, despite training on randomized labels. This does not by itself prove leakage. A gradient-boosting model can overfit random labels, and its out-of-sample ranking can be unstable when feature distributions shift.

Our original model remains promising, but let's quantify that uncertainty using multiple shuffled-label runs before moving on.

## Step 18 — Measure the permutation baseline

We'll train 10 models on independently shuffled training labels, all evaluated on the same October 1 validation set. Then we'll compare the distribution with the original model's validation scores.

Run this as one new cell in Colab.

C_AUC"]).sum()), "/ 10")
</CodeBlock>

### How we'll interpret this

The key question is whether the real-label model's AP and ROC-AUC are far above the distribution produced by shuffled labels. If they are, that strengthens the case that the features contain genuine predictive information.

Ten permutations are a diagnostic, not a formal proof of significance. Once this check is complete, we'll investigate which features drive the original model's performance and whether their information is available at a realistic trading decision time.

Paste the complete output of Step 18, and we'll continue from there.

---

# you asked

=== Individual results ===
        run     AP  ROC_AUC
real_labels 0.7415   0.9381
  shuffle_1 0.0270   0.3666
  shuffle_2 0.0370   0.5092
  shuffle_3 0.0319   0.4116
  shuffle_4 0.0234   0.1805
  shuffle_5 0.0240   0.2280
  shuffle_6 0.0956   0.4836
  shuffle_7 0.0359   0.3801
  shuffle_8 0.0679   0.6733
  shuffle_9 0.0765   0.6017
 shuffle_10 0.0276   0.3032

=== Shuffled-label distribution ===
            AP  ROC_AUC
mean    0.0447   0.4138
std     0.0257   0.1568
min     0.0234   0.1805
median  0.0339   0.3958
max     0.0956   0.6733

=== Original model vs permutation controls ===
Original AP: 0.7415
Original ROC-AUC: 0.9381
Shuffled runs with AP >= original: 0 / 10
Shuffled runs with ROC-AUC >= original: 0 / 10

---

# chatgpt response

The results strongly support a real predictive relationship in the features, although they do not yet rule out every form of leakage.

## Step 18 — Interpretation

<box border radius="lg" padding={3} gap={3}>
  <title size="lg">Real labels vs. shuffled labels</title>
  <row align="center" gap={3}>
    <box flex="1" gap={1}>
      <text color="secondary" size="sm">Real-label validation AP</text>
      <title size="2xl" color="success">0.7415</title>
    </box>
    <box flex="1" gap={1}>
      <text color="secondary" size="sm">Mean shuffled-label AP</text>
      <title size="2xl">0.0447</title>
    </box>
  </row>
  The real-label model's average precision is about **16.6 times** the mean from the ten shuffled-label runs. None of those runs approached its 0.7415 AP.
</box>

Three conclusions:

1. **There is a strong signal worth investigating.** The real-label model ranks likely graduates far better than the shuffled-label controls.
2. **The controls are still noisy.** Their ROC-AUC ranges from 0.1805 to 0.6733. This suggests unstable, sometimes inverted rankings under random labels. It does not by itself establish leakage, but the control is not perfectly behaved.
3. **We should investigate feature reliance next.** The earlier ablation found that removing `f10_rs` barely changed AP, while the launch-only model still achieved 0.5835 AP. The strongest information may therefore come from other launch-time and early-life features.

The dataset documentation defines these early features as snapshots from the token's first seconds of life, while graduation fields describe later outcomes. We need to confirm that any useful signal was available at the time we could realistically enter a trresults).sort_values(
    "AP_drop_mean", ascending=False
)

print("=== Feature permutation importance ===")
print(importance.round(4).to_string(index=False))
print()

print("Interpretation:")
print("- Larger positive AP_drop_mean means greater model reliance.")
print("- Near-zero importance can mean a feature adds little unique information.")
print("- Negative importance means shuffling improved AP in this experiment.")
</CodeBlock>

### What to send back

Paste the complete output. We'll use it to identify the most influential features and decide which deserve deeper timing and leakage checks.

One caution: highly correlated features can substitute for one another, so permutation importance measures the model's reliance on each feature individually—not its full causal or economic value. This step is diagnostic, not proof of trading profitability.

---

# you asked

Baseline AP: 0.7415
Baseline ROC-AUC: 0.9381

=== Feature permutation importance ===
           feature  baseline_AP  AP_after_shuffle_mean  AP_drop_mean  AP_drop_std  AUC_drop_mean
            f10_rs       0.7415                 0.1216        0.6199       0.0034         0.1633
 f10_insider_share       0.7415                 0.7207        0.0208       0.0045         0.0091
       dev_buy_sol       0.7415                 0.7257        0.0157       0.0005         0.0051
         dev_share       0.7415                 0.7305        0.0110       0.0011         0.0036
           f10_age       0.7415                 0.7373        0.0042       0.0002         0.0012
         f10_rep_n       0.7415                 0.7374        0.0041       0.0015         0.0029
        f10_n_buys       0.7415                 0.7417       -0.0003       0.0007         0.0002
f10_bundle_wallets       0.7415                 0.7428       -0.0013       0.0008         0.0006

Interpretation:
- Larger positive AP_drop_mean means greater model reliance.
- Near-zero importance can mean a feature adds little unique information.
- Negative importance means shuffling improved AP in this experiment.

---

# chatgpt response

The feature-importance result gives us a clear lead: **`f10_rs` dominates the current model's predictions.**

| Feature | AP after shuffling | AP decrease |
|---|---:|---:|
| `f10_rs` | 0.1216 | **0.6199** |
| `f10_insider_share` | 0.7207 | 0.0208 |
| `dev_buy_sol` | 0.7257 | 0.0157 |
| `dev_share` | 0.7305 | 0.0110 |

There is an interesting detail: retraining without `f10_rs` retained almost the same AP, at 0.7427. This isn't necessarily contradictory. Permutation importance measures how much the *existing model* relies on a feature, while retraining lets the model discover alternative relationships in the remaining features.

The next question is whether `f10_rs` remains predictive when we restrict the evaluation to snapshots with better timing and capture quality.

## Step 20 — Validate the early-reserve signal

The dataset documentation defines `f10_rs` as the curve's real SOL reserve at an early snapshot. It also warns that capture delays above one second and interruptions in the first three seconds can compromise early features. <FileCite ref="turn1file0" line_range_start={265} line_range_end={273} />

Run this single cell in yo f"{roc_auc_score(y_part, probabilities):.4f}",
    )
</CodeBlock>

### What we're trying to establish

First, the decile table will show whether graduation rates rise consistently with early SOL reserve. Second, the clean-subset evaluation will show whether the model retains its predictive ability on launches with better early-data quality.

Even if both checks look good, the model predicts graduation—not profitable trades. We still need to test entry prices, exits, slippage, fees and missed opportunities before deciding whether this signal can help a trading strategy.

Paste the complete output of Step 20, and we'll interpret it before proceeding.

---

# you asked

=== Snapshot quality by split ===
            launches  f10_coverage  create_lag_over_1s  silence_3s_positive  clean_snapshot_share  graduation_rate  clean_graduation_rate
split                                                                                                                                    
train         108231        0.9362              0.0638               0.0042                0.9344           0.0309                 0.0309
validation     30781        0.9250              0.0750               0.0042                0.9213           0.0316                 0.0322
test           29836        0.9640              0.0360               0.0058                0.9604           0.0308                 0.0310

=== Graduation rates by f10_rs decile ===
                launches  reserve_min  reserve_median  reserve_max  graduations  graduation_rate
reserve_decile                                                                                  
1                  18435       0.0000          0.0000       0.0000         27.0           0.0015
2                  13458       0.0000          0.0010       0.0099          1.0           0.0001
3                  15694       0.0099          0.0501       0.1481         13.0           0.0008
4                  15838       0.1481          0.3467       0.5030         17.0           0.0011
5                  15892       0.5030          0.8296       1.0716         30.0           0.0019
6                  15901       1.0716          1.5000       1.9790         74.0           0.0047
7                  15775       1.9790          2.6864       3.7953        120.0           0.0076
8                  15900       3.7954          5.2054       6.9136        240.0           0.0151
9                  15814       6.9136          8.6849      10.7656        404.0           0.0255
10                 15854      10.7659         15.2959      85.0055       4012.0           0.2531

=== Validation performance by snapshot quality ===

All validation rows
Rows: 30781
Graduation rate: 3.161%
Average precision: 0.7415
ROC-AUC: 0.9381

Clean early snapshots
Rows: 28360
Graduation rate: 3.219%
Average precision: 0.7589
ROC-AUC: 0.9453

---

# chatgpt response

Step 20 gives us a strong signal, but it also reveals the next issue we need to resolve: **the model may be identifying tokens that have already progressed very far along their bonding curve, rather than finding an actionable entry opportunity.**

## Step 20 — Interpretation

Your early-reserve results are striking.

decile has a **25.31% graduation rate**, versus approximately 3.1% across the full classic cohort. Graduation rates generally increase with reserve, with a particularly large jump in the highest decile.

The clean-snapshot validation subset also performs better:

| Metric | All validation rows | Clean snapshots |
|---|---:|---:|
| Average precision | 0.7415 | 0.7589 |
| ROC-AUC | 0.9381 | 0.9453 |

This supports further investigation, but it does not establish that the model can earn money. The dataset's `f10_age` field records snapshot age, and the documentation warns that event-timing fields can have different meanings across the recorder restart on September 29. <FileCite ref="turn1file0" line_range_start={96} line_range_end={104} /><FileCite ref="turn1file0" line_range_start={257} line_range_end={273} />

## Step 21 — Check whether the snapshot comes before graduation

**Goal:** Check whether the early snapshot was observed before or after the migration event for tokens that eventually graduated.

This is our next critical check. A feature can be measured only a few seconds after launch and still be too late to use for entering a bonding-curve trade.

We'll restrict this audit to classic launches created **on or after September 29, 2026, at 10:56:23 UTC**. After this recorder restart, `migrate_dt_s` refers to the migration transaction rather than the first pool sighting. We will compare that event time with `f10_age`, the actual snapsmbiguous within 1 ms:",
              int(diff.abs().le(0.001).sum()))
</CodeBlock>

### How we'll interpret the result

If many snapshots occur after the migration event, those observations cannot be used as evidence for a bonding-curve entry strategy at the earlier time. If the snapshots consistently precede migration, that supports their temporal validity for this particular check.

There is still a distinction between temporal validity and tradeability: even a pre-migration snapshot needs enough time for a real bot to observe it, submit a transaction, and receive an executable fill.

Paste the complete output of Step 21. We'll use it to decide whether the impressive reserve signal is usable for trading research or needs to be reframed as an outcome-prediction signal.

---

# you asked

=== Audit population ===
Classic launches after recorder restart: 107599
Graduates with usable snapshot and migration times: 3116

=== Snapshot timing relative to migration ===
Snapshot age earlier than migration: 1352
Times differ by at most 1 ms: 2
Snapshot age later than migration: 1762

Difference (snapshot age - migration time), seconds:
count      3116.0000
mean      -1885.7395
std       15021.4675
min     -337339.8650
1%       -52983.8688
25%        -211.0765
50%           2.9690
75%           2.9960
99%           2.9990
max           3.0000

=== High early-reserve audit ===

f10_rs >= 10 SOL
Launches: 12030
Graduation rate: 21.812%
Graduates with both times: 2623
Snapshot age after migration time: 1762
Snapshot age before migration time: 859
Timing ambiguous within 1 ms: 2

f10_rs >= 50 SOL
Launches: 2051
Graduation rate: 96.002%
Graduates with both times: 1969
Snapshot age after migration time: 1762
Snapshot age before migration time: 205
Timing ambiguous within 1 ms: 2

f10_rs >= 80 SOL
Launches: 1842
Graduation rate: 99.946%
Graduates with both times: 1841
Snapshot age after migration time: 1762
Snapshot age before migration time: 77
Timing ambiguous within 1 ms: 2

---

# chatgpt response

**Step 21 reveals a major timing problem.** We need to revise our interpretation of the excellent model results before proceeding.

## What the timing audit tells us

Of the 1,841 graduates with `f10_rs >= 80` and known migration times, **1,762 had snapshots recorded after the migration event**—about 95.7%.

| Finding | Result |
|---|---:|
| Tokens with `f10_rs >= 80` | 1,842 |
| These tokens marked graduated | 1,841 |
| Graduates whose snapshot was after migration | 1,762 |
| Graduation rate in this group | 99.946% |

The likely explanation is that these snapshots capture tokens whose bonding curves had already reached the graduation event. Their high reserve values can reveal an outcome that has already happened.

That changes our conclusions from Step 20. A snapshot taken within three seconds of launch is not necessarily available **before graduation**. Consequently, the model's AP of 0.7415 is not evidence that we can identify profitable entries before graduation.

The same timing concern applies to other `f10_*` features recorded in the same snapshot. We should exclude all these features from our strict launch-time baseline until their availability is verified. The dataset documentation says launch-time features such as `dev_buy_sol` and `dev_share` are known at or just after launch, making them suitable candidates for that baseline. <FileCite ref="turn1file0" line_range_start={289} line_range_end={291} />

## Step 22 — Test the launch-time-only model

**Goal:** Find out how much predictive power remains when we use only information available at launch, before the early-snapshot timing problem arises.

We'll train a new model using just two features:

- `dev_buy_sol`: the creator's initial SOL purchase.
- `dev_share`: the creator's share of supply following that purchase.

This is intentionally a smaller model. We want a more defensible starting point, not the highest possible score.

Run thisploratory)",
    X_test_launch,
    y_test_launch,
)
</CodeBlock>

### What to send back

Paste the complete output of Step 22.

We'll compare the launch-time-only model with our earlier results. October 2 has already been examined, so its result is now exploratory rather than an untouched final test.

If the launch-time model retains useful ranking ability, we can investigate whether it helps select tokens for further trading simulation. The next challenge would be estimating actual entry and exit returns after fees, slippage, and execution delay—not merely predicting graduation.

---

# you asked

=== Launch-time model setup ===
Features: ['dev_buy_sol', 'dev_share']
Train rows: 108231
Validation rows: 30781
Test rows: 29836

=== Validation — October 1 ===
Graduation rate: 3.161%
Average precision: 0.5835
ROC-AUC: 0.8604
Brier score: 0.01734
Top 1%: precision=100.000%, recall=31.655%, lift=31.64x
Top 3%: precision=54.221%, recall=51.490%, lift=17.15x
Top 5%: precision=38.377%, recall=60.740%, lift=12.14x

=== Test — October 2 (exploratory) ===
Graduation rate: 3.084%
Average precision: 0.5396
ROC-AUC: 0.8442
Brier score: 0.01726
Top 1%: precision=100.000%, recall=32.500%, lift=32.43x
Top 3%: precision=48.772%, recall=47.500%, lift=15.82x
Top 5%: precision=33.512%, recall=54.348%, lift=10.87x

---

# chatgpt response

Step 22 is encouraging. The launch-time-only model achieved **0.5396 AP on October 2**, compared with a 0.0308 graduation rate. That suggests the early-snapshot fields are not necessary for the model to find a strong predictive relationship.

However, the **100% precision in the top 1% on both validation and test is unusually strong**. We should identify which launch-time feature drives this result before drawing conclusions. The dataset documentation identifies `dev_buy_sol` as the creator's first SOL purchase and `dev_share` as the creator's share of supply after that purchase. Both are recorded as launch-time information. <FileCite ref="turn1file0" line_range_start={245} line_range_end={246} />

## Step 23 — Find the source of the launch-time signal

**Goal:** Determine whether `dev_buy_sol`, `dev_share`, or their combination accounts for the model's performance.

We'll train two small models, each using one feature, and compare them with the existing two-feature model. Then we'll inspect how the feature values differ between tokens that graduate and those that do no f"mean AP drop={baseline_ap - np.mean(shuffled_aps):.4f}"
    )
</CodeBlock>

### Why this matters

If one feature alone produces nearly the full model's performance, we have a simpler hypothesis to investigate. If neither does, the combination may be important.

We'll also check whether performance depends on extreme values rather than a broad relationship across the data.

Remember that this is still graduation prediction, not proof of a profitable trading strategy. The next major question is whether a token selected at launch offers enough *subsequent tradable price movement* to cover execution costs.

Paste the complete output of Step 23, and we'll interpret it before proceeding.

---

# you asked

=== Single-feature models ===

Feature: dev_buy_sol
Validation: AP=0.5274, ROC-AUC=0.8340, top-1% precision=100.000%
Test: AP=0.5151, ROC-AUC=0.8245, top-1% precision=100.000%

Feature: dev_share
Validation: AP=0.5516, ROC-AUC=0.8582, top-1% precision=92.857%
Test: AP=0.5454, ROC-AUC=0.8507, top-1% precision=95.987%

=== Feature distributions by graduation outcome ===

dev_buy_sol
              count      mean       std  min       50%       90%       95%       99%       max
graduated                                                                                     
0.0        104883.0   1.19039   2.12461  0.0   0.48840   3.00000   4.93827   9.87614  79.03214
1.0          3348.0  41.38447  41.26711  0.0  11.68674  85.00536  85.00536  85.00536  85.00536

dev_share
              count     mean      std  min     50%      90%      95%      99%      max
graduated                                                                             
0.0        104883.0  0.03726  0.05541  0.0  0.0172  0.09755  0.15166  0.26576  0.77777
1.0          3348.0  0.40945  0.37038  0.0  0.3008  0.79310  0.79310  0.79310  0.79310

=== Two-feature model permutation check ===
Baseline validation AP: 0.5835
dev_buy_sol: mean AP after shuffle=0.2198, mean AP drop=0.3637
dev_share: mean AP after shuffle=0.4834, mean AP drop=0.1001

---

# chatgpt response

Step 23 has revealed a potentially serious problem with our launch-time baseline. **We need to investigate `dev_buy_sol` before trusting the model's performance.**

## What the results show

The single-feature models are both strong:

| Model | Validation AP | Test AP |
|---|---:|---:|
| `dev_buy_sol` only | 0.5274 | 0.5151 |
| `dev_share` only | 0.5516 | 0.5454 |
| Both features | 0.5835 | 0.5396 |

However, look at the feature distributions:

- For graduates, the 90th, 95th and 99th percentiles of `dev_buy_sol` are all **exactly 85.00536 SOL**.
- The maximum is also exactly 85.00536 SOL.
- For graduates, the 95th, 99th and maximum values of `dev_share` are all exactly **0.79310**.

That concentration is suspicious. According to the dataset documentation, `dev_buy_sol` represents the creator's first SOL purchase, and `dev_share` represents the creator's share of supply after that purchase. <FileCite ref="turn1file0" line_range_start={243} line_range_end={246} />

Those definitions alone do not explain why so many graduated tokens share the exact same extreme values. It could be a legitimate data pattern, a recording or transformation artifact, or information that indirectly reveals an outcome. We must not assume which explanation is correct.

The permutation test adds to the concern: `dev_buy_sol` is responsible for most of the two-feature model's predictive performance. We need to understand that signal before trusting the AP of 0.5396 on October 2.

## Step 24 — Investigate the suspicious values

**Goal:** Determine how often these exact values occur, whether they are concentrated among graduates, and how the two features behave together.

Run this as one new cell in Colab. It only inspects the existing data; it doesn't modif

print(example.head(15).to_string(index=False))
</CodeBlock>

### What happens next?

Paste the complete output. If these exact values are strongly concentrated among graduates, we'll investigate the dataset's construction and source records before using either feature for prediction.

For now, **do not train another model or interpret these results as a trading edge**. A good backtest score is useful only when the inputs genuinely represent information available to the bot at decision time.

---

# you asked

=== Exact-value frequency by outcome ===

dev_buy_sol ~= 85.00536
           launches  matching_rows  graduation_rate  matching_share
graduated                                                          
0.0          163607              0              0.0          0.0000
1.0            5241           1076              1.0          0.2053

dev_share ~= 0.7931
           launches  matching_rows  graduation_rate  matching_share
graduated                                                          
0.0          163607              0              0.0         0.00000
1.0            5241           2374              1.0         0.45297

=== Most frequent dev_buy_sol values among graduates ===
dev_buy_sol
85.00495    1169
85.00536    1076
0.00000      205
85.00503     127
0.00988       78
0.04897       74
0.09834       73
0.98765       69
0.00947       68
0.98738       57
0.04938       57
2.96296       52
0.09875       51
1.97531       44
3.00000       41

=== dev_buy_sol thresholds by outcome ===
>= 10 SOL: 4110 launches; graduation rate=62.628%
>= 50 SOL: 2424 launches; graduation rate=99.175%
>= 80 SOL: 2384 launches; graduation rate=100.000%
>= 85 SOL: 2375 launches; graduation rate=100.000%

=== Example rows with dev_buy_sol near 85.00536 ===
                                        mint                 launched_at  dev_buy_sol  dev_share  graduated  rugged features_basis  decoder_complete
 Cr5enABewj7i284QEXDKZjEgYGaypCVJGnVTgfKpump 2026-09-30T02:29:56.361999Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
 MB3XEHbxxTSmd4z1kx8uneaMgAmoFKHgrAxCL3Lpump 2026-09-30T02:33:22.426000Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
 wwBv5tvt9VCgPNtWz1nEwW6GcAUfBWN98g82mfQpump 2026-09-30T02:36:29.164000Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
7uy9KcXSW4Q2BPtYsPSVYfdBzXofm8aw66b1qDbnpump 2026-09-30T02:41:21.796000Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
36NeT4Lbq3mNMgvb1E1SRisgKRwEbX8ZDjywSjeHpump 2026-09-30T02:42:01.533999Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
47UZ1hDkjQ6qhReE1oD84cj24m2eXCK4RwXevWyZWJJy 2026-09-30T02:42:09.033999Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
EnydPC3tev6iouM1E8ubLaP2Vk3HE3epnB3kXysFpump 2026-09-30T02:48:28.862999Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
8MFRTZq9Xev3G5V8MNZgFJL9azhuCTCs2jnYXtGhoyQ1 2026-09-30T02:50:08.706000Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
4xovE8QUiyuXm6vtvEobFXaW9k3rBxniegaJwUCEpump 2026-09-30T02:51:16.723000Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
7DcQNAyGqjtGdc78sb9qJgBPDLVfhyYgsaLHBpW9pump 2026-09-30T02:51:41.788000Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
Ep3UuB7AMSws3WLt9bG7N7sWXkmx9B7qqYXUGZcUu1xP 2026-09-30T02:54:11.760999Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
9Fj5QjTtc6EChYQDgv3XYx4ahirZ5Hi2z8eyJVQapump 2026-09-30T02:59:10.263000Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
5p4fR3tjwq4hGA61vmHPNDFAYdiVC5ncHo6zQydbpump 2026-09-30T03:14:20.082000Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
HKdULkp2U5Ee7yC8AQjbaoNaBSJFT8uqxV5dtP31pump 2026-09-30T03:17:12.323999Z    85.005359     0.7931        1.0     0.0    tape_replay                 1
GKyuKwsYFpfTXrNfbawLHe2a76zcoZ1xi91qVwG8pump 2026-09-30T03:17:32.584000Z    85.005359     0.7931        1.0     0.0    tape_replay                 1

---

# chatgpt response

Step 24 has exposed a strong relationship between the creator-buy fields and graduation. **We should not treat the launch-time model's high scores as evidence of a tradable edge yet.**

## What your results show

<box border radius="lg" padding={3} gap={3}>
  <row align="center" gap={3}>
    <box flex="1" gap={1}>
      <text color="secondary" size="sm">Tokens with `dev_buy_sol ≥ 80`</text>
      <title size="2xl">2,384</title>
      <text color="secondary" size="sm">100% observed graduation rate</text>
    </box>
  </row>
  <divider color="subtle" />
  <row align="center" gap={3}>
    <box flex="1" gap={1}>
      <text color="secondary" size="sm">Exact `dev_buy_sol ≈ 85.00536`</text>
      <title size="xl">1,076</title>
      <text color="secondary" size="sm">All marked graduated</text>
    </box>
  </row>
  <divider color="subtle" />
  <row align="center" gap={3}>
    <box flex="1" gap={1}>
      <text color="secondary" size="sm">Exact `dev_share ≈ 0.79310`</text>
      <title size="xl">2,374</title>
      <text color="secondary" size="sm">All marked graduated</text>
    </box>
  </row>
</box>

These patterns could reflect genuine, very large creator purchases that complete the bonding curve immediately. They could also reflect a data-construction issue. Our output alone cannot distinguish those explanations.

The dataset defines `dev_buy_sol` as the creator's first SOL purchase and `dev_share` as their resulting supply share. Graduation igh["launched_dt"].dt.date

high_daily = high.groupby("day").agg(
    high_buy_launches=("mint", "size"),
    graduations=("graduated", "sum"),
    exact_8500536=(
        "dev_buy_sol",
        lambda s: np.isclose(
            s, 85.00536, atol=1e-5, rtol=0
        ).sum(),
    ),
)

print(high_daily.to_string())
print()

# Inspect individual high-buy records and their event timings.
print("=== Example high-buy launches ===")

example_cols = [
    "mint",
    "launched_at",
    "dev_buy_sol",
    "dev_share",
    "graduated",
    "migrate_dt_s",
    "f10_age",
    "f10_rs",
]

example_cols = [
    c for c in example_cols if c in high.columns
]

print(
    high[example_cols]
    .sort_values("migrate_dt_s")
    .head(15)
    .to_string(index=False)
)
</CodeBlock>

### What we're testing

If high-buy launches usually migrate within seconds, that would support the hypothesis that these purchases are associated with immediate curve completion. If they do not, we will need to investigate why the feature values are so tightly coupled to graduation.

Either way, don't remove rows or retrain the model yet. Paste the complete output of Step 25, and we'll decide whether `dev_buy_sol` is a legitimate launch-time signal for our intended entry decision or a feature that effectively describes an outcome already underway.

---

# you asked

=== Graduation and migration by creator-buy size ===
           launches  graduations  graduation_rate  migration_coverage  median_migrate_s  migration_within_3s  migration_within_10s
buy_band                                                                                                                          
< 1 SOL     71822.0       1084.0           0.0151              0.0151           73.1980               0.3834                0.4065
1–10 SOL    33049.0        617.0           0.0187              0.0186          316.4950               0.0552                0.0731
10–50 SOL    1143.0        118.0           0.1032              0.1032          193.5690               0.0424                0.0932
50–80 SOL      30.0         12.0           0.4000              0.4000          258.8375               0.0000                0.0000
>= 80 SOL    1555.0       1555.0           1.0000              1.0000            0.0030               0.9981                0.9994

=== Exact high-buy values by launch day ===
            high_buy_launches  graduations  exact_8500536
day                                                      
2026-09-29                281        281.0              0
2026-09-30                453        453.0            388
2026-10-01                427        427.0            423
2026-10-02                394        394.0            265

=== Example high-buy launches ===
                                        mint                 launched_at  dev_buy_sol  dev_share  graduated  migrate_dt_s  f10_age    f10_rs
FqiGWuVNeBQi3hxiHS8KQHf9oJhATDW2GZZdu51Kpump 2026-10-01T08:08:51.191999Z    85.005359     0.7931        1.0         0.000      3.0 85.005359
6feYsPGqT7xGr13FrSnSLNhfxgiCsCei9Wu4jpshpump 2026-10-01T08:54:51.345999Z    85.005359     0.7931        1.0         0.000      3.0 85.005359
25xmw6ZenCNkS6YPTkKZUfdzYfxLvFj5LWs9JBpPpump 2026-10-01T13:03:03.244999Z    85.005359     0.7931        1.0         0.000      3.0 85.005359
2GhwZN5SuRkuCwVcq3zquXeiKMvjvfqgCAdbkhr2a7E1 2026-10-02T00:10:20.076999Z    85.005359     0.7931        1.0         0.000      3.0 85.005359
 Z7PerutAfCHCFhKvmQYb1Ad5XRHmUoH7vcBeu9opump 2026-10-02T00:46:53.250999Z    85.005359     0.7931        1.0         0.000      3.0 85.005359
3AiAsw4MVufNVbAMGHAh8zbDvWa5zj6uV9rRZenEpump 2026-09-29T16:02:08.562000Z    85.004953     0.7931        1.0         0.001      3.0 85.005359
3vt7QRQSAvDE5ouWVZRpPcMYGjuUud3KstzT6yLKpump 2026-09-29T15:43:36.453000Z    85.004953     0.7931        1.0         0.001      3.0 85.005359
 FZrt8uvQsQMR2vtKCLRFwU7CCtHJBxq9eTALNTJpump 2026-10-02T23:39:53.046000Z    85.005034     0.7931        1.0         0.001      3.0 85.005034
4TFr6mMY4rJdjSf6FA3XQwRkLkhBSnP3y4K5pwRb3aWo 2026-10-02T20:51:57.045000Z    85.005034     0.7931        1.0         0.001      3.0 85.005034
CWKs8BM8P3bpwfXuvLDuds4WeoyucSD7VANLBxKCpump 2026-10-02T21:06:28.302999Z    85.005034     0.7931        1.0         0.001      3.0 85.005034
 1e5LjjWxXbq34umFDbmvnBnPiEK8o8QCvZCEZ5Xpump 2026-09-30T15:29:23.716000Z    85.005359     0.7931        1.0         0.001      3.0 85.005359
CMu3p9CLK3ZgHMeoSNiikNE8gELHMATfat7uSozDpump 2026-09-30T20:02:10.822999Z    85.005359     0.7931        1.0         0.001      3.0 85.005359
DX8qxTMkxpUECrZ4jXSF31aZ5yxFPxSY4e4ZQbAcpbsJ 2026-09-30T20:13:16.334000Z    85.005359     0.7931        1.0         0.001      3.0 85.005359
DCcv8bpGMPjnhkQmmeSmvuEyCnG3yVZ2ZYVhDdeMpump 2026-09-30T19:13:58.769999Z    85.005359     0.7931        1.0         0.001      3.0 85.005359
 RFH6Crn4136CzR8q4JKvkzXmqCkeTp6cPM2mmevpump 2026-09-29T12:56:58.042999Z    85.004953     0.7931        1.0         0.001      3.0 85.005359
/tmp/ipykernel_1789/586869057.py:52: DeprecationWarning: DataFrameGroupBy.apply operated on the grouping columns. This behavior is deprecated, and in a future version of pandas the grouping columns will be excluded from the operation. Either pass `include_groups=False` to exclude the groupings or explicitly select the grouping columns after groupby to silence this warning.
  .apply(summarize_group)

---

# chatgpt response

Step 25 makes the explanation much clearer. **The launch-time model's high scores are heavily influenced by tokens that graduate almost immediately.**

Among the 1,555 launches with `dev_buy_sol >= 80`, every token is marked graduated, and the median migration time is only **0.003 seconds**. Almost all migrated within three seconds.

That is a strong warning for our intended trading task. The dataset defines `dev_buy_sol` as the creator's first purchase, while `migrate_dt_s` records the migration or pool-sighting time; after the September 29 recorder restart, it refers to the migration transaction. <FileCite ref="turn1file0" line_range_start={243} line_range_end={249} /><FileCite ref="turn1file0" line_range_start={96} line_range_end={104} />

We cannot conclude that `dev_buy_sol` is incorrectly recorded, but these high values are not evidence of an opportunity we could necessarily trade. The graduation may already have happened before our bot can react.

## Step 26 — Test whether the signal survives without immediate-graduation cases

**Goal:** Train the same simple model after excluding launches with `dev_buy_sol >= 80 SOL`, then evaluate it only on validation and test launches below that threshold.

This is a diagnostic experiment, not a proposed trading filter. We are isolating the suspicious group to learn h_val_cut,
)

evaluate_filtered(
    "Test — below 80 SOL (exploratory)",
    X_test_cut,
    y_test_cut,
)
</CodeBlock>

### What this experiment will tell us

If AP and top-percentile precision fall sharply, the original model's performance relied substantially on the immediate-graduation group. If performance remains strong, we have evidence that the launch-time features carry additional predictive information among the other launches.

Even if the signal survives, this still does not demonstrate profitability. We must eventually evaluate executable entry prices, subsequent price paths, exits, fees, slippage and latency.

Paste the complete output of Step 26. We'll use it to decide whether the launch-time baseline is worth pursuing or whether we should move toward sequential trading data instead.

---

# you asked

=== Outcome rates by dev_buy_sol threshold ===

train:
Below 80 SOL: n=106668, graduations=1785, graduation_rate=1.673%
At least 80 SOL: n=1563, graduations=1563, graduation_rate=100.000%

validation:
Below 80 SOL: n=30354, graduations=546, graduation_rate=1.799%
At least 80 SOL: n=427, graduations=427, graduation_rate=100.000%

test:
Below 80 SOL: n=29442, graduations=526, graduation_rate=1.787%
At least 80 SOL: n=394, graduations=394, graduation_rate=100.000%

=== Filtered sample sizes ===
Train: 106668
Validation: 30354
Test: 29442

=== Validation — below 80 SOL ===
Rows: 30354
Graduation rate: 1.799%
Average precision: 0.1032
ROC-AUC: 0.7514
Brier score: 0.01690
Top 1%: precision=26.316%, recall=14.652%, lift=14.63x
Top 3%: precision=13.282%, recall=22.161%, lift=7.38x
Top 5%: precision=11.528%, recall=32.051%, lift=6.41x

=== Test — below 80 SOL (exploratory) ===
Rows: 29442
Graduation rate: 1.787%
Average precision: 0.0641
ROC-AUC: 0.7366
Brier score: 0.01732
Top 1%: precision=10.847%, recall=6.084%, lift=6.07x
Top 3%: precision=7.466%, recall=12.548%, lift=4.18x
Top 5%: precision=6.653%, recall=18.631%, lift=3.72x

---

# chatgpt response

Step 26 confirms that the original model's very high performance was driven substantially by the immediate-graduation group. But **the launch-time features still retain some predictive value after excluding tokens with `dev_buy_sol >= 80 SOL`.**

## Step 26 — Interpretation

| Metric | Validation, below 80 SOL | Test, below 80 SOL |
|---|---:|---:|
| Graduation rate | 1.80% | 1.79% |
| Average precision | 0.1032 | 0.0641 |
| ROC-AUC | 0.7514 | 0.7366 |
| Top 1% precision | 26.32% | 10.85% |
| Top 5% precision | 11.53% | 6.65% |

The test AP is approximately 3.6 times the test graduation rate, so there is still a ranking signal. However, AP falls from 0.1032 on validation to 0.0641 on test. That is a meaningful deterioration, and we have only one test day.

The high-value group is not merely a minor anomaly: every launch with `dev_buy_sol >= 80` graduated in all three chronological splits. The dataset's migration timing indicates that these graduations generally happen almost immediately. We should keep these cases separate from ordinary token-selection experiments until the feature's practical availability is established.

## Step 27 — Test whether the remaining signal survives stricter thresholds

**Goal:** Check whether the model retains predictive ability when we exclude progressively more high creator-buy values.

We'll compare three overlapping cohorts: `dev_buy_sol < 10`, `< 50`, and `< 80 SOL`. For each threshold, we will train a new model using only that threshold's training rows and evaluate it on the corresponding validation and test rows.

Run this as one new cell in your existing Colab notebook.

<CodeBlock langu=False))
</CodeBlock>

### What we're looking for

If performance remains reasonably consistent under the stricter thresholds, that supports the hypothesis that the model identifies useful differences among ordinary launches. If it collapses as we lower the threshold, much of its remaining signal may still come from unusually large creator purchases.

Either result is useful. Our aim is to determine what the data can genuinely support—not to maximize a classification score.

Paste the full output of Step 27. After that, we can decide whether to continue with supervised token selection or start planning the sequential price-data component required for PPO.

---

# you asked

=======================================================
Creator-buy threshold: < 10 SOL
=======================================================
Rows: train / validation / test: 105709 / 29873 / 29156
Graduation rates: train=1.577%, validation=1.694%, test=1.694%
validation: AP=0.1237, ROC-AUC=0.7425, top-1% precision=19.398%, AP/prevalence=7.30x
test: AP=0.0578, ROC-AUC=0.7105, top-1% precision=9.589%, AP/prevalence=3.41x

=======================================================
Creator-buy threshold: < 50 SOL
=======================================================
Rows: train / validation / test: 106648 / 30337 / 29439
Graduation rates: train=1.662%, validation=1.780%, test=1.783%
validation: AP=0.1006, ROC-AUC=0.7461, top-1% precision=25.000%, AP/prevalence=5.65x
test: AP=0.0679, ROC-AUC=0.7436, top-1% precision=12.881%, AP/prevalence=3.81x

=======================================================
Creator-buy threshold: < 80 SOL
=======================================================
Rows: train / validation / test: 106668 / 30354 / 29442
Graduation rates: train=1.673%, validation=1.799%, test=1.787%
validation: AP=0.1032, ROC-AUC=0.7514, top-1% precision=26.316%, AP/prevalence=5.74x
test: AP=0.0641, ROC-AUC=0.7366, top-1% precision=10.847%, AP/prevalence=3.59x

=== Combined comparison ===
 threshold      split  rows  graduation_rate     AP  ROC_AUC  top_1pct_precision  AP_lift_over_prevalence
        10 validation 29873           0.0169 0.1237   0.7425              0.1940                   7.3019
        10       test 29156           0.0169 0.0578   0.7105              0.0959                   3.4111
        50 validation 30337           0.0178 0.1006   0.7461              0.2500                   5.6526
        50       test 29439           0.0178 0.0679   0.7436              0.1288                   3.8095
        80 validation 30354           0.0180 0.1032   0.7514              0.2632                   5.7397
        80       test 29442           0.0179 0.0641   0.7366              0.1085                   3.5894

---

# chatgpt response

Step 27 shows that the launch-time model retains a predictive signal even after we remove the immediate-graduation cases. However, its performance is weaker on October 2 than on October 1.

| Creator-buy limit | Validation AP | Test AP | Test ROC-AUC |
|---|---:|---:|---:|
| Below 10 SOL | 0.1237 | 0.0578 | 0.7105 |
| Below 50 SOL | 0.1006 | **0.0679** | **0.7436** |
| Below 80 SOL | 0.1032 | 0.0641 | 0.7366 |

The test average precision is about 3.4–3.8 times the corresponding graduation rate. That's worth investigating, but the validation-to-test deterioration suggests that the signal may be sensitive to time or market conditions.

**We should not choose the 50 SOL threshold just because it performed best on this test.** We've examined October 2 repeatedly, so it is no longer an untouched holdout. The next step is to look for genuinely newer data and evaluate the existing models without retraining or adjusting their settings.

## Step 28 — Check for a newer dataset release

**Goal:** Find out whether the dataset now contains launches after October 2, 2026. If it does, we'll evaluate our existing models on those new launches. If not, we'll preserve our current results and identify another source of genuinely out-of-time data.

Run this as one new cell in Colab.

<CodeBlock languag     )
</CodeBlock>

### What to send back

Paste the complete output, especially the latest commit, last launch date, number of fresh rows, and any model scores produced.

We'll keep the original snapshot and models intact. If the published dataset still ends on October 2, we'll know this source cannot provide the fresh evaluation window we need yet.

One final distinction: even a successful fresh evaluation would establish only that the model predicts graduation. Our longer-term objective is still a sequential trading environment with realistic entry and exit prices, execution delays, fees and slippage—the information needed to evaluate PPO as a trading policy.

---

# you asked

\---------------------------------------------------------------------------&#x20;
TypeError                                 Traceback (most recent call last)&#x20;
/tmp/ipykernel_1789/774449317.py in \<cell line: 0>()&#x20;**&#x20;    13** # 1) Check the latest published version.&#x20;**&#x20;    14** api = HfApi() ---> 15 latest_info = api.dataset_info(&#x20;**&#x20;    16**     repo_id,&#x20;**&#x20;    17**     repo_type="dataset", &#x20;
/usr/local/lib/python3.13/dist-packages/huggingface_hub/utils/\_validators.py in \_inner_fn(\*args, \*\*kwargs)&#x20;**&#x20;    87**         kwargs = smoothly_deprecate_legacy_arguments(fn_name=fn.\_\_name\_\_, kwargs=kwargs)&#x20;**&#x20;    88**  ---> 89         return fn(\*args, \*\*kwargs)&#x20;**&#x20;    90** &#x20;**&#x20;    91**     return \_inner_fn  # type: ignore &#x20;
TypeError: HfApi.dataset_info() got an unexpected keyword argument 'repo_type'

---

# chatgpt response

This is a small API compatibility issue. In your installed `huggingface_hub` version, `HfApi.dataset_info()` already identifies the repository as a dataset, so it doesn't accept `repo_type`. The official API documentation confirms this signature. <Cite refs={["turn203069search1"]}/>

### Fix Step 28

Replaet",
)
```

Wito_id)
```

**Then rerun the entire Step 28 cell.** No need to reinstall anything or restart Colab.

Keep the rest of the code unchanged for now. Please paste the new output, especially the latest commit, last launch date, and number of launches after October 2. We need to confirm that fresh data is actually available before evaluating the existing model o it.

---

# you asked

=== Dataset version ===
Original commit: 21be6aeb5d66721e3d40e34b09141f408e1e0ca0
Latest commit:   21be6aeb5d66721e3d40e34b09141f408e1e0ca0
Last modified:   2026-10-09 07:30:41+00:00
New commit available: False

=== Latest data coverage ===
Rows: 269538
Unique mints: 269538
First launch: 2026-09-27 00:00:02.844000+00:00
Last launch:  2026-10-02 23:59:56.779000+00:00

=== Fresh launch dates ===
Rows after October 2: 0

=== Fresh classic cohort ===
Rows with known graduation: 0
Graduations: 0
No eligible fresh cohort is available yet.

---

# chatgpt response

Step 28 is complete. The result confirms that **we do not have a fresh evaluation set in the current Loopholetape release**.

The repository was last modified on October 9, 2026, but its latest launch is still October 2. The dataset intentionally publishes historical files with a delay of at least seven days. <FileCite ref="turn1file0" line_range_start={216} line_range_end={221} />

We should stop tuning the supervised model against the same six days. The next stage of your project is to acquire **sequential trade data** so that we can reconstruct token price paths and eventually train PPO.

## Step 29 — Check a more recent historical event archive

Let's try Shrine's historical replay archive before resorting to PumpApi. Its documentation describes free, hourly compressed event archives that use the same general event format as its live stream. The published archive index currently lists data through October 9, 2026, although there are missing hours. <Cite refs={["turn642390view0","turn905517view0"]}/>

We won't download any large trading files yet. First, we'll inspect the archive index to identify its coverage and gaps.

Run "to {end:%Y-%m-%d %H}:59"
        )
else:
    print("No missing hourly slots.")
</CodeBlock>

### Why we're doing this first

An event archive is more useful for our goal than another table of final token outcomes: it can potentially support sequential observations, simulated buy/sell actions, and trade-level reward calculations.

But we must check completeness before using it. The archive documentation warns that hourly files can have gaps and recommends checking block numbers when completeness matters. Individual files can also be hundreds of megabytes compressed, so we won't download the entire archive into Colab. <Cite refs={["turn642390view0"]}/>

Paste the output of Step 29. We'll select a manageable first sample and inspect its event schema before attempting to reconstruct any tradig environment.

---

# you asked

\=== Archive information === Base URL: [https://replay.shrine.trade/pump](https://replay.shrine.trade/pump) Reported archive hours: 608 Parsed archive hours: 608 First available hour: 2026-09-14 15:00:00+00:00 Last available hour:  2026-10-10 05:00:00+00:00 Last index update: 2026-10-10T06:00:28.917028556+00:00  === Coverage === Expected hourly slots: 615 Missing hourly slots: 7 Coverage percentage: 98.86%  === First 15 missing periods (UTC) === 2026-09-27 15:00 to 2026-09-27 15:59 2026-10-03 02:00 to 2026-10-03 07:59

---

# chatgpt response

The archive index looks promising for an out-of-time sample: 608 of 615 hourly slots are present (98.86% coverage), reaching **October 10, 2026 at 05:00 UTC**. The seven missing hours are one hour on September 27 and a six-hour gap on October 3 from 02:00–07:59 UTC. Next, let's verify a single post-October-2 archive file's size and format before downloading anything large.

Your archive audit is promising. We now have historical events after the October 2 cutoff of the launch dataset, so we can begin investigating actual trading sequences rather than relying only on final outcomes.

The archive stores one Zstandard-compressed JSON object per line. Each event includes fields such as `signature`, `block`, `timestamp`, `action`, `protocol`, `mint`, reserves and trader information. An hour can be hundreds of megabytes compressed, so we'll stream it instead of loading the whole file. <Cite refs={["turn309264view0"]}/>

## Step 30 — Inspect the first 100 historical events

**Goal:** Confirm the actual event schema and whether the archive contains the buy/sell events needed to reconstruct token activity.

We'll inspect **October 4, 2026, 12:00–13:00 UTC**. This is after the launch dataset's last date and outside the archive's reported gaps.

Run this as one new cell i   print(f"{field}:", description)
</CodeBlock>

### What this step tells us

We'll verify whether events contain actual trade actions, how protocols are represented, and where price/reserve and trader information live in the schema.

This is only a **100-event sample**, not a full-hour market statistic. Shrine also cautions that neighbouring events can occasionally be out of order, so when reconstructing trading sequences we must account for block ordering. <Cite refs={["turn309264view0"]}/>

Paste the complete output of Step 30. Then we'll decide how to build a small, filtered event dataset for one token without downloading gigabytes unneessarily.

---

# you asked

\=== Archive file === Hour (UTC): 2026/10/04/12 URL: [https://replay.shrine.trade/pump/2026/10/04/12.jsonl.zst](https://replay.shrine.trade/pump/2026/10/04/12.jsonl.zst)  HTTP status: 200 Compressed size: 213.64 MiB  === Sample size === Events inspected: 100 Block range in sample: 453250176 to 453250177  === Actions in the first 100 events === {'buy': 58, 'sell': 42}  === Protocols in the first 100 events === {'PUMPSWAP': 76, 'METEORA': 9, 'PUMPFUN': 10, 'ORCA': 2, 'PUMPFUN_MAYHEM': 3}  === First event: available field names === ['action', 'block', 'breakdown', 'localTimestamp', 'marketCapQuote', 'mint', 'pool', 'price', 'protocol', 'pub', 'quoteAmount', 'quoteInPool', 'quoteMint', 'recv', 'signature', 'timestamp', 'tokenAmount', 'tokensInPool', 'tradersInvolved', 'txSigner']  === First event: selected values === {   "signature": "39vJnmzJHjvrM5YsxupX7AgkeirRx287ySSuaYDo4F3K4YCLMw1TXWHSL6iEssgsBxjQiNdRwcyPzHW3nGy86jas",   "block": 453250176,   "timestamp": 1791115199,   "localTimestamp": 1791115200032,   "action": "buy",   "protocol": "PUMPSWAP",   "mint": "7VertkgF9KLhxxJXHX6uaWuoYZTP9LdGj2bWmVXVpump" }  === Nested-field structure === breakdown: {'type': 'list', 'length': 1, 'first_item_keys': ['action', 'price', 'quoteAmount', 'tokenAmount', 'trader']} tradersInvolved: {'type': 'list', 'length': 1, 'first_item_keys': None} reserves: {'type': 'NoneType'}

---

# chatgpt response

Step 30 confirms that Shrine's archive contains the kind of data we need: individual buys and sells, token mints, prices, trade amounts, pool information, timestamps, and trader identifiers.

There is one important detail: **the event has `quoteInPool` and `tokensInPool`, but no `reserves` field.** We'll inspect the actual values before deciding how to reconstruct prices and pool state. We also won't download the entire 213.64 MiB hour into memory.

## Step 31 — Understand the event fields and units

**Goal:** Inspect the three event records already held in your Colab session. This is a lightweight check; it doesn't download the archive again.

Run this as one new cell.

<aders[:5])

    print()
</CodeBlock>

### What we're checking

We need to establish whether `price` is expressed in quote-asset units per token, whether the trade amounts are already human-readable, and whether the two timestamp fields represent event time and observation time.

We'll also inspect whether `quoteInPool` and `tokensInPool` provide enough information to track a token's state. We shouldn't assume that their units or semantics are correct until we've compared them with the recorded price and trade amounts.

**Paste the output of Step 31.** Then we'll move on to identifying a token with a sufficiently long sequence of trades and extracting only the events needed to reconstruct its price path.

---

# you asked

============================================================
EVENT 1
============================================================
Mint: 7VertkgF9KLhxxJXHX6uaWuoYZTP9LdGj2bWmVXVpump
Action: buy
Protocol: PUMPSWAP
Block: 453250176
timestamp as UTC: 2026-10-04 11:59:59+00:00
localTimestamp as UTC: 2026-10-04 12:00:00.032000+00:00

Main field values:
price: 0.00015416998889953388
quoteAmount: 0.0499
tokenAmount: 320.382986
marketCapQuote: 148135.3028772824
quoteInPool: 2442.954742329
tokensInPool: 15845851.45116
quoteMint: 'So11111111111111111111111111111111111111112'
pool: 'CyJwKnLiiY4fmiwqMCSWFSHxo7T9Ubshgs2uRAuJCrk5'
pub: 1791115200032
recv: 1791115200031
txSigner: '5kdqs4NtqPgdaJvZ7n33zzSARo32uP8EshACAJ5VfD4G'

Price consistency check:
quoteAmount / tokenAmount: 0.0001557510922256027665588958585
Recorded price: 0.00015416998889953388
Relative difference: 0.01025558435435333219950118110

Breakdown:
[
  {
    "action": "buy",
    "price": 0.00015575109222560276,
    "quoteAmount": 0.0499,
    "tokenAmount": 320.382986,
    "trader": "5kdqs4NtqPgdaJvZ7n33zzSARo32uP8EshACAJ5VfD4G"
  }
]

Trader identifiers:
['5kdqs4NtqPgdaJvZ7n33zzSARo32uP8EshACAJ5VfD4G']

============================================================
EVENT 2
============================================================
Mint: J2ejrTUy12spPt2kcmPMA8yjoXM7rbDQfvDVjCdpVNxh
Action: buy
Protocol: METEORA
Block: 453250176
timestamp as UTC: 2026-10-04 12:00:00+00:00
localTimestamp as UTC: 2026-10-04 12:00:00.060000+00:00

Main field values:
price: 8.754578664119566e-07
quoteAmount: 0.007329704
tokenAmount: 8372.423484
marketCapQuote: 875.4578664119565
quoteInPool: None
tokensInPool: None
quoteMint: 'So11111111111111111111111111111111111111112'
pool: 'HJ4BkGPcHMoaqeSodFXQeadYxLNtsxoEN3Mr5tNZa3mC'
pub: 1791115200060
recv: 1791115200056
txSigner: '92Jc6DWodwBeXAWQvirT6m5Q2t8FxJvfcBxf76QxAcUs'

Price consistency check:
quoteAmount / tokenAmount: 8.754578664119565693961019901E-7
Recorded price: 8.754578664119566E-7
Relative difference: 3.495759097502813422403668816E-17

Breakdown:
[
  {
    "action": "buy",
    "price": 8.754578664119566e-07,
    "quoteAmount": 0.007329704,
    "tokenAmount": 8372.423484,
    "trader": ""
  }
]

Trader identifiers:
['']

============================================================
EVENT 3
============================================================
Mint: 49XwhFwKvKvrFJjb6ojfoHd8AMfp26yFFfV9gH8qpump
Action: sell
Protocol: PUMPFUN
Block: 453250176
timestamp as UTC: 2026-10-04 11:59:59+00:00
localTimestamp as UTC: 2026-10-04 12:00:00.060000+00:00

Main field values:
price: 1.4009068299526143e-07
quoteAmount: 0.069621504
tokenAmount: 496459.84164
marketCapQuote: 0.00014009068299526142
quoteInPool: 67.152953269
tokensInPool: 479353457.58341
quoteMint: 'So11111111111111111111111111111111111111112'
pool: '4utmo5esJgSmb1nUBjQ8ikZmbitaGiwDxG1Z5rVHWPc8'
pub: 1791115200060
recv: 1791115200056
txSigner: '8EkyDgMH6ki2FZD8Vrf7jwQRY5BB8m5wrSVvSmGQU1j5'

Price consistency check:
quoteAmount / tokenAmount: 1.402359227485814093086089073E-7
Recorded price: 1.4009068299526143E-7
Relative difference: 0.001036755266050719775632454153

Breakdown:
[
  {
    "action": "sell",
    "price": 1.402359227485814e-07,
    "quoteAmount": 0.069621504,
    "tokenAmount": 496459.84164,
    "trader": "8EkyDgMH6ki2FZD8Vrf7jwQRY5BB8m5wrSVvSmGQU1j5"
  }
]

Trader identifiers:
['8EkyDgMH6ki2FZD8Vrf7jwQRY5BB8m5wrSVvSmGQU1j5']

---

# chatgpt response

Step 31 confirms the archive has the information needed to begin reconstructing trading sequences. We also verified an important distinction in Shrine's published schema: **the top-level `price` is the post-trade pool price, while `breakdown[].price` provides the price of an individual swap leg.** Amounts are in human-readable units, not raw token units. <Cite refs={["turn389877view0"]}/>

For example, in Event 1, `quoteAmount / tokenAmount` matches the breakdown price, not the top-level price. That difference is expected under the documented schema.

We also have two different timestamps: `timestamp` is the block timestamp in seconds, while `localTimestamp` records when Shrine's server saw the transaction in milliseconds. We'll retain both. <Cite refs={["turn801896view0"]}/>

## Step 32 — Find an active, newly launched token

**Goal:** Scan the October 4 archive hour and find classic Pump.fun launches with enough subsequent trading activity to study.

We'll stream the file and keep only compact statistics for each mint. The cell processes the full hour, but it does not load the entire archive into memory or save every event.

Run this as one new cell in your exiint(eligible.iloc[0][display_cols].to_string())
</CodeBlock>

### What we'll do with the result

We'll choose a token with at least 20 observed trades, preferably one that has activity on both the initial Pump.fun curve and PumpSwap after migration. If no token meets that condition, we'll adjust the sample rather than forcing a poor candidate.

The trade counts here cover only the selected hour, so they are not the token's complete lifetime history. The next step will extract the selected mint's actual events into a compact table, preserve the event ordering, and inspect its price path.

Paste the complete scan summary and the candidte table.

---

# you asked

Scanning archive hour: 2026/10/04/12
This reads the full compressed hour as a stream.

Compressed file size: 213.64 MiB
Events scanned: 500000
Events scanned: 1000000

=== Scan summary ===
Total events scanned: 1107318
Classic SOL Pump.fun creates: 2133
Relevant SOL-quoted buy/sell events: 771350
Unique classic launches: 1082

=== Most active newly launched tokens ===
                                        mint    symbol                      launch_time  total_trades  buy_events  sell_events  pumpfun_events  pumpswap_events    min_price    max_price
DoVAVzViX8Bjy3r15nwikSaSbzE6dV4ovd28aWpJpump     HIGGS 2026-10-04 12:26:34.860000+00:00         28725       15082        13643            2768            25957 2.983022e-08 7.545186e-06
98FPTSbFm3m8w3YMWLK9Ke2Fjt3SdZtNcSCFZcgWpump    Gemini 2026-10-04 12:17:47.988000+00:00         17193        7809         9384               1            17192 2.766389e-10 7.586423e-06
 nMnddwSU83WJ5NnVzocrBdnmGJQBHnLYyCscKEWpump Robinhood 2026-10-04 12:03:38.230000+00:00         16926        9435         7491               1            16925 3.736063e-10 4.745089e-06
HTYuNpG6eWjQqt5fznEgU1hFVmaV8DYrMJKtvhuas5xN     Joker 2026-10-04 12:29:17.864000+00:00         10302        5578         4724               1            10301 2.587609e-10 4.421672e-06
A3WUfYA5DRCBX8PQTyk9tvaUxrte2bb76qUsev4Rwswx      LEGO 2026-10-04 12:20:00.288000+00:00          7456        3920         3536               1             7455 3.070867e-10 3.300288e-06
ChUdczuMMJRnLPyg9nFrED4oULt6h2TL8UimW3Ub97Qb     Tesla 2026-10-04 12:44:13.213000+00:00          6380        3251         3129               1             6379 2.084605e-10 3.690272e-06
FvEtxYTGk6UxgKvcHETh3oCVDQbQFgLdupf8rzcNpump  VIRTUALZ 2026-10-04 12:16:37.252000+00:00          5499        3042         2457            2792             2707 2.959050e-08 1.218665e-06
AYXqgh4Ryy1VwQX2hpKxX1yrNXj4JKehw8WAeC8epump   knightT 2026-10-04 12:14:19.865000+00:00          5007        2569         2438               6             5001 3.057735e-09 8.771102e-07
HJ2QzKWG5WxxPgJNu6dABfchZDfJLgk3BnhAH2NZpump    NVIDIA 2026-10-04 12:17:25.650000+00:00          4485        2172         2313               1             4484 5.627491e-10 3.328988e-06
8Y5AP9NqanQbQHn253HB2ns9ZDWyba3vxoHTdhern886    SpaceX 2026-10-04 12:50:44.132000+00:00          4396        2540         1856               1             4395 3.344039e-07 3.815546e-06
BBirK74KfPezj25Z9tGcb5gAD3tKgmtQqcBzx3LBpump    NVIDIA 2026-10-04 12:46:53.818000+00:00          3553        1852         1701               1             3552 3.344055e-07 4.144143e-06
C2FSFMFRE3E68AQ1yHTNAb2NRMfeFSXkpTKmx4Ehpump   MEOWFIA 2026-10-04 12:31:27.462000+00:00          3463        1738         1725            1031             2432 3.028929e-09 7.174267e-07
7QJ3BnoFkuxBFtqS3MsAN9EeMeoytob7H7KAFP38pump     HIGGS 2026-10-04 12:51:52.742000+00:00          3059        1536         1523               1             3058 3.344055e-07 3.449352e-06
DMZTzPBTTWYb7SREE2BXwZ42zVJpxrAKfpvHbqE5XJww      VEIL 2026-10-04 12:21:19.243000+00:00          3023        1700         1323            3023                0 2.983022e-08 2.551171e-07
7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump     TR4CE 2026-10-04 12:46:27.744000+00:00          2967        2260          707            1219             1748 2.246053e-09 4.108802e-07
Av9FWAxskP79aNirbcmj8t1Wbcy1sYC42GPBo4gtpump       YUI 2026-10-04 12:08:27.884000+00:00          1996        1047          949            1996                0 3.445372e-08 2.689231e-07
AXY9AY3dfsybAP9LfYWPYqaFHTE9vUGTiCBiqnfUT9g3  HIGGSCAT 2026-10-04 12:31:38.690000+00:00          1979        1138          841            1979                0 2.985399e-08 2.347727e-07
 sihzPFxjsGQrSWoygu3EicSMSkaDDJZ1ymvYB7yPRzL       .si 2026-10-04 12:05:26.845000+00:00          1933         894         1039            1933                0 2.853383e-08 2.863335e-07
FQx7siGvemHtn4onzsrkrEPpWAh4qWSUfchN6z1Qpump     CRAWL 2026-10-04 12:10:15.813000+00:00          1307         960          347            1307                0 2.795899e-08 2.834036e-08
4Aw8j4ai5d9VpzAiifEs1ig1Hom8ciFag5L4jV6kpump      riff 2026-10-04 12:15:38.673000+00:00          1197         760          437            1197                0 9.920258e-12 3.267774e-07

Tokens with at least 20 observed trades, including buys and sells: 335

Best candidate for our first sequence inspection:
mint               DoVAVzViX8Bjy3r15nwikSaSbzE6dV4ovd28aWpJpump
symbol                                                    HIGGS
launch_time                    2026-10-04 12:26:34.860000+00:00
total_trades                                              28725
buy_events                                                15082
sell_events                                               13643
pumpfun_events                                             2768
pumpswap_events                                           25957
min_price                                                   0.0
max_price                                              0.000008

---

# chatgpt response

Good. We found a useful candidate for our first trading-sequence inspection: **HIGGS**, mint `DoVAVzViX8Bjy3r15nwikSaSbzE6dV4ovd28aWpJpump`.

Your scan found 28,725 buy/sell events for this token during the selected hour, including 2,768 Pump.fun events and 25,957 PumpSwap events. That gives us activity from both protocols in one archive window.

One limitation: the selected hour only covers approximately 33 minutes after HIGGS launched. We should inspect the observed sequence before assuming it contains the token's entire lifecycle.

## Step 33 — Extract HIGGS's actual trade sequence

**Goal:** Save only HIGGS events from the October 4, 2026, 12:00–13:00 UTC archive hour, then inspect the timestamps, protocol transition, prices, and ordering.

This cell streams the same archive file again but keeps only the selected mint in memory. It does not download the full archive into a DataFrame.

<CmpSwap events found.")
</CodeBlock>

### What to send back

Paste the extraction summary, ordering diagnostics, the first and last event tables, and the protocol-transition table.

We'll use those results to decide how to build a reliable per-token price series. We need to distinguish event time from observation time and understand any block-order reversals before simulating buy/sell decisions.

---

# you asked

Extracting mint: DoVAVzViX8Bjy3r15nwikSaSbzE6dV4ovd28aWpJpump
Archive hour: 2026/10/04/12

=== Extraction summary ===
Archive lines scanned: 1107318
HIGGS events extracted: 28847
Unique signatures: 28734
Unique blocks: 5467
First event time: 2026-10-04 12:26:34+00:00
Last event time:  2026-10-04 12:59:59+00:00

=== Actions and protocols ===
action      buy  create  createPool   sell    All
protocol                                         
METEORA      65       0           1     53    119
PUMPFUN    1633       2           0   1135   2770
PUMPSWAP  13449       0           1  12508  25958
All       15147       2           2  13696  28847

=== Ordering diagnostics ===
Block decreases in archive order: 184
Observed timestamp decreases (seconds): 1
Zero or missing top-level prices: 5

Positive price range: 2.983021808809611e-08 to 233482947.9420168
Positive price observations: 28842

=== First 10 HIGGS events in archive order ===
 archive_seq            event_time_utc                observed_time_utc     block action protocol        price  quoteAmount  tokenAmount
      540630 2026-10-04 12:26:34+00:00 2026-10-04 12:26:34.860000+00:00 453256170    buy  PUMPFUN 2.983022e-08     0.987654 3.419920e+07
      540631 2026-10-04 12:26:34+00:00 2026-10-04 12:26:34.860000+00:00 453256170 create  PUMPFUN          NaN          NaN          NaN
      540632 2026-10-04 12:26:34+00:00 2026-10-04 12:26:34.860000+00:00 453256170 create  PUMPFUN          NaN          NaN          NaN
      541971 2026-10-04 12:26:38+00:00 2026-10-04 12:26:38.990000+00:00 453256186    buy  PUMPFUN 3.479122e-08     1.185542 3.532741e+07
      541972 2026-10-04 12:26:38+00:00 2026-10-04 12:26:38.991000+00:00 453256186    buy  PUMPFUN 3.729150e-08     1.181637 3.280532e+07
      541973 2026-10-04 12:26:38+00:00 2026-10-04 12:26:38.993000+00:00 453256186    buy  PUMPFUN 3.236986e-08     1.292150 4.158286e+07
      541974 2026-10-04 12:26:38+00:00 2026-10-04 12:26:38.993000+00:00 453256186    buy  PUMPFUN 3.998529e-08     1.229560 3.184158e+07
      541981 2026-10-04 12:26:38+00:00 2026-10-04 12:26:39.016000+00:00 453256186    buy  PUMPFUN 7.076731e-08    11.851852 2.228024e+08
      541986 2026-10-04 12:26:38+00:00 2026-10-04 12:26:39.030000+00:00 453256186    buy  PUMPFUN 7.223929e-08     0.493827 6.906721e+06
      541987 2026-10-04 12:26:38+00:00 2026-10-04 12:26:39.035000+00:00 453256186    buy  PUMPFUN 7.342778e-08     0.395062 5.424354e+06

=== Last 10 HIGGS events in archive order ===
 archive_seq            event_time_utc                observed_time_utc     block action protocol    price  quoteAmount   tokenAmount
     1106941 2026-10-04 12:59:58+00:00 2026-10-04 12:59:59.152000+00:00 453263640    buy  METEORA 0.000003     0.000012      3.678591
     1106942 2026-10-04 12:59:58+00:00 2026-10-04 12:59:59.152000+00:00 453263640   sell PUMPSWAP 0.000003     0.000012      3.678591
     1106954 2026-10-04 12:59:58+00:00 2026-10-04 12:59:59.169000+00:00 453263640   sell PUMPSWAP 0.000003     0.124008  37180.451218
     1106974 2026-10-04 12:59:58+00:00 2026-10-04 12:59:59.229000+00:00 453263641   sell PUMPSWAP 0.000003     0.099793  29833.849906
     1106976 2026-10-04 12:59:58+00:00 2026-10-04 12:59:59.232000+00:00 453263640    buy PUMPSWAP 0.000003     0.497500 147332.781274
     1107023 2026-10-04 12:59:58+00:00 2026-10-04 12:59:59.327000+00:00 453263641   sell PUMPSWAP 0.000003     0.522408 156546.992243
     1107135 2026-10-04 12:59:58+00:00 2026-10-04 12:59:59.545000+00:00 453263641    buy PUMPSWAP 0.000003     0.135085  40539.563190
     1107227 2026-10-04 12:59:59+00:00 2026-10-04 12:59:59.736000+00:00 453263643   sell PUMPSWAP 0.000003     0.125706  37723.363946
     1107293 2026-10-04 12:59:59+00:00 2026-10-04 12:59:59.882000+00:00 453263644    buy PUMPSWAP 0.000003     0.015492   4650.851637
     1107312 2026-10-04 12:59:59+00:00 2026-10-04 12:59:59.959000+00:00 453263644   sell PUMPSWAP 0.000003     0.541451 162878.990002

=== First PumpSwap event and surrounding records ===
 archive_seq            event_time_utc                observed_time_utc     block     action protocol        price  quoteAmount  tokenAmount
      726354 2026-10-04 12:36:15+00:00 2026-10-04 12:36:15.867000+00:00 453258340        buy  PUMPFUN 4.007948e-07     0.195556 4.887608e+05
      726415 2026-10-04 12:36:15+00:00 2026-10-04 12:36:15.922000+00:00 453258340        buy  PUMPFUN 4.021901e-07     0.197531 4.919922e+05
      726462 2026-10-04 12:36:15+00:00 2026-10-04 12:36:16.007000+00:00 453258341        buy  PUMPFUN 4.027519e-07     0.079451 1.974078e+05
      726468 2026-10-04 12:36:15+00:00 2026-10-04 12:36:16.027000+00:00 453258341        buy  PUMPFUN 4.096988e-07     0.977778 2.407072e+06
      726516 2026-10-04 12:36:15+00:00 2026-10-04 12:36:16.253000+00:00 453258342        buy  PUMPFUN 4.108802e-07     0.165451 4.032555e+05
      726749 2026-10-04 12:36:16+00:00 2026-10-04 12:36:16.782000+00:00 453258344 createPool PUMPSWAP          NaN          NaN          NaN
      726780 2026-10-04 12:36:16+00:00 2026-10-04 12:36:16.845000+00:00 453258344        buy PUMPSWAP 3.257895e-07     0.105000 2.521480e+05
      726820 2026-10-04 12:36:16+00:00 2026-10-04 12:36:16.916000+00:00 453258344        buy PUMPSWAP 3.266890e-07     0.175000 4.188836e+05
      726835 2026-10-04 12:36:16+00:00 2026-10-04 12:36:16.981000+00:00 453258344       sell PUMPSWAP 3.281911e-07     0.037761 9.137090e+04
      726836 2026-10-04 12:36:16+00:00 2026-10-04 12:36:16.986000+00:00 453258344        buy PUMPSWAP 3.281908e-07     0.000030 7.230147e+01
      726842 2026-10-04 12:36:16+00:00 2026-10-04 12:36:17.032000+00:00 453258344        buy PUMPSWAP 3.278627e-07     0.000020 4.781259e+01

---

# chatgpt response

The HIGGS extraction is large enough to study, but it reveals two data-quality problems we should resolve before building a price path: 184 block-order reversals and top-level prices spanning from about $3\times10^{-8}$ to over 233 million. We should not treat that maximum as a real market move. Next, we'll inspect the extreme records and compare top-level prices with each event's swap-leg price before cleaning or sorting anything.

The HIGGS sequence is useful, and we found an important detail in the official Shrine schema: **prices are denominated in the pool's quote asset, and the top-level `price` represents the post-trade pool state.** The `breakdown` array records individual swap legs. Those prices are related, but they are not necessarily equal. <Cite refs={["turn201196view0"]}/>

We should investigate the extreme prices before calling them bad data. A token can have multiple pools, and comparing prices from different quote assets would produce misleading results.

## Step 34 — Audit quote assets and extreme prices

**Goal:** Find out whether HIGGS's unusually large prices come from a different quote asset, a specific pool, or genuinely anomalous records. We'll also inspect repeated transaction signatures without deleting anything.

Run this as one new cell in Colab. It uses `higgs_events` from Step 33 and does not download the archid(15)
    .to_string(index=False)
)
</CodeBlock>

### What we'll learn

The first two tables tell us whether prices from different quote assets have been mixed. The extreme-price table will help identify whether the biggest values belong to a distinct asset or pool. The signature check will tell us whether duplicate records represent multiple legitimate events in one transaction.

Shrine documents that a transaction can contain multiple swaps and that its archive is occasionally out of order; it recommends sorting by block and signature when event ordering matters. We should preserve the original archive sequence as well, rather than blindly deduplicating by signature. <Cite refs={["turn290491view0","turn201196view0"]}/>

Paste the output of Step 34. We'll use it to define the correct price series before simulating any tading actions.

---

# chatgpt response

Step 34 has identified the main data-quality issue. We now know how to build a cleaner first price sequence for HIGGS.

## What the results mean

**1. The enormous prices are almost certainly invalid records.**

The four largest prices belong to `METEORA` events. Their `quoteAmount` is exactly `1.844674e10` SOL—a value consistent with a numeric overflow or sentinel, not a realistic trade amount. The resulting prices, reaching 233 million SOL per token, should not enter our price series.

**2. We'll start with Pump.fun and PumpSwap only.**

These protocols give us the initial bonding-curve trades and the subsequent PumpSwap pool trades. Their observed prices are within a much more plausible range for this token. We'll leave Meteora out of this first experiment, not assume its entire data feed is invalid.

**3. Don't deduplicate by transaction signature.**

The 112 repeated signatures mostly reflect transactions represented by multiple protocol events. For example, a single signature can contain a Meteora buy and a PumpSwap sell. Deleting every repeated signature would lose legitimate market information.

**4. Use observation time for the initial trading sequence.**

We'll order events by `observed_time_utc`, then block and original archive sequence. This better represents when a bot could have learned about an event than simply ordering by the block timestamp. Same-time events still require conservative treatment in an execution simulator.

## Step 35 — Build the first clean HIGGS price path

**Goal:** Create a reusable, filtered table of actual buy/sell events and inspect the transition from Pump.fun to PumpSwap.

Run this as one new cell in Colab. It reuses `higgs_events` from Step 33; no download is needed.

<Codelayout()
plt.show()
</CodeBlock>

### What to send back

Paste the initial trade selection, clean price path summary, protocol transition, and the chart.

This is still a descriptive price reconstruction—not a trading backtest. Once the sequence looks coherent, the next step is to define a realistic simulated entry and exit using an observation delay and execution costs. We should not let the agent buy at a price that was only known after the transaction had already happened.

---

# you asked

=== Initial trade selection ===
Candidate trades: 28725
Invalid prices: 0
Invalid trade amounts: 0

=== Clean price path ===
Rows retained: 28725
Rows excluded: 0
Unique signatures: 28725
Unique pools: 2
First observed trade: 2026-10-04 12:26:34.860000+00:00
Last observed trade: 2026-10-04 12:59:59.959000+00:00

=== Summary by protocol ===
          trades   buys  sells  pools                   first_observed                    last_observed   first_price  median_price    last_price     min_price     max_price  first_to_last_price_change_pct
protocol                                                                                                                                                                                                     
PUMPFUN     2768   1633   1135      1 2026-10-04 12:26:34.860000+00:00 2026-10-04 12:36:16.253000+00:00  3.000000e-08  2.500000e-07  4.100000e-07  3.000000e-08  4.100000e-07                     1277.395810
PUMPSWAP   25957  13449  12508      1 2026-10-04 12:36:16.845000+00:00 2026-10-04 12:59:59.959000+00:00  3.300000e-07  3.660000e-06  3.110000e-06  3.300000e-07  7.550000e-06                      854.673044

=== Protocol transition ===
Last Pump.fun observation: 2026-10-04 12:36:16.253000+00:00
Last Pump.fun price: 4.1088017403715614e-07
First PumpSwap observation: 2026-10-04 12:36:16.845000+00:00
First PumpSwap price: 3.2578953639922666e-07
Pump.fun pool: G75N69MfK1vYeqqZPdo6JQTsLwRGf3ka2oTyyU489zZx
PumpSwap pool: BFrSZakeqNzVtM3EFhroo4eRhagmmWN8BRntiQKFH6Ru

---

# chatgpt response

Step 35 looks good. We've successfully reconstructed HIGGS's observed trading activity across two pools.

## What the chart tells us

<box border radius="lg" padding={3} gap={3}>
  <row align="center" gap={3}>
    <box flex="1" gap={1}>
      <text color="secondary" size="sm">Pump.fun curve</text>
      <title size="xl">+1,277%</title>
      <text color="secondary" size="xs">First to last observed price</text>
    </box>
    <box flex="1" gap={1}>
      <text color="secondary" size="sm">PumpSwap pool</text>
      <title size="xl">+855%</title>
      <text color="secondary" size="xs">First to last observed price</text>
    </box>
  </row>
</box>

These are historical price changes, not simulated trading returns. In particular, the approximately 20% price difference at migration must **not** automatically be treated as a real loss: Pump.fun and PumpSwap are separate pools, and their recorded prices may not be directly comparable.

We have 27,725? Actually, your output reports **28,725 clean trade events** across 27,725? No—the correct count is 28,725, consisting of 2,768 Pump.fun events and 25,957 PumpSwap events. We should preserve those counts exactly.

## Step 36 — Measure forward price movement

Now we   forward_summary.drop(columns="pool")
        .round(3)
        .to_string(index=False)
    )

    print("\nNote:")
    print("- Returns are measured within each pool, not across migration.")
    print("- Coverage falls at longer horizons near the end of each pool's data.")
    print("- These are price changes, not realized trading profits.")
    print("- Fees, entry delay, trade impact, and exit costs are not yet modeled.")
</CodeBlock>

### How to interpret the output

The median return tells us the typical direction of price movement. The positive-return percentage tells us how often the future price exceeds the observed entry reference. The 10th and 90th percentiles show how wide the outcomes are.

The coverage column is important too: the Pump.fun curve has a much shorter observation window than PumpSwap, so longer forward horizons will have fewer usable observations.

Run Step 36 and paste the complete output. Next, we'll decide how to introduce execution delay and trading costs without confusing historical price movement with actual profitability.

---

# you asked

Processing PUMPFUN pool
Events: 2768
First observation: 2026-10-04 12:26:34.860000+00:00
Last observation:  2026-10-04 12:36:16.253000+00:00

Processing PUMPSWAP pool
Events: 25957
First observation: 2026-10-04 12:36:16.845000+00:00
Last observation:  2026-10-04 12:59:59.959000+00:00

=== Forward price-movement summary ===
protocol  horizon_seconds  entry_observations  valid_forward_observations  coverage_pct  median_return_pct  mean_return_pct  positive_return_pct  p10_return_pct  p90_return_pct  median_actual_wait_s
 PUMPFUN                5                2768                        2749        99.314              0.037            2.011               50.455         -11.517          23.146                 5.150
 PUMPFUN               15                2768                        2701        97.579              0.560            6.872               51.388         -23.495          53.913                15.165
 PUMPFUN               30                2768                        2647        95.629             -2.816            4.524               44.730         -35.754          41.989                30.185
 PUMPFUN               60                2768                        2530        91.402             -0.819            4.367               49.328         -37.203          47.533                60.258
 PUMPFUN              180                2768                        2085        75.325             34.107           49.549               79.376         -10.419         131.693               180.255
PUMPSWAP                5               25957                       25930        99.896              0.655            1.126               54.150          -8.444          10.567                 5.039
PUMPSWAP               15               25957                       25867        99.653              1.912            3.406               58.066         -13.292          21.270                15.041
PUMPSWAP               30               25957                       25762        99.249              4.677            7.518               61.416         -18.157          34.197                30.041
PUMPSWAP               60               25957                       25579        98.544              6.437           14.461               60.487         -18.866          55.262                60.044
PUMPSWAP              180               25957                       25245        97.257             23.782           40.713               64.904         -28.234         115.154               180.049

Note:
- Returns are measured within each pool, not across migration.
- Coverage falls at longer horizons near the end of each pool's data.
- These are price changes, not realized trading profits.
- Fees, entry delay, trade impact, and exit costs are not yet modeled.

---

# chatgpt response

Step 36 shows continued upward price movement in HIGGS, especially after it migrated to PumpSwap. But we need to be careful: **HIGGS was selected because it was the most active token in the hour**, so this is a selected example, not evidence that newly launched tokens generally have this behavior.

The results so far:

- PumpSwap's median forward return was +0.655% over 5 seconds and +6.437% over 60 seconds.
- Its 10th-percentile return was −8.444% over 5 seconds and −18.866% over 60 seconds.
- Mean returns were considerably higher than median returns, showing that large positive moves influenced the averages.

These are overlapping historical price observations, not independent trades or realized profits.

## Step 37 — Stress-test observation and execution delay

**Goal:** Measure how much of the forward price movement remains when the simulated bot waits 1, 3, or 5 seconds before entering.

We'll calculate results separately for Pump.fun and PumpSwap. The zero-delay case is an optimistic reference, not a realistic execution assumption.

Run this as one new cell in your existing Colab notebook.

<Cpresentative sample.")
</CodeBlock>

### How we'll interpret the result

We want to see whether the median forward return and positive-return rate deteriorate as latency increases, particularly over short holding periods.

Even if positive returns persist after five seconds, that doesn't establish profitability. The eventual trading simulator must account for executable entry and exit prices, trade size, liquidity, fees, and slippage. We also need to test this on many tokens selected without looking into their future activity.

Paste the complete output of Step 37. We'll interpret it before building the first actual trading simulation.

---

# you asked

=== Forward returns after simulated entry delay ===
protocol  latency_s  holding_s  signals  valid_pairs  coverage_pct  median_return_pct  mean_return_pct  positive_pct  p10_pct  p90_pct  median_actual_entry_delay_s
 PUMPFUN          0          5     2768         2749        99.314              0.037            1.993        50.455  -11.517   23.272                        0.000
 PUMPFUN          0         15     2768         2701        97.579              0.553            6.820        51.351  -23.495   53.913                        0.000
 PUMPFUN          0         30     2768         2647        95.629             -2.837            4.450        44.692  -35.743   41.914                        0.000
 PUMPFUN          0         60     2768         2530        91.402             -0.819            4.331        49.368  -37.203   47.533                        0.000
 PUMPFUN          0        180     2768         2085        75.325             34.138           49.468        79.376  -10.399  131.693                        0.000
 PUMPFUN          1          5     2768         2743        99.097              0.095            2.002        50.820  -10.707   23.558                        1.131
 PUMPFUN          1         15     2768         2690        97.182              0.405            7.484        50.929  -21.973   55.020                        1.132
 PUMPFUN          1         30     2768         2643        95.484             -3.144            1.273        44.419  -35.328   37.100                        1.128
 PUMPFUN          1         60     2768         2525        91.221             -1.143            4.566        47.485  -36.567   47.319                        1.126
 PUMPFUN          1        180     2768         2078        75.072             36.207           49.233        78.152  -10.321  132.159                        1.114
 PUMPFUN          3          5     2768         2737        98.880              0.261            2.676        52.284  -11.470   30.486                        3.145
 PUMPFUN          3         15     2768         2681        96.857              0.086            6.416        50.131  -21.973   53.672                        3.144
 PUMPFUN          3         30     2768         2641        95.412             -3.213            0.869        43.544  -26.759   36.762                        3.144
 PUMPFUN          3         60     2768         2518        90.968             -1.556            4.438        48.133  -37.754   46.192                        3.141
 PUMPFUN          3        180     2768         2064        74.566             36.189           49.590        79.990  -10.914  137.765                        3.133
 PUMPFUN          5          5     2768         2731        98.663              0.349            4.842        52.325  -11.542   37.700                        5.150
 PUMPFUN          5         15     2768         2676        96.676             -0.507            5.312        48.094  -19.923   43.533                        5.149
 PUMPFUN          5         30     2768         2635        95.195             -3.144            0.714        43.416  -22.782   36.700                        5.148
 PUMPFUN          5         60     2768         2514        90.824             -1.063            4.542        49.324  -37.754   45.694                        5.145
 PUMPFUN          5        180     2768         2037        73.591             38.035           50.738        81.934   -9.170  130.851                        5.135
PUMPSWAP          0          5    25957        25930        99.896              0.647            1.125        54.157   -8.427   10.552                        0.000
PUMPSWAP          0         15    25957        25867        99.653              1.922            3.407        58.105  -13.277   21.279                        0.000
PUMPSWAP          0         30    25957        25762        99.249              4.677            7.513        61.482  -18.116   34.195                        0.000
PUMPSWAP          0         60    25957        25579        98.544              6.444           14.467        60.499  -18.866   55.299                        0.000
PUMPSWAP          0        180    25957        25245        97.257             23.795           40.713        64.912  -28.275  115.014                        0.000
PUMPSWAP          1          5    25957        25921        99.861              0.806            1.187        55.029   -8.342   10.348                        1.038
PUMPSWAP          1         15    25957        25860        99.626              1.953            3.412        57.997  -12.867   21.319                        1.038
PUMPSWAP          1         30    25957        25755        99.222              4.752            7.613        61.639  -18.191   34.254                        1.037
PUMPSWAP          1         60    25957        25572        98.517              6.491           14.324        60.363  -18.743   54.571                        1.037
PUMPSWAP          1        180    25957        25241        97.242             23.934           40.472        64.863  -28.267  114.607                        1.037
PUMPSWAP          3          5    25957        25910        99.819              0.698            1.166        54.774   -8.501   10.305                        3.039
PUMPSWAP          3         15    25957        25852        99.595              2.037            3.461        57.965  -13.304   21.038                        3.039
PUMPSWAP          3         30    25957        25741        99.168              4.873            7.570        61.532  -18.209   34.395                        3.039
PUMPSWAP          3         60    25957        25563        98.482              6.609           14.032        59.766  -18.909   53.701                        3.039
PUMPSWAP          3        180    25957        25236        97.222             23.039           40.242        64.753  -28.758  112.825                        3.038
PUMPSWAP          5          5    25957        25897        99.769              0.817            1.205        54.891   -8.595   10.308                        5.039
PUMPSWAP          5         15    25957        25835        99.530              2.215            3.567        58.692  -13.428   21.461                        5.039
PUMPSWAP          5         30    25957        25726        99.110              4.920            7.591        61.879  -18.380   35.436                        5.039
PUMPSWAP          5         60    25957        25544        98.409              6.458           13.943        60.237  -19.122   54.088                        5.038
PUMPSWAP          5        180    25957        25219        97.157             23.587           40.020        64.388  -27.999  112.840                        5.038

Important limitations:
1. Every observed event is treated as a hypothetical signal.
2. These observations overlap heavily.
3. Reference prices are not executable trade quotes.
4. Fees, price impact, failed transactions and exit latency are not included.
5. HIGGS was selected for high activity, so this is not a representative sample.

---

# chatgpt response

Step 37 is complete. The main lesson is that adding 1–5 seconds of simulated delay did not erase HIGGS's upward price trend, but **this is still one unusually active token selected after inspecting the archive**. We cannot generalize its returns to newly launched memecoins.

For PumpSwap, the median 60-second return stayed around +6.4% across the tested delays. However, the 10th percentile remained around −19%, and these measurements exclude execution costs and price impact.

## Step 38 — Test a random sample of launches

We'll move beyond HIGGS and select **100 launches uniformly at random** from the 1,082 classic SOL-quoted launches found in the October 4 archive hour. This avoids selecting the tokens with the highest future activity.

For this first cross-token check, we'll examine only Pump.fun curve trades, use a one-second observation delay, and measure forward price changes over 5, 15, 30, and 60 seconds. Tokens without enough subsequent observations will remain in the coverage counts rather than being assigned fabricated returns.

Run this as one new cell in your existing Colab notebook.

<ns, and exit latency.")
</CodeBlock>

### What to send back

Paste the sample coverage and forward-price summary. The crucial figures are how many of the 100 launches have an observable entry and what percentage of the sample has usable 5–60 second outcomes.

If the coverage is adequate, we'll have our first less-selection-biased estimate of short-term price behavior across multiple tokens. It will still be a descriptive baseline, not a profitable strategy or a trained PPO agent.

---

# you asked

=== Random sample ===
Available launches: 1082
Sampled launches: 100
Sampling seed: 20261004

=== Observed sample activity ===
Sampled launches: 100
Sampled launches with Pump.fun trades: 99
Matching Pump.fun trades: 12419

=== Sample coverage ===
Launches with observed curve trades: 99
Launches with a reference entry: 48
Launches with no curve trades: 1

=== Cross-token forward price changes ===
           valid_tokens  median_return_pct  mean_return_pct  positive_return_pct  p10_return_pct  p90_return_pct  median_actual_hold_s  coverage_of_sample_pct
horizon_s                                                                                                                                                     
5                    28             -3.090           -1.272               35.714         -21.569          14.323                 5.485                    28.0
15                   20             -1.813            3.290               45.000         -17.653          23.657                15.668                    20.0
30                   12             -6.718           12.403               41.667         -20.088          54.790                30.352                    12.0
60                    4             22.382           23.593               50.000         -24.580          72.734                60.346                     4.0

Limitations:
- The sample covers one archive hour only.
- Price changes are conditional on a usable curve entry and exit reference.
- Pool migration can end the Pump.fun-only price path.
- Returns exclude fees, price impact, failed transactions, and exit latency.

---

# chatgpt response

Step 38 gives us a useful warning: **we don't yet have enough usable observations to estimate typical short-term returns reliably.**

The random sample contained 100 launches, but only 28 had usable five-second forward returns, and only four had usable 60-second returns. The five-second median was −3.09%, but this is based on just 28 tokens and excludes trading costs.

The main limitation is that Step 38 followed only Pump.fun curve trades. Once a token migrates to PumpSwap, the curve-only sequence ends even though the token may continue trading actively.

## Step 39 — Include both Pump.fun and PumpSwap

We'll reuse the same 100 randomly selected launches and scan the archive again, this time collecting trades from both protocols. We'll anchor each hypothetical entry to the launch time, allow a one-second observation delay, and require an observed trade within five additional seconds.

For forward returns, we'll distinguish exits observed in the **same pool** from exits observed in a **different pool**. That distinction matters because migration can create a price discontinuity, and we should not silently mix the two.

Run this as one new cell in Colab.

<ency are not modeled.")
</CodeBlock>

### What to send back

Paste the entry coverage and forward-return summary. We'll check whether including PumpSwap improves the number of usable observations, and whether returns differ substantially between same-pool and cross-pool outcomes.

Even with better coverage, this one-hour sample remains exploratory. The next meaningful test will need a broader, time-stratified sample of launches rather than a single day's most active hour.

---

# you asked

Scanning the same archive hour for both protocols...

=== Expanded event coverage ===
Selected launches: 100
Mints with trade events: 99
Matching trade events: 12419

Trades by protocol:
          events  tokens  buys  sells
protocol                             
PUMPFUN    12419      99  6746   5673

=== Entry coverage ===
Selected launches: 100
Eligible entries: 56
Entry protocol counts: {'PUMPFUN': 56}
Median observed entry delay from launch (s): 1.602

=== Forward return coverage by pool relationship ===
 horizon_s  same_pool  tokens  observations  median_return_pct  mean_return_pct  positive_return_pct  p10_return_pct  p90_return_pct  median_actual_hold_s  sample_coverage_pct
         5       True      29            29             -2.794           -1.239               34.483         -21.458          14.057                 5.526                 29.0
        15       True      20            20             -1.813            3.290               45.000         -17.653          23.657                15.668                 20.0
        30       True      14            14             -2.526           17.634               50.000         -19.231          68.661                30.352                 14.0
        60       True       6             6             51.442           57.803               66.667         -23.675         145.642                60.666                  6.0

Assumptions and limitations:
- A price observation is used as a reference, not a guaranteed fill.
- Pool migrations are explicitly flagged, not silently treated as continuous.
- Tokens that fail entry or exit timing checks remain out of coverage.
- Fees, price impact, transaction failures, and exit latency are not modeled.

---

# chatgpt response

Step 39 did **not** capture any PumpSwap trades. The output contains only 12,419 Pump.fun events, exactly the same number as Step 38.

That means the experiment hasn't yet tested whether including PumpSwap improves coverage. The unchanged results are not evidence that migrated tokens stop trading; we need to find out why those events weren't included.

## Step 40 — Diagnose the missing PumpSwap events

We'll first check whether our randomly selected launches were expected to have PumpSwap trades. The `candidates` table from Step 32 already contains the event counts, so we don't need to download the archive again.

Run this single new cell in Colab.

5).to_string()
        )
</CodeBlock>

### What to send back

Paste the complete output. If the original scan shows many expected PumpSwap events, we'll inspect the affected records and correct the extraction logic before rerunning the forward-return analysis. If the sample genuinely contains no PumpSwap activity, we'll investigate the sampling procedure instead.

We should not proceed to a broader trading simulation until this discrepancy is resolved.

---

# you asked

=== Sample metadata from the original archive scan ===
                                        mint     symbol  total_trades  pumpfun_events  pumpswap_events
4PGLXUiJifgpfYaWUvm2YS3GgNhEEGnpxoHxC7cSpump       CULT           301             301                0
AXY9AY3dfsybAP9LfYWPYqaFHTE9vUGTiCBiqnfUT9g3   HIGGSCAT          1979            1979                0
39Y8teb9Wec5KiRmxFCPVz4qZKtuQTzJgzoNxikpp5Za    DIANABW            11              11                0
53pYFFaapfK5CtQ5nZVc7jfAUswBJ5CFN597rbyokKDx    Traders             2               2                0
5RRjgGotqb4DsgejoX42CafC7ZVY2RrXyaifVxn78GRn      FYSUT            12              12                0
7H6hGKNEpnHJn6pdCgFyCLdqgroRc4f51vUjuXtcpump         jp             6               6                0
HFWkNnzgeoKHDVeWxN5n2WtMLHHVr1vvXptQzeDTpump       SPOT            11              11                0
6zC7WmyeL9zoQFVZaC7ojbAFkXKDaPq4rrtTTKgspump      SIWIF            13              13                0
8AGZxx8NZZvBwTYXqc6UrBbNJ74wJPPd8GYApRrwpump    SpIurge            57              57                0
51Me8Yck6Lert7LYMtQ65P3Pp6L8JZYjWmRuewaZpump        INU             6               6                0
D2k54eSeYoACTToc7qh1wGdhJfPFs7dJAakvu5Jtpump    BANDOAI             3               3                0
Erc12GjJ4uPSudh7M9PrwbWQKofBYcBvTy9hjKe1pump      RIVET           134             134                0
Ew1J35zGpKAibuAq751YeSRVYJNWcjYLYMMPHfATZWVk    CARDCAT             3               3                0
EJwc4YBw3qUXCbsG79vteGivNhHdQNqVkgwsiA1Rpump       TUNG             4               4                0
8zqyUUFLvCgWQnFfeV2qbdnrArdxV4G3xneQSKeQQ3d1 CROSSYCOIN             0               0                0

=== Expected PumpSwap coverage ===
Sampled mints: 100
Mints with PumpSwap events in Step 32: 0
Total expected PumpSwap events: 0

=== Actual extracted protocol coverage ===
          events  mints
protocol               
PUMPFUN    12419     99

=== Largest PumpSwap discrepancies ===
                                              expected_pumpswap  extracted_pumpswap  missing_from_extraction
4PGLXUiJifgpfYaWUvm2YS3GgNhEEGnpxoHxC7cSpump                  0                 0.0                      0.0
AXY9AY3dfsybAP9LfYWPYqaFHTE9vUGTiCBiqnfUT9g3                  0                 0.0                      0.0
39Y8teb9Wec5KiRmxFCPVz4qZKtuQTzJgzoNxikpp5Za                  0                 0.0                      0.0
53pYFFaapfK5CtQ5nZVc7jfAUswBJ5CFN597rbyokKDx                  0                 0.0                      0.0
5RRjgGotqb4DsgejoX42CafC7ZVY2RrXyaifVxn78GRn                  0                 0.0                      0.0
7H6hGKNEpnHJn6pdCgFyCLdqgroRc4f51vUjuXtcpump                  0                 0.0                      0.0
HFWkNnzgeoKHDVeWxN5n2WtMLHHVr1vvXptQzeDTpump                  0                 0.0                      0.0
6zC7WmyeL9zoQFVZaC7ojbAFkXKDaPq4rrtTTKgspump                  0                 0.0                      0.0
8AGZxx8NZZvBwTYXqc6UrBbNJ74wJPPd8GYApRrwpump                  0                 0.0                      0.0
51Me8Yck6Lert7LYMtQ65P3Pp6L8JZYjWmRuewaZpump                  0                 0.0                      0.0
D2k54eSeYoACTToc7qh1wGdhJfPFs7dJAakvu5Jtpump                  0                 0.0                      0.0
Erc12GjJ4uPSudh7M9PrwbWQKofBYcBvTy9hjKe1pump                  0                 0.0                      0.0
Ew1J35zGpKAibuAq751YeSRVYJNWcjYLYMMPHfATZWVk                  0                 0.0                      0.0
EJwc4YBw3qUXCbsG79vteGivNhHdQNqVkgwsiA1Rpump                  0                 0.0                      0.0
8zqyUUFLvCgWQnFfeV2qbdnrArdxV4G3xneQSKeQQ3d1                  0                 0.0                      0.0

---

# chatgpt response

We've found the reason Step 39 didn't improve coverage: **all 100 randomly selected launches had zero PumpSwap events in the selected archive hour.** The extraction code agrees with the original scan, so this is a sampling issue rather than a parsing failure.

That does not mean those tokens never migrated; it means PumpSwap activity was not observed for them in this particular hour.

## Step 41 — Create a stratified sample

Instead of drawing another purely random sample, we'll deliberately select up to 50 launches with observed PumpSwap activity and up to 50 without it. This will let us inspect both types of price path.

This is a diagnostic sample, not a representative sample for estimating market-wide probabilities. We are intentionally oversampling tokens with PumpSwap activity.

Run this one new cell in Colab. It uses the `candidates` table already in memory; no archive download is needed.

to_string(index=False)
)
</CodeBlock>

### What to send back

Paste the activity-strata summary and the selected-launch counts. If the sample includes enough tokens with PumpSwap activity, our next cell will extract their trade sequences and quantify the usable entry/exit coverage across both protocols.

We will keep same-pool and cross-pool returns separate and continue treating the results as exploratory—not as evidence of a profitable strategy.

---

# you asked

=== Activity strata in the launch universe ===
Unique launches: 1082
               launches  median_total_trades  median_pumpswap_events  total_pumpswap_events
pumpswap_seen                                                                              
False              1066                  8.0                     0.0                      0
True                 16               4746.0                  4439.5                 112807

=== Stratified sample ===
Total selected: 66
With PumpSwap observed: 16
Without PumpSwap observed: 50

=== Selected launches ===
                                        mint    symbol                      launch_time  pumpfun_events  pumpswap_events  total_trades  pumpswap_seen
DoVAVzViX8Bjy3r15nwikSaSbzE6dV4ovd28aWpJpump     HIGGS 2026-10-04 12:26:34.860000+00:00            2768            25957         28725           True
98FPTSbFm3m8w3YMWLK9Ke2Fjt3SdZtNcSCFZcgWpump    Gemini 2026-10-04 12:17:47.988000+00:00               1            17192         17193           True
 nMnddwSU83WJ5NnVzocrBdnmGJQBHnLYyCscKEWpump Robinhood 2026-10-04 12:03:38.230000+00:00               1            16925         16926           True
HTYuNpG6eWjQqt5fznEgU1hFVmaV8DYrMJKtvhuas5xN     Joker 2026-10-04 12:29:17.864000+00:00               1            10301         10302           True
A3WUfYA5DRCBX8PQTyk9tvaUxrte2bb76qUsev4Rwswx      LEGO 2026-10-04 12:20:00.288000+00:00               1             7455          7456           True
ChUdczuMMJRnLPyg9nFrED4oULt6h2TL8UimW3Ub97Qb     Tesla 2026-10-04 12:44:13.213000+00:00               1             6379          6380           True
FvEtxYTGk6UxgKvcHETh3oCVDQbQFgLdupf8rzcNpump  VIRTUALZ 2026-10-04 12:16:37.252000+00:00            2792             2707          5499           True
AYXqgh4Ryy1VwQX2hpKxX1yrNXj4JKehw8WAeC8epump   knightT 2026-10-04 12:14:19.865000+00:00               6             5001          5007           True
HJ2QzKWG5WxxPgJNu6dABfchZDfJLgk3BnhAH2NZpump    NVIDIA 2026-10-04 12:17:25.650000+00:00               1             4484          4485           True
8Y5AP9NqanQbQHn253HB2ns9ZDWyba3vxoHTdhern886    SpaceX 2026-10-04 12:50:44.132000+00:00               1             4395          4396           True
BBirK74KfPezj25Z9tGcb5gAD3tKgmtQqcBzx3LBpump    NVIDIA 2026-10-04 12:46:53.818000+00:00               1             3552          3553           True
C2FSFMFRE3E68AQ1yHTNAb2NRMfeFSXkpTKmx4Ehpump   MEOWFIA 2026-10-04 12:31:27.462000+00:00            1031             2432          3463           True
7QJ3BnoFkuxBFtqS3MsAN9EeMeoytob7H7KAFP38pump     HIGGS 2026-10-04 12:51:52.742000+00:00               1             3058          3059           True
7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump     TR4CE 2026-10-04 12:46:27.744000+00:00            1219             1748          2967           True
4mqskjYrrcfvZ4VeveJZtUeJjoRqiV5FdDeNChU2pump   Odyssey 2026-10-04 12:56:40.204000+00:00               1             1011          1012           True
BK77PdW4i5ThuoMsStmqYVCpVTSNUzve63iCTjgLpump    Apency 2026-10-04 12:59:09.558000+00:00               6              210           216           True
52JXUnsomfshtLwgfV5E96Trf1ZRHfMboS5FPSNsdHqW        SI 2026-10-04 12:07:44.989000+00:00            1113                0          1113          False
Dy5wN9Mo7sfQg48maK9mnx8ErHwjBfDYeR72N3D3pump Ouroboros 2026-10-04 12:01:28.075000+00:00             881                0           881          False
3jZX1spEmUMumkarNVzBpUMrVjMUrW5SvnT6Srw9z8xR      NCAT 2026-10-04 12:30:00.683000+00:00             450                0           450          False
52sQ5kFhaTD6NsfN4oKreHZAwxrxgUo129ZCG3EBsVhv    HIGCAT 2026-10-04 12:35:36.614000+00:00             366                0           366          False

---

# chatgpt response

Good. Step 41 gives us a better sample for examining both types of activity:

| Group | Launches | How selected |
|---|---:|---|
| PumpSwap observed | 16 | All launches in this hour with PumpSwap trades |
| No PumpSwap observed | 50 | Random sample from launches without observed PumpSwap trades |
| **Total** | **66** | Stratified diagnostic sample |

The important distinction is that **“no PumpSwap observed” does not mean “never graduated.”** It only describes this archive hour. And because we deliberately included every PumpSwap-active launch, this sample cannot be used to estimate the overall migration rate.

## Step 42 — Extract both protocols and measure same-pool returns

We'll now correct the sampling issue from Step 39 by using `sample_stratified`, not the earlier `sample` variable.

For each of the 66 tokens, we'll look for a reference entry at least one second after launch, allowing up to five additional seconds for an observed trade. We'll then measure 5-, 15-, 30- and 60-second forward prices **within the same pool**. We will not treat a migration into another pool as a continuous price series.

Run this as one new cell in Colab.

<CodeBlock langudeled.")
</CodeBlock>

### What to send back

Paste the extracted event counts, entry coverage and same-pool return summary.

If coverage remains very low for the no-PumpSwap group, that will tell us to sample a longer observation window next, rather than assuming that a single archive hour captures each token's useful price path.

---

# you asked

Scanning the archive for the 66 selected launches...

=== Extracted event coverage ===
Selected launches: 66
Tokens with valid trades: 61
Valid trades: 124551

=== Trades by protocol ===
          events  tokens   buys  sells
protocol                              
PUMPFUN    11744      61   6782   4962
PUMPSWAP  112807      16  58745  54062

=== Reference entry coverage ===
Selected launches: 66
Reference entries found: 44

Entry protocol:
entry_protocol
PUMPFUN     32
PUMPSWAP    12

Entry coverage by sample stratum:
                       entries  median_entry_delay_s
pumpswap_seen_in_hour                               
False                       28                 1.417
True                        16                 1.572

=== Same-pool forward-return coverage ===
 horizon_s  pumpswap_seen_in_hour  tokens  observations  median_return_pct  mean_return_pct  positive_return_pct  p10_return_pct  p90_return_pct  median_actual_hold_s  sample_coverage_pct
         5                  False      11            11              0.290            3.810               54.545          -7.113          16.848                 5.277               16.667
         5                   True      15            15              0.779           18.870              100.000           0.260          47.295                 5.298               22.727
        15                  False       9             9            -11.433           -6.886               33.333         -37.088          31.042                15.406               13.636
        15                   True      11            11              1.477           64.675               90.909           1.095         253.361                15.218               16.667
        30                  False       6             6            -15.669           -0.136               33.333         -35.536          50.799                30.641                9.091
        30                   True      14            14              2.301           79.398               92.857           1.167         224.149                30.120               21.212
        60                  False       5             5             41.493           35.354               60.000         -28.042         104.492                60.703                7.576
        60                   True      13            13              3.447           65.926               92.308           1.312         193.813                60.078               19.697

Limitations:
- This is a deliberately stratified, non-representative sample.
- Entries use observed trades as reference prices, not guaranteed fills.
- Exit observations must be from the same pool as entry.
- Fees, price impact, failed transactions and realistic execution are not modeled.

---

# chatgpt response

Step 42 is complete. We now have evidence that the pool transition matters, but we still don't have a reliable estimate of typical trading returns.

### What the results tell us

- **PumpSwap-active group:** 16 of the 66 selected launches. At five seconds, 15 had usable same-pool returns; the median was +0.779%.
- **No-PumpSwap-observed group:** 50 launches. Only 11 had usable five-second returns, 9 had 15-second returns, and 5 had 60-second returns.
- **Outliers matter:** The PumpSwap-active group's mean 15-second return was +64.675%, while its median was only +1.477%. A few extreme winners substantially affect the mean.

One correction: the reported `sample_coverage_pct` divided by all 66 selected tokens, not by each group's size. Within the groups, five-second coverage was 15/16 = **93.75%** for PumpSwap-active launches and 11/50 = **22%** for the other group.

These groups were deliberately selected based on observed PumpSwap activity. The positive results from the first group therefore cannot be generalized to all new launches.

## Step 43 — Inspect the Pump.fun-to-PumpSwap price transition

Before building an RL environment, we need to understand how the observed price changes when a token moves from its bonding curve to a new pool. We shouldn't silently stitch together price series if the transition creates a material discontinuity.

This step reuses `stratified_trades`; it does not download the archive again.

Run this as one new Colab cell.

<Condex=False)
        )
</CodeBlock>

### What to send back

Paste the transition summary and individual rows.

We'll use those results to decide how to handle migration in the price path. In the eventual simulator, a token's position should remain open across migration, but its valuation and exit must reflect the actual pool available after migration—not an assumed continuous fill at the last bonding-curve price.

---

# you asked

=== Transition sample ===
Tokens with both protocols: 16
Chronologically ordered transitions: 14

=== Transition price differences ===
Valid transitions: 14
count    14.000
mean    -18.697
std       1.847
min     -20.709
10%     -20.709
25%     -20.185
50%     -18.613
75%     -18.612
90%     -16.559
max     -14.337

=== Individual transitions ===
                                        mint  pumpfun_events  pumpswap_events  gap_seconds  last_curve_price  first_pool_price  price_change_pct
A3WUfYA5DRCBX8PQTyk9tvaUxrte2bb76qUsev4Rwswx               1             7455        0.003      4.100000e-07      3.300000e-07        -18.612782
HTYuNpG6eWjQqt5fznEgU1hFVmaV8DYrMJKtvhuas5xN               1            10301        0.003      4.100000e-07      3.300000e-07        -18.612782
BK77PdW4i5ThuoMsStmqYVCpVTSNUzve63iCTjgLpump               6              210        0.005      4.100000e-07      3.500000e-07        -15.679666
ChUdczuMMJRnLPyg9nFrED4oULt6h2TL8UimW3Ub97Qb               1             6379        0.007      4.100000e-07      3.300000e-07        -18.612782
8Y5AP9NqanQbQHn253HB2ns9ZDWyba3vxoHTdhern886               1             4395        0.010      4.100000e-07      3.300000e-07        -18.612782
HJ2QzKWG5WxxPgJNu6dABfchZDfJLgk3BnhAH2NZpump               1             4484        0.014      4.100000e-07      3.300000e-07        -18.612407
 nMnddwSU83WJ5NnVzocrBdnmGJQBHnLYyCscKEWpump               1            16925        0.028      4.100000e-07      3.300000e-07        -18.612782
98FPTSbFm3m8w3YMWLK9Ke2Fjt3SdZtNcSCFZcgWpump               1            17192        0.052      4.100000e-07      3.300000e-07        -18.612407
4mqskjYrrcfvZ4VeveJZtUeJjoRqiV5FdDeNChU2pump               1             1011        0.059      4.100000e-07      3.300000e-07        -18.612407
AYXqgh4Ryy1VwQX2hpKxX1yrNXj4JKehw8WAeC8epump               6             5001        0.064      4.100000e-07      3.500000e-07        -14.337485
DoVAVzViX8Bjy3r15nwikSaSbzE6dV4ovd28aWpJpump            2768            25957        0.592      4.100000e-07      3.300000e-07        -20.709356
7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump            1219             1748        0.609      4.100000e-07      3.300000e-07        -20.709356
C2FSFMFRE3E68AQ1yHTNAb2NRMfeFSXkpTKmx4Ehpump            1031             2432        0.857      4.100000e-07      3.300000e-07        -20.709356
FvEtxYTGk6UxgKvcHETh3oCVDQbQFgLdupf8rzcNpump            2792             2707        3.437      4.100000e-07      3.300000e-07        -20.709356

---

# chatgpt response

Step 43 reveals a remarkably consistent pattern: **14 of the 16 tokens with both protocol types show a lower recorded price at the PumpSwap transition.**

| Transition statistic | Result |
|---|---:|
| Valid chronological transitions | 14 |
| Median price change | −18.61% |
| Mean price change | −18.70% |
| Smallest price change | −20.71% |
| Largest price change | −14.34% |

This is too consistent to ignore, but we shouldn't automatically treat the difference as an actual loss on migration. The last Pump.fun observation and first PumpSwap observation may reflect different pool states or pricing behavior. We need to inspect their underlying trade amounts and pool fields before stitching the two series together.

## Step 44 — Inspect the underlying migration records

**Goal:** Compare the last Pump.fun trade and first PumpSwap trade for the 16 selected tokens, including their amounts, prices, and pool state fields.

This cell streams the same archive hour again and keeps only events belonging to those 16 tokens. It does not store the full archive in memory.

Run this as one new cell in Colab.

<CodeBlockx=False)
    )
</CodeBlock>

### What we're looking for

We want to determine whether the price difference is also present in the individual trade-leg prices, and whether the pool-state fields explain the transition.

If the records confirm a genuine difference between the two markets, the simulator will need to model migration as a change of execution venue. If the difference is mostly a pricing convention or state-measurement artifact, we will need a consistent price reference before calculating returns across the transition.

Paste the full output of Step 44. We'll use it to choose the appropriate price-series construction for the trading environment.

---

# you asked

Selected transition mints: 16
Scanning the archive hour again...

=== Transition records with pool-state details ===
Chronologically valid transitions: 14

                                        mint  gap_s  curve_price  curve_leg_price  curve_quote_amount  curve_token_amount  curve_quote_in_pool  curve_tokens_in_pool   pool_price  pool_leg_price  pool_quote_amount  pool_token_amount  pool_quote_in_pool  pool_tokens_in_pool  price_change_pct
4mqskjYrrcfvZ4VeveJZtUeJjoRqiV5FdDeNChU2pump  0.059 4.109000e-07     1.072000e-07           85.005359        7.931000e+08           115.005359           279900000.0 3.344000e-07    4.207000e-07         161.000000       1.348561e+08           68.393706         2.045233e+08        -18.612407
7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump  0.609 4.109000e-07     4.105000e-07            0.103852        2.529834e+05           115.005360           279900000.0 3.258000e-07    4.118000e-07           0.206708       5.019882e+05           67.405855         2.069000e+08        -20.709356
8Y5AP9NqanQbQHn253HB2ns9ZDWyba3vxoHTdhern886  0.010 4.109000e-07     1.072000e-07           85.005359        7.931000e+08           115.005359           279900000.0 3.344000e-07    4.156000e-07         148.122172       1.314663e+08           68.393530         2.045237e+08        -18.612782
98FPTSbFm3m8w3YMWLK9Ke2Fjt3SdZtNcSCFZcgWpump  0.052 4.109000e-07     1.072000e-07           85.005359        7.931000e+08           115.005359           279900000.0 3.344000e-07    4.207000e-07         161.000000       1.348561e+08           68.393706         2.045233e+08        -18.612407
A3WUfYA5DRCBX8PQTyk9tvaUxrte2bb76qUsev4Rwswx  0.003 4.109000e-07     1.072000e-07           85.005359        7.931000e+08           115.005359           279900000.0 3.344000e-07    4.156000e-07         148.122172       1.314663e+08           68.393530         2.045237e+08        -18.612782
AYXqgh4Ryy1VwQX2hpKxX1yrNXj4JKehw8WAeC8epump  0.064 4.109000e-07     4.085000e-07            0.677702        1.659169e+06           115.005359           279900000.0 3.520000e-07    4.502000e-07           1.000000       2.221213e+06           70.369409         1.999300e+08        -14.337485
BK77PdW4i5ThuoMsStmqYVCpVTSNUzve63iCTjgLpump  0.005 4.109000e-07     4.087000e-07            0.614829        1.504414e+06           115.005359           279900000.0 3.465000e-07    4.440000e-07           1.000000       2.252423e+06           69.754457         2.013374e+08        -15.679666
C2FSFMFRE3E68AQ1yHTNAb2NRMfeFSXkpTKmx4Ehpump  0.857 4.109000e-07     4.024000e-07            2.382189        5.920405e+06           115.005360           279900000.0 3.258000e-07    4.207000e-07           1.000000       2.376720e+06           67.405854         2.069000e+08        -20.709356
ChUdczuMMJRnLPyg9nFrED4oULt6h2TL8UimW3Ub97Qb  0.007 4.109000e-07     1.072000e-07           85.005359        7.931000e+08           115.005359           279900000.0 3.344000e-07    4.156000e-07         148.122172       1.314663e+08           68.393530         2.045237e+08        -18.612782
DoVAVzViX8Bjy3r15nwikSaSbzE6dV4ovd28aWpJpump  0.592 4.109000e-07     4.103000e-07            0.165451        4.032555e+05           115.005361           279900000.0 3.258000e-07    4.164000e-07           0.105000       2.521480e+05           67.405855         2.069000e+08        -20.709356
FvEtxYTGk6UxgKvcHETh3oCVDQbQFgLdupf8rzcNpump  3.437 4.109000e-07     3.974000e-07            3.783693        9.522028e+06           115.005361           279900000.0 3.258000e-07    4.099000e-07           0.179279       4.373577e+05           67.405855         2.069000e+08        -20.709356
HJ2QzKWG5WxxPgJNu6dABfchZDfJLgk3BnhAH2NZpump  0.014 4.109000e-07     1.072000e-07           85.005359        7.931000e+08           115.005359           279900000.0 3.344000e-07    4.207000e-07         149.000000       1.311774e+08           68.393706         2.045233e+08        -18.612407
HTYuNpG6eWjQqt5fznEgU1hFVmaV8DYrMJKtvhuas5xN  0.003 4.109000e-07     1.072000e-07           85.005359        7.931000e+08           115.005359           279900000.0 3.344000e-07    4.156000e-07         148.122172       1.314663e+08           68.393530         2.045237e+08        -18.612782
 nMnddwSU83WJ5NnVzocrBdnmGJQBHnLYyCscKEWpump  0.028 4.109000e-07     1.072000e-07           85.005359        7.931000e+08           115.005359           279900000.0 3.344000e-07    4.156000e-07         148.122172       1.314663e+08           68.393530         2.045237e+08        -18.612782

=== Recorded-price versus trade-leg-price comparison ===
                                        mint  curve_price_vs_leg_pct  pool_price_vs_leg_pct  price_change_pct
4mqskjYrrcfvZ4VeveJZtUeJjoRqiV5FdDeNChU2pump                283.3512               -20.5212          -18.6124
7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump                  0.0904               -20.8824          -20.7094
8Y5AP9NqanQbQHn253HB2ns9ZDWyba3vxoHTdhern886                283.3512               -19.5279          -18.6128
98FPTSbFm3m8w3YMWLK9Ke2Fjt3SdZtNcSCFZcgWpump                283.3512               -20.5212          -18.6124
A3WUfYA5DRCBX8PQTyk9tvaUxrte2bb76qUsev4Rwswx                283.3512               -19.5279          -18.6128
AYXqgh4Ryy1VwQX2hpKxX1yrNXj4JKehw8WAeC8epump                  0.5928               -21.8199          -14.3375
BK77PdW4i5ThuoMsStmqYVCpVTSNUzve63iCTjgLpump                  0.5375               -21.9636          -15.6797
C2FSFMFRE3E68AQ1yHTNAb2NRMfeFSXkpTKmx4Ehpump                  2.1152               -22.5689          -20.7094
ChUdczuMMJRnLPyg9nFrED4oULt6h2TL8UimW3Ub97Qb                283.3512               -19.5279          -18.6128
DoVAVzViX8Bjy3r15nwikSaSbzE6dV4ovd28aWpJpump                  0.1441               -21.7646          -20.7094
FvEtxYTGk6UxgKvcHETh3oCVDQbQFgLdupf8rzcNpump                  3.4019               -20.5223          -20.7094
HJ2QzKWG5WxxPgJNu6dABfchZDfJLgk3BnhAH2NZpump                283.3512               -20.5212          -18.6124
HTYuNpG6eWjQqt5fznEgU1hFVmaV8DYrMJKtvhuas5xN                283.3512               -19.5279          -18.6128
 nMnddwSU83WJ5NnVzocrBdnmGJQBHnLYyCscKEWpump                283.3512               -19.5279          -18.6128

---

# chatgpt response

Step 44 confirms that the roughly **−18.6% transition is real in the recorded reserve-implied prices**, but it does not yet establish an executable 18.6% loss.

For example, the first transition shows:

- Pump.fun: `115.005359 SOL / 279,900,000 tokens` → about `4.109 × 10⁻⁷ SOL/token`.
- PumpSwap: `68.393706 SOL / 204,523,300 tokens` → about `3.344 × 10⁻⁷ SOL/token`.

Those ratios reproduce the recorded top-level prices. However, the `breakdown_price` field can differ substantially, and our earlier cell retained only the first breakdown item's price. We need to inspect the original event structure before deciding which price to use for backtesting.

## Step 45 — Validate the raw event prices

Run this cell next. It checks how closely the top-level price matches the pool-reserve ratio, then retrieves four original endpoint records so we can examine their `breakdown` fields.

<Co default=str)[:4500])
</CodeBlock>

Paste the output. The key questions are whether the reserve states are repeated across tokens and what the raw `breakdown` entries actually represent. Those determine whether we should use the top-level price, trade-level prices, or exclude these transition records from the initial backtest.

---

# you asked

=== Price / reserve consistency ===
Valid endpoints: 32
                count  median  min  max
role                                   
first_PUMPSWAP     16     0.0  0.0  0.0
last_PUMPFUN       16     0.0  0.0  0.0

=== Repeated reserve states ===
PUMPFUN | endpoints: 16 | distinct reserve/price tuples: 7
PUMPSWAP | endpoints: 16 | distinct reserve/price tuples: 8

=== Selected endpoint summary ===
                                        mint           role  archive_seq                                                                                signature        price  breakdown_price  quoteAmount  tokenAmount  quoteInPool  tokensInPool  reserve_price
4mqskjYrrcfvZ4VeveJZtUeJjoRqiV5FdDeNChU2pump   last_PUMPFUN      1064165  dYBxVTycerGV7x7ppi8UdgMksqXCb6RJmTFnr9MBspWeyVigHcZj7XPU2binbxQwHpLDCXgR4Mq5Ve7y6P2FXaP 4.108800e-07     1.071810e-07    85.005359 7.931000e+08   115.005359  2.799000e+08   4.108800e-07
4mqskjYrrcfvZ4VeveJZtUeJjoRqiV5FdDeNChU2pump first_PUMPSWAP      1064218 2Q5MNdsR6DmB9U5bGtg3AT5KakKCpoDwHNJx6qia7whwkAtVBUmBNfXdNj9xHrmnCQCWPNTiocimY1zZfFdrhDJu 3.344050e-07     4.207480e-07   161.000000 1.348561e+08    68.393706  2.045233e+08   3.344050e-07
7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump   last_PUMPFUN      1003516 3R73W6zVu46XK2DkUS3BS2VfTe1bZLknnjM1z9JvByYUtsrzVuQ5vNoHbTxDwoNunuPPTGs5mkNXEtRhCudXBXFm 4.108800e-07     4.105090e-07     0.103852 2.529834e+05   115.005360  2.799000e+08   4.108800e-07
7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump first_PUMPSWAP      1003850 3QFMPjreMaKNpD2y5YRmQyocXta8UrKQbxugjXmVTYUXQDYT3G5BLyvzdsenqKdbNeEa2xVCnkTDWbuACwh7V5Mw 3.257900e-07     4.117790e-07     0.206708 5.019882e+05    67.405855  2.069000e+08   3.257900e-07

Fetching original event records for the selected endpoints...
Original records recovered: 4 / 4

--- PUMPFUN | 7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump ---
{
  "signature": "3R73W6zVu46XK2DkUS3BS2VfTe1bZLknnjM1z9JvByYUtsrzVuQ5vNoHbTxDwoNunuPPTGs5mkNXEtRhCudXBXFm",
  "block": 453261689,
  "timestamp": 1791118275,
  "localTimestamp": 1791118276504,
  "action": "buy",
  "protocol": "PUMPFUN",
  "mint": "7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump",
  "pool": "5zu5HvHAewWzBzcfX2uBM1rWFruzgGg4B7a55enCoe85",
  "price": 4.1088017232940336e-07,
  "quoteAmount": 0.103852013,
  "tokenAmount": 252983.43548,
  "quoteMint": "So11111111111111111111111111111111111111112",
  "quoteInPool": 115.005360235,
  "tokensInPool": 279900000.0,
  "tradersInvolved": [
    "1UTzmbt1c3NuQB6i7ZRf5PKxqyTFo1mpgb1P6xQ5JgU"
  ],
  "txSigner": "1UTzmbt1c3NuQB6i7ZRf5PKxqyTFo1mpgb1P6xQ5JgU",
  "breakdown": [
    {
      "action": "buy",
      "price": 4.1050914184541617e-07,
      "quoteAmount": 0.103852013,
      "tokenAmount": 252983.43548,
      "trader": "1UTzmbt1c3NuQB6i7ZRf5PKxqyTFo1mpgb1P6xQ5JgU"
    }
  ]
}

--- PUMPSWAP | 7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump ---
{
  "signature": "3QFMPjreMaKNpD2y5YRmQyocXta8UrKQbxugjXmVTYUXQDYT3G5BLyvzdsenqKdbNeEa2xVCnkTDWbuACwh7V5Mw",
  "block": 453261693,
  "timestamp": 1791118276,
  "localTimestamp": 1791118277113,
  "action": "buy",
  "protocol": "PUMPSWAP",
  "mint": "7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump",
  "pool": "6rVPaxwytzE26is8hJWzkp671RFkH6EukNTgo3j7u5na",
  "price": 3.257895345674239e-07,
  "quoteAmount": 0.206708192,
  "tokenAmount": 501988.222223,
  "quoteMint": "So11111111111111111111111111111111111111112",
  "quoteInPool": 67.405854702,
  "tokensInPool": 206900000.0,
  "tradersInvolved": [
    "AAKs8FPSaDD5U3TN1h2gZBTBx3B68tqgU1NeYZZRPU8N"
  ],
  "txSigner": "AAKs8FPSaDD5U3TN1h2gZBTBx3B68tqgU1NeYZZRPU8N",
  "breakdown": [
    {
      "action": "buy",
      "price": 4.1177896781047046e-07,
      "quoteAmount": 0.206708192,
      "tokenAmount": 501988.222223,
      "trader": "AAKs8FPSaDD5U3TN1h2gZBTBx3B68tqgU1NeYZZRPU8N"
    }
  ]
}

--- PUMPFUN | 4mqskjYrrcfvZ4VeveJZtUeJjoRqiV5FdDeNChU2pump ---
{
  "signature": "dYBxVTycerGV7x7ppi8UdgMksqXCb6RJmTFnr9MBspWeyVigHcZj7XPU2binbxQwHpLDCXgR4Mq5Ve7y6P2FXaP",
  "block": 453262360,
  "timestamp": 1791118454,
  "localTimestamp": 1791118600203,
  "action": "buy",
  "protocol": "PUMPFUN",
  "mint": "4mqskjYrrcfvZ4VeveJZtUeJjoRqiV5FdDeNChU2pump",
  "pool": "6zTVZSZvU6YvgY5QRZtEgmUTqYvhN2PMjSeVnLyvbvHH",
  "price": 4.108801681207574e-07,
  "quoteAmount": 85.005359057,
  "tokenAmount": 793100000.0,
  "quoteMint": "So11111111111111111111111111111111111111112",
  "quoteInPool": 115.005359057,
  "tokensInPool": 279900000.0,
  "tradersInvolved": [
    "C1EvVafVPvv5o4SXfvZ1Tnp2AYfJH5W765kbC5MbE2Lc"
  ],
  "txSigner": "C1EvVafVPvv5o4SXfvZ1Tnp2AYfJH5W765kbC5MbE2Lc",
  "breakdown": [
    {
      "action": "buy",
      "price": 1.0718113612028748e-07,
      "quoteAmount": 85.005359057,
      "tokenAmount": 793100000.0,
      "trader": "C1EvVafVPvv5o4SXfvZ1Tnp2AYfJH5W765kbC5MbE2Lc"
    }
  ]
}

--- PUMPSWAP | 4mqskjYrrcfvZ4VeveJZtUeJjoRqiV5FdDeNChU2pump ---
{
  "signature": "2Q5MNdsR6DmB9U5bGtg3AT5KakKCpoDwHNJx6qia7whwkAtVBUmBNfXdNj9xHrmnCQCWPNTiocimY1zZfFdrhDJu",
  "block": 453262360,
  "timestamp": 1791118454,
  "localTimestamp": 1791118600262,
  "action": "buy",
  "protocol": "PUMPSWAP",
  "mint": "4mqskjYrrcfvZ4VeveJZtUeJjoRqiV5FdDeNChU2pump",
  "pool": "61dwue7tnQkNP7VuVRz9HYaXGTLf51DQMNgj3sd5qGMt",
  "price": 3.3440548027583814e-07,
  "quoteAmount": 161.0,
  "tokenAmount": 134856099.430345,
  "quoteMint": "So11111111111111111111111111111111111111112",
  "quoteInPool": 68.393705619,
  "tokensInPool": 204523279.829579,
  "tradersInvolved": [
    "9qZvANPkPE6NHoj5W5BzJ4gb4byaVqvg1V4JCJBfiK2m",
    "BTmCme13XXrD3VLxXFChL9VnmicJ5PjkVUpAsjrooEYh"
  ],
  "txSigner": "BTmCme13XXrD3VLxXFChL9VnmicJ5PjkVUpAsjrooEYh",
  "breakdown": [
    {
      "action": "buy",
      "price": 4.207478913358425e-07,
      "quoteAmount": 1.0,
      "tokenAmount": 2376720.170421,
      "trader": "BTmCme13XXrD3VLxXFChL9VnmicJ5PjkVUpAsjrooEYh"
    },
    {
      "action": "buy",
      "price": 1.2077351274878837e-06,
      "quoteAmount": 160.0,
      "tokenAmount": 132479379.259924,
      "trader": "9qZvANPkPE6NHoj5W5BzJ4gb4byaVqvg1V4JCJBfiK2m"
    }
  ]
}

---

# chatgpt response

Step 45 changes our interpretation. **The apparent −18.6% migration drop is not evidence of an 18.6% trading loss.**

The reserve-implied prices match the archive's top-level `price` exactly, but that field can differ substantially from the price implied by the actual trade amounts.

For the `7ySd...` token, for example:

| Measure | Pump.fun | PumpSwap |
|---|---:|---:|
| Reserve-implied price | $4.109 \times 10^{-7}$ | $3.258 \times 10^{-7}$ |
| Trade amount ÷ token amount | $4.105 \times 10^{-7}$ | $4.118 \times 10^{-7}$ |

The reserve prices suggest a 20.7% decline, while the transaction-level average prices suggest a change of roughly **+0.31%**. That's a very different result.

The `breakdown` records also matter: an event can aggregate multiple trades at different prices. So we should compare amount-implied average prices first, and avoid treating either a reserve ratio or a single breakdown entry as a guaranteed execution price.

## Step 46 — Recalculate the transition using trade amounts

This uses the existing `transition_detail_df`; no archive download is needed. It compares the top-level spot-price change with the average price implied by each endpoint event's `quoteAmount / tokenAmount`.

<CodeBlock language="pyth</CodeBlock>

Paste the output. This will tell us how much of the apparent transition drop survives when we use the event amounts. These averages are still diagnostic—not guaranteed fill prices—because the archive can aggregate multiple swaps into one event.

---

# you asked

=== Transition price comparison ===
Valid transitions: 14

Reserve-implied spot change:
count    14.000
mean    -18.697
std       1.847
min     -20.709
10%     -20.709
25%     -20.185
50%     -18.613
75%     -18.612
90%     -16.559
max     -14.337
Positive: 0
Negative: 14
Approximately unchanged (within +/-1%): 0

Amount-implied average trade-price change:
count      14.000
mean      555.137
std       495.108
min         0.309
10%         1.994
25%         5.584
50%       951.204
75%       951.204
90%       997.642
max      1013.876
Positive: 14
Negative: 0
Approximately unchanged (within +/-1%): 1

=== Per-token comparison ===
                                        mint gap_s curve_quote_amount curve_token_amount pool_quote_amount pool_token_amount spot_change_pct avg_trade_change_pct
7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump 0.609           0.103852         252983.435          0.206708        501988.222         -20.71%               +0.31%
DoVAVzViX8Bjy3r15nwikSaSbzE6dV4ovd28aWpJpump 0.592           0.165451         403255.521          0.105000        252147.972         -20.71%               +1.49%
FvEtxYTGk6UxgKvcHETh3oCVDQbQFgLdupf8rzcNpump 3.437           3.783693        9522027.710          0.179279        437357.737         -20.71%               +3.16%
C2FSFMFRE3E68AQ1yHTNAb2NRMfeFSXkpTKmx4Ehpump 0.857           2.382189        5920404.957          1.000000       2376720.157         -20.71%               +4.57%
BK77PdW4i5ThuoMsStmqYVCpVTSNUzve63iCTjgLpump 0.005           0.614829        1504414.377          1.000000       2252423.010         -15.68%               +8.63%
AYXqgh4Ryy1VwQX2hpKxX1yrNXj4JKehw8WAeC8epump 0.064           0.677702        1659169.224          1.000000       2221213.093         -14.34%              +10.22%
8Y5AP9NqanQbQHn253HB2ns9ZDWyba3vxoHTdhern886 0.010          85.005359      793100000.000        148.122172     131466342.645         -18.61%             +951.20%
A3WUfYA5DRCBX8PQTyk9tvaUxrte2bb76qUsev4Rwswx 0.003          85.005359      793100000.000        148.122172     131466342.645         -18.61%             +951.20%
 nMnddwSU83WJ5NnVzocrBdnmGJQBHnLYyCscKEWpump 0.028          85.005359      793100000.000        148.122172     131466342.645         -18.61%             +951.20%
HTYuNpG6eWjQqt5fznEgU1hFVmaV8DYrMJKtvhuas5xN 0.003          85.005359      793100000.000        148.122172     131466342.645         -18.61%             +951.20%
ChUdczuMMJRnLPyg9nFrED4oULt6h2TL8UimW3Ub97Qb 0.007          85.005359      793100000.000        148.122172     131466342.645         -18.61%             +951.20%
HJ2QzKWG5WxxPgJNu6dABfchZDfJLgk3BnhAH2NZpump 0.014          85.005359      793100000.000        149.000000     131177417.703         -18.61%             +959.76%
4mqskjYrrcfvZ4VeveJZtUeJjoRqiV5FdDeNChU2pump 0.059          85.005359      793100000.000        161.000000     134856099.430         -18.61%            +1013.88%
98FPTSbFm3m8w3YMWLK9Ke2Fjt3SdZtNcSCFZcgWpump 0.052          85.005359      793100000.000        161.000000     134856099.430         -18.61%            +1013.88%

---

# chatgpt response

The Step 46 result exposes another data-quality problem: the amount-implied transition change has a median of **+951.2%**, while the reserve-implied change is −18.6%. That is not a credible basis for a migration-return estimate.

My previous suggestion to prefer `quoteAmount / tokenAmount` was too broad. It works as an arithmetic average of the recorded amounts, but that average may combine multiple trades and is not necessarily a valid market price. For now, **neither transition series should be used to claim a strategy edge**.

The next check is whether the raw breakdown entries reconcile with each event's top-level amounts and prices across all 28 transition endpoints—not just the four we inspected.

## Step 47 — Audit all transition-event breakdowns

<Cn"]
        },
    )
)
</CodeBlock>

Paste the complete output. The key distinction is whether each event's breakdown amounts reconcile with its top-level totals, and whether top-level prices align with the reserve snapshot or the trade amounts. That will tell us which archive fields can safely support the next backtest step.

---

# you asked

Target endpoint records: 32
Scanning the archive hour...
Recovered: 32 / 32

=== Reconciliation by protocol ===

PUMPFUN: 16 events
Events with multiple breakdown legs: 0
Quote sums matching top-level within 1%: 16 / 16
Token sums matching top-level within 1%: 16 / 16
Median top-price vs reserve-price difference: 0.0 %
Median top-price vs amount-price difference: 283.3512 %

PUMPSWAP: 16 events
Events with multiple breakdown legs: 10
Quote sums matching top-level within 1%: 16 / 16
Token sums matching top-level within 1%: 16 / 16
Median top-price vs reserve-price difference: 0.0 %
Median top-price vs amount-price difference: -70.3199 %

=== All transition endpoints ===
                                        mint           role protocol action breakdown_count top_price reserve_price amount_price breakdown_min_price breakdown_max_price quote_sum_diff_pct token_sum_diff_pct top_vs_reserve_pct top_vs_amount_price_pct
4mqskjYrrcfvZ4VeveJZtUeJjoRqiV5FdDeNChU2pump first_PUMPSWAP PUMPSWAP    buy               2  3.34e-07      3.34e-07     1.19e-06            4.21e-07            1.21e-06                  0                  0                  0                     -72
4mqskjYrrcfvZ4VeveJZtUeJjoRqiV5FdDeNChU2pump   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     1.07e-07            1.07e-07            1.07e-07                  0                  0                  0                     283
7QJ3BnoFkuxBFtqS3MsAN9EeMeoytob7H7KAFP38pump first_PUMPSWAP PUMPSWAP    buy               2  3.34e-07      3.34e-07     1.09e-06            4.21e-07             1.1e-06                  0                  0                  0                   -69.2
7QJ3BnoFkuxBFtqS3MsAN9EeMeoytob7H7KAFP38pump   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     1.07e-07            1.07e-07            1.07e-07                  0                  0                  0                     283
7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump first_PUMPSWAP PUMPSWAP    buy               1  3.26e-07      3.26e-07     4.12e-07            4.12e-07            4.12e-07                  0                  0                  0                   -20.9
7ySdpkBAyHhFt7yUXEEgAacsKbRjqbyMCjqdkGBFpump   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     4.11e-07            4.11e-07            4.11e-07                  0                  0                  0                  0.0904
8Y5AP9NqanQbQHn253HB2ns9ZDWyba3vxoHTdhern886 first_PUMPSWAP PUMPSWAP    buy               2  3.34e-07      3.34e-07     1.13e-06            4.16e-07            1.14e-06                  0                  0                  0                   -70.3
8Y5AP9NqanQbQHn253HB2ns9ZDWyba3vxoHTdhern886   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     1.07e-07            1.07e-07            1.07e-07                  0                  0                  0                     283
98FPTSbFm3m8w3YMWLK9Ke2Fjt3SdZtNcSCFZcgWpump first_PUMPSWAP PUMPSWAP    buy               2  3.34e-07      3.34e-07     1.19e-06            4.21e-07            1.21e-06                  0                  0                  0                     -72
98FPTSbFm3m8w3YMWLK9Ke2Fjt3SdZtNcSCFZcgWpump   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     1.07e-07            1.07e-07            1.07e-07                  0                  0                  0                     283
A3WUfYA5DRCBX8PQTyk9tvaUxrte2bb76qUsev4Rwswx first_PUMPSWAP PUMPSWAP    buy               2  3.34e-07      3.34e-07     1.13e-06            4.16e-07            1.14e-06                  0                  0                  0                   -70.3
A3WUfYA5DRCBX8PQTyk9tvaUxrte2bb76qUsev4Rwswx   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     1.07e-07            1.07e-07            1.07e-07                  0                  0                  0                     283
AYXqgh4Ryy1VwQX2hpKxX1yrNXj4JKehw8WAeC8epump first_PUMPSWAP PUMPSWAP    buy               1  3.52e-07      3.52e-07      4.5e-07             4.5e-07             4.5e-07                  0                  0                  0                   -21.8
AYXqgh4Ryy1VwQX2hpKxX1yrNXj4JKehw8WAeC8epump   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     4.08e-07            4.08e-07            4.08e-07                  0                  0                  0                   0.593
BBirK74KfPezj25Z9tGcb5gAD3tKgmtQqcBzx3LBpump first_PUMPSWAP PUMPSWAP    buy               2  3.34e-07      3.34e-07     1.14e-06            4.21e-07            1.15e-06                  0                  0                  0                   -70.6
BBirK74KfPezj25Z9tGcb5gAD3tKgmtQqcBzx3LBpump   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     1.07e-07            1.07e-07            1.07e-07                  0                  0                  0                     283
BK77PdW4i5ThuoMsStmqYVCpVTSNUzve63iCTjgLpump first_PUMPSWAP PUMPSWAP    buy               1  3.46e-07      3.46e-07     4.44e-07            4.44e-07            4.44e-07                  0                  0                  0                     -22
BK77PdW4i5ThuoMsStmqYVCpVTSNUzve63iCTjgLpump   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     4.09e-07            4.09e-07            4.09e-07                  0                  0                  0                   0.537
C2FSFMFRE3E68AQ1yHTNAb2NRMfeFSXkpTKmx4Ehpump first_PUMPSWAP PUMPSWAP    buy               1  3.26e-07      3.26e-07     4.21e-07            4.21e-07            4.21e-07                  0                  0                  0                   -22.6
C2FSFMFRE3E68AQ1yHTNAb2NRMfeFSXkpTKmx4Ehpump   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     4.02e-07            4.02e-07            4.02e-07                  0                  0                  0                    2.12
ChUdczuMMJRnLPyg9nFrED4oULt6h2TL8UimW3Ub97Qb first_PUMPSWAP PUMPSWAP    buy               2  3.34e-07      3.34e-07     1.13e-06            4.16e-07            1.14e-06                  0                  0                  0                   -70.3
ChUdczuMMJRnLPyg9nFrED4oULt6h2TL8UimW3Ub97Qb   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     1.07e-07            1.07e-07            1.07e-07                  0                  0                  0                     283
DoVAVzViX8Bjy3r15nwikSaSbzE6dV4ovd28aWpJpump first_PUMPSWAP PUMPSWAP    buy               1  3.26e-07      3.26e-07     4.16e-07            4.16e-07            4.16e-07                  0                  0                  0                   -21.8
DoVAVzViX8Bjy3r15nwikSaSbzE6dV4ovd28aWpJpump   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07      4.1e-07             4.1e-07             4.1e-07                  0                  0                  0                   0.144
FvEtxYTGk6UxgKvcHETh3oCVDQbQFgLdupf8rzcNpump first_PUMPSWAP PUMPSWAP   sell               1  3.26e-07      3.26e-07      4.1e-07             4.1e-07             4.1e-07                  0                  0                  0                   -20.5
FvEtxYTGk6UxgKvcHETh3oCVDQbQFgLdupf8rzcNpump   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     3.97e-07            3.97e-07            3.97e-07                  0                  0                  0                     3.4
HJ2QzKWG5WxxPgJNu6dABfchZDfJLgk3BnhAH2NZpump first_PUMPSWAP PUMPSWAP    buy               2  3.34e-07      3.34e-07     1.14e-06            4.21e-07            1.15e-06                  0                  0                  0                   -70.6
HJ2QzKWG5WxxPgJNu6dABfchZDfJLgk3BnhAH2NZpump   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     1.07e-07            1.07e-07            1.07e-07                  0                  0                  0                     283
HTYuNpG6eWjQqt5fznEgU1hFVmaV8DYrMJKtvhuas5xN first_PUMPSWAP PUMPSWAP    buy               2  3.34e-07      3.34e-07     1.13e-06            4.16e-07            1.14e-06                  0                  0                  0                   -70.3
HTYuNpG6eWjQqt5fznEgU1hFVmaV8DYrMJKtvhuas5xN   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     1.07e-07            1.07e-07            1.07e-07                  0                  0                  0                     283
 nMnddwSU83WJ5NnVzocrBdnmGJQBHnLYyCscKEWpump first_PUMPSWAP PUMPSWAP    buy               2  3.34e-07      3.34e-07     1.13e-06            4.16e-07            1.14e-06                  0                  0                  0                   -70.3
 nMnddwSU83WJ5NnVzocrBdnmGJQBHnLYyCscKEWpump   last_PUMPFUN  PUMPFUN    buy               1  4.11e-07      4.11e-07     1.07e-07            1.07e-07            1.07e-07                  0                  0                  0                     283

---

# chatgpt response

## Step 48 — Check how prices move around each trade

This next cell checks whether the recorded pool price tends to move in the direction of the **current trade** or the **previous trade**. It does this separately for Pump.fun and PumpSwap, using only consecutive observations from the same token and pool.

<d fill is realistic."
)
</CodeBlock>

Paste the output. We can then decide whether the recorded price is a defensible *mark price* for within-pool forward-return analysis. Until that is established, cross-pool migration returns should remain excluded from strategy-performance claims.

---

# you asked

=== Price movement / trade direction ===
All eligible consecutive observations: 53040

--- PUMPFUN ---
Observations: 7161
Price-change median: 0.0661 %
Price rises: 60.17 %
Price falls: 39.83 %
Move direction matches CURRENT trade: 95.68 %
Move direction matches PREVIOUS trade: 59.77 % | observations: 7161

By current trade action:
        count  median    mean
action                       
buy      4346  0.2918  1.5204
sell     2815 -0.4035 -1.1787

--- PUMPSWAP ---
Observations: 45879
Price-change median: -0.0109 %
Price rises: 49.79 %
Price falls: 50.21 %
Move direction matches CURRENT trade: 53.47 %
Move direction matches PREVIOUS trade: 89.7 % | observations: 45879

By current trade action:
        count  median    mean
action                       
buy     21621  0.0243  0.1643
sell    24258 -0.0330  0.1148

Interpretation caution:
Directional alignment is diagnostic only; it does not establish that a price was executable or that a simulated fill is realistic.

---

# chatgpt response

Step 48 gives us an important clue about the archive's price semantics:

| Protocol | Move matches current trade direction | Move matches previous trade direction |
|---|---:|---:|
| Pump.fun | 95.68% | 59.77% |
| PumpSwap | 53.47% | 89.70% |

Within this selected sample, Pump.fun's recorded price behaves like a post-trade mark, while PumpSwap's price changes align much more strongly with the *previous* trade. That suggests the two protocols may record price at different points in the event lifecycle.

This is not yet proof of a one-trade lag: ordering and observation timestamps could contribute to the result. The next check tests whether this pattern survives alternative event orderings.

## Step 49 — Test whether event ordering explains the pattern

Run this cell. It reuses `detail` and compares three orderings: observed timestamp, block order, and original archive order.

<CodeBlock lansample."
)
</CodeBlock>

Paste the output. If the pattern changes substantially with ordering, timestamp sequencing is part of the problem. If it remains stable, the stronger next step is to verify price-field semantics against another hour and more pools before using these prices in a backtest.

---

# you asked

=== Ordering sensitivity ===
     ordering protocol  adjacent_pairs  negative_time_gaps_all_protocols  pairs_with_0_to_2s_gap  pairs_after_move_filter move_matches_current_trade_pct move_matches_previous_trade_pct
observed_time  PUMPFUN            7816                                 0                    7550                     7161                         95.68%                          59.77%
observed_time PUMPSWAP          112791                                 0                  112383                    45879                         53.47%                          89.70%
  block_order  PUMPFUN            7816                               753                    7543                     7154                         95.72%                          59.80%
  block_order PUMPSWAP          112791                               753                  111637                    45472                         53.65%                          90.17%
archive_order  PUMPFUN            7816                                 4                    7550                     7161                         95.68%                          59.77%
archive_order PUMPSWAP          112791                                 4                  112379                    45878                         53.45%                          89.69%

Reminder: this is the selected 16-token transition sample, not a representative market-wide sample.

---

# chatgpt response

Step 49 shows that the result is largely insensitive to event ordering: the directional alignment stays almost unchanged across all three orderings. That makes a simple sorting artifact less likely, although the sample is still restricted to one hour and selected tokens.

## Step 50 — Validate the price behavior in another hour

This cell selects the next available archive hour and analyzes **all eligible Pump.fun and PumpSwap SOL trades**, rather than just the 16 selected tokens. It keeps each mint and pool separate and applies the same short-gap price-movement test.

r execution slippage."
)
</CodeBlock>

Paste the output. The most useful comparison is whether PumpSwap again aligns more with the previous trade while Pump.fun aligns more with the current trade, now across a broader set of pools.