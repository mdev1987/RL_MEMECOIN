"""Test trained RL strategy against PumpAPI replay price paths."""
import zstandard as zstd, json, io, collections
import numpy as np
from bot import BotConfig, PumpSwapEnv, LinearPolicy

PATH = "/mnt/HDD/PumpAPI_Replay_Zst/2026-10-04/12.jsonl.zst"
MAX_MINTS = 60
MIN_EVENTS = 40

dctx = zstd.ZstdDecompressor()
by_mint = collections.defaultdict(list)
n_lines = 0
with open(PATH, 'rb') as f:
    r = dctx.stream_reader(f)
    t = io.TextIOWrapper(r, encoding='utf-8')
    for line in t:
        if not line.strip():
            continue
        n_lines += 1
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get('action') not in ('buy', 'sell'):
            continue
        if e.get('quoteMint') != 'So11111111111111111111111111111111111111112':
            continue
        p = e.get('price')
        if not p or p <= 0:
            continue
        by_mint[e['mint']].append((e.get('timestamp', 0), float(p), e.get('pool'), e.get('action')))
        if n_lines >= 600000:
            break

print(f"scanned={n_lines} mints={len(by_mint)}")
paths = []
for mint, evs in by_mint.items():
    evs.sort()
    prices = [p for _, p, _, _ in evs]
    if len(prices) >= MIN_EVENTS:
        paths.append((mint, prices[:200], evs))
print(f"kept paths>={MIN_EVENTS}: {len(paths)}")
paths = paths[:MAX_MINTS]

cfg = BotConfig(max_steps=80, seed=7)
pol = LinearPolicy(seed=7)
try:
    pol.load('data/rl_bot.npz')
    print("loaded trained policy")
except Exception as ex:
    print("no checkpoint, using init:", ex)


def run_path(prices, policy_fn):
    env = PumpSwapEnv(cfg)
    obs = env.reset(price_path=np.array(prices[:cfg.max_steps]) / prices[0])
    # normalize: env expects relative path; reset with given path directly
    done = False
    while not done:
        a = policy_fn(obs)
        obs, _, done, _ = env.step(a)
    return env.equity


def pol_argmax(o):
    return int(np.argmax(pol.probs(o)))


rets_rl, rets_hold, rets_bh = [], [], []
for mint, prices, _ in paths:
    # RL
    r_rl = run_path(prices, pol_argmax) - 1.0
    rets_rl.append(r_rl)
    # hold (do nothing)
    env = PumpSwapEnv(cfg)
    obs = env.reset(price_path=np.array(prices[:cfg.max_steps]) / prices[0])
    done = False
    while not done:
        obs, _, done, _ = env.step(0)
    rets_hold.append(env.equity - 1.0)
    # buy-hold: buy step0 then hold
    env = PumpSwapEnv(cfg)
    obs = env.reset(price_path=np.array(prices[:cfg.max_steps]) / prices[0])
    done = False
    first = True
    while not done:
        a = 1 if first else 0
        first = False
        obs, _, done, _ = env.step(a)
    rets_bh.append(env.equity - 1.0)

import statistics
def summ(v):
    v = np.array(v)
    return f"mean {v.mean():+.3%} med {np.median(v):+.3%} win {(v>0).mean():.1%} max {v.max():+.2%} min {v.min():+.2%}"
print(f"RL      : {summ(rets_rl)}")
print(f"HOLD    : {summ(rets_hold)}")
print(f"BUY-HOLD: {summ(rets_bh)}")
# per-mint table (first 15)
for i, (mint, _, _) in enumerate(paths[:15]):
    print(f"{mint[:10]} RL {rets_rl[i]:+.2%} BH {rets_bh[i]:+.2%}")
