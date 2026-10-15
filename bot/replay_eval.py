"""Replay evaluation with train/holdout split. No lookahead, deterministic."""
from __future__ import annotations
import zstandard as zstd, json, io, collections, hashlib
import numpy as np
from .strategy import run_selective


def is_pump_pool(e) -> bool:
    """Classic pump universe predicate, schema-tolerant.

    Old schema (local 11/12/13*.zst): pool is the literal name
    'pump-amm' or 'pump'. New schema (shrine 10/12+): pool is the pool
    address and the venue arrives as protocol == 'PUMPSWAP'.
    Either signal admits; anything else (meteora/raydium/orca/...) is out.
    """
    if e.get('pool') in ('pump-amm', 'pump'):
        return True
    return e.get('protocol') == 'PUMPSWAP'


def load_paths(path, max_lines=600000, min_events=40, max_len=200):
    """Slot-aggregated per (mint,pool): last price per block, block-ordered.

    Notebook audit (cells 146-152): 71-83% transitions share a slot and up to
    70 trades share one pool-slot, so intra-slot archive order is unreliable.
    We aggregate to one observation per (mint,pool,block) to avoid sequencing noise.
    """
    dctx = zstd.ZstdDecompressor()
    by_pool = collections.defaultdict(dict)  # (mint,pool) -> {block: (ts,price,action,liq)}
    n = 0
    with open(path, 'rb') as f:
        r = dctx.stream_reader(f)
        t = io.TextIOWrapper(r, encoding='utf-8')
        for line in t:
            if not line.strip():
                continue
            n += 1
            if n > max_lines:
                break
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
            # reliability: classic pump universe only (schema-tolerant predicate)
            if not is_pump_pool(e):
                continue
            try:
                block = int(e.get('block', 0) or 0)
            except Exception:
                continue
            key = (e['mint'], e.get('poolId') or e.get('pool'))
            slot_map = by_pool[key]
            prev = slot_map.get(block)
            # last-write-wins within a slot (no intra-slot sequencing assumed)
            if prev is None or float(e.get('timestamp', 0)) >= prev[0]:
                slot_map[block] = (float(e.get('timestamp', 0)), float(p), e.get('action'),
                                   float(e.get('quoteInPool') or 0))
    paths = []
    for (mint, pool), slot_map in by_pool.items():
        evs = sorted(slot_map.items())  # block-ordered
        if len(evs) < min_events:
            continue
        evs = evs[:max_len]
        prices = [v[1] for _, v in evs]
        acts = [v[2] for _, v in evs]
        liq_series = [v[3] for _, v in evs]
        liq = max(liq_series, default=0.0)
        paths.append({"mint": mint, "pool": pool, "prices": prices, "actions": acts, "liq": liq,
                      "liq_series": liq_series, "liq_min": min(liq_series, default=0.0),
                      "blocks": [b for b, _ in evs]})
    return paths, n


def split_paths(paths, train_frac=0.5, seed="replay"):
    train, test = [], []
    for d in paths:
        h = int(hashlib.md5((seed + d["mint"]).encode()).hexdigest(), 16) % 100
        (train if h < train_frac * 100 else test).append(d)
    return train, test


def evaluate(paths, **kw):
    from .strategy import entry_liq_ok
    rets, reasons = [], collections.Counter()
    # fail_rate needs a per-mint seed for independent deterministic rolls
    fail_rate = kw.pop("fail_rate", 0.0)
    for d in paths:
        # reliability: entry-time depth gate (worst, not max, reserves)
        if not entry_liq_ok(d.get("liq_series") or [d.get("liq", 0.0)] * 11):
            rets.append(0.0)
            reasons["illiquid"] += 1
            continue
        r, why, _ = run_selective(d["prices"], d["actions"],
                                  fail_rate=fail_rate,
                                  fail_seed=d.get("mint", ""),
                                  liq_series=d.get("liq_series"), **kw)
        rets.append(r)
        reasons[why] += 1
    rets = np.array(rets)
    traded = rets != 0
    return {
        "n": len(rets), "traded": int(traded.sum()),
        "trade_rate": float(traded.mean()) if len(rets) else 0.0,
        "mean": float(rets.mean()), "median": float(np.median(rets)) if len(rets) else 0.0,
        "win_rate_traded": float((rets[traded] > 0).mean()) if traded.sum() else 0.0,
        "mean_traded": float(rets[traded].mean()) if traded.sum() else 0.0,
        "max": float(rets.max()) if len(rets) else 0.0,
        "min": float(rets.min()) if len(rets) else 0.0,
        "reasons": dict(reasons),
    }


def buyhold_replay(paths, fee=0.013, entry=10):
    rets = []
    for d in paths:
        p = d["prices"]
        if len(p) < entry + 5 or d["liq"] < 20.0:
            rets.append(0.0)
            continue
        rets.append(p[-1] / p[entry] - 1.0 - fee)
    rets = np.array(rets)
    return {"n": len(rets), "mean": float(rets.mean()), "median": float(np.median(rets)),
            "win": float((rets > 0).mean())}
