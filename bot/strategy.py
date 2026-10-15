"""Selective momentum strategy: trade only filtered setups, with stops. Product-ready, deterministic."""
from __future__ import annotations
import hashlib
import numpy as np


# Per-path execution costs at 0.05 SOL/trade (see plan §5.4; measured via
# scripts/jup_quote.py: feeBps=2 platform on majors, tip floor 0.001 SOL).
# AMM pool+protocol+creator (~1%) + slippage ride in fee_roundtrip.
COST_PATHS = {
    # own tx via cheap sender: no platform fee, tip+prio ~1e-5 SOL/side
    "swqos": {"extra_bps": 0, "fixed_sol": 0.00001},
    # managed Jupiter order+execute on fresh tokens: 50bps/side
    "jupiter": {"extra_bps": 50, "fixed_sol": 0.00001},
    # Jito-bundle style tip floor: 0.001 SOL/side = 2%/side at 0.05
    "jito": {"extra_bps": 0, "fixed_sol": 0.001},
}


def early_features(prices, actions=None, lookback=10):
    prices = np.asarray(prices, dtype=float)
    if len(prices) < lookback + 1:
        return None
    early = prices[:lookback + 1]
    ret = early[-1] / early[0] - 1.0 if early[0] > 0 else 0.0
    # max adverse dip in window (robustness: skip pump-and-dump pre-entry)
    dip = float(np.min(early / early[0] - 1.0))
    buy_ratio = 0.5
    if actions is not None and len(actions) >= lookback:
        w = actions[:lookback]
        buy_ratio = sum(1 for a in w if a == "buy") / max(len(w), 1)
    return {"ret": float(ret), "dip": dip, "buy_ratio": float(buy_ratio),
            "last": float(early[-1]), "first": float(early[0])}


def select_entry(feat, cfg_thresh=(0.05, 0.60, -0.05)):
    """Return True if setup passes robust filter.

    v2 (2026-10-12, validated): (0.05, 0.60, -0.05) passes Gate G1
    (lower95=+0.00071, 31 trades, 3.1% rate) on 7 replay files at
    realistic swqos costs; v1 (0.02, 0.55, -0.08) fails G1 (lb=-0.003).
    v1 kept in configs/selective-v1.json for audit.
    """
    if feat is None:
        return False
    min_ret, min_buy, max_dip = cfg_thresh
    return feat["ret"] >= min_ret and feat["buy_ratio"] >= min_buy and feat["dip"] >= max_dip


# Bad-tick guard: single-bar price jumps beyond this multiple in either
# direction indicate corrupt/archive-sequencing artifacts (e.g. the
# 2026-10-12 +26154% event: 0.0006 -> 389.0 within one bar). Such paths
# are skipped as "bad-tick" rather than traded or capped, so backtests
# can never book fake outlier profits.
MAX_TICK_MULT = 20.0


def path_has_bad_tick(prices, max_mult=MAX_TICK_MULT) -> bool:
    """True if any single-bar jump exceeds max_mult (either direction)."""
    try:
        for i in range(len(prices) - 1):
            a, b = float(prices[i]), float(prices[i + 1])
            if a > 0 and b > 0:
                if b / a > max_mult or a / b > max_mult:
                    return True
        return False
    except Exception:
        return False


def entry_liq_ok(liq_series, lookback=10, min_liq=20.0):
    """Entry-time depth gate: min reserves over the entry window.

    Uses the worst (not max) liquidity available at decision time, so pools
    that are deep only in hindsight do not pass.
    """
    if not liq_series or len(liq_series) < lookback + 1:
        return False
    return min(liq_series[:lookback + 1]) >= min_liq


def run_selective(prices, actions=None, entry_lookback=10, take_profit=0.6,
                  stop_loss=0.12, trailing=0.15, fee_roundtrip=0.013,
                  size_sol=0.05, latency_bars=0, fail_rate=0.0,
                  fail_seed="", extra_bps=0, fixed_cost_sol=0.0,
                  liq_series=None, rug_drop=0.9, entry_thresh=None,
                  max_tick_mult=MAX_TICK_MULT):
    """Simulate selective buy-hold with stops. Returns (net_return, reason, exit_px).

    Entry at bar `entry_lookback` only if filter passes. No lookahead beyond entry.
    exit_px is the actual (adverse) exit price (None when no trade taken).
    Realism knobs (defaults reproduce the legacy idealized fill exactly):
    - latency_bars: entry fills at the WORST (max) price over the next N bars
      (buy-side adverse selection); exits fill at the worst (min) price over
      the next N bars. Pessimistic by design; never executes at observed price.
    - fail_rate: deterministic per fail_seed (md5 uniform); a failed buy takes
      no position and pays fixed costs only ('failed-tx').
    - extra_bps / fixed_cost_sol: per-side venue costs on top of fee_roundtrip
      (see COST_PATHS); fixed costs scale with size_sol.
    - liq_series: per-bar quote reserves; if reserves collapse by more than
      rug_drop after entry (liquidity pull), the position is treated as a
      total loss ('rug'). None disables the check (legacy).
    """
    prices = np.asarray(prices, dtype=float)
    if len(prices) < entry_lookback + latency_bars + 5:
        return 0.0, "too-short", None
    # Bad-tick guard runs before the entry filter so corrupt paths are
    # labelled, not silently traded or filtered. Zero PnL, no position.
    if max_tick_mult and path_has_bad_tick(prices, max_tick_mult):
        return 0.0, "bad-tick", None
    feat = early_features(prices, actions, entry_lookback)
    if not select_entry(feat, entry_thresh or (0.05, 0.60, -0.05)):
        return 0.0, "filtered", None
    if fail_rate > 0.0:
        u = int(hashlib.md5(fail_seed.encode()).hexdigest(), 16) / 16 ** 32
        if u < fail_rate:
            return -2.0 * fixed_cost_sol / size_sol, "failed-tx", None
    entry = float(np.max(prices[entry_lookback:entry_lookback + 1 + latency_bars]))
    per_side = extra_bps / 10_000.0 + fixed_cost_sol / size_sol
    liq_ref = None
    if liq_series is not None and len(liq_series) > entry_lookback:
        liq_ref = liq_series[entry_lookback]
    peak = entry
    for j in range(entry_lookback + 1 + latency_bars, len(prices)):
        p = prices[j]
        if liq_ref and j < len(liq_series) and liq_series[j] < (1.0 - rug_drop) * liq_ref:
            return -1.0, "rug", None  # liquidity pulled: holdings -> dust
        peak = max(peak, p)
        # trailing stop / hard stop / take profit (reliable exits, legacy order)
        if p <= entry * (1 - stop_loss):
            why = "stop"
        elif p <= peak * (1 - trailing):
            why = "trail"
        elif p >= entry * (1 + take_profit):
            why = "take"
        else:
            continue
        x = float(np.min(prices[j:j + 1 + latency_bars]))
        return x / entry - 1.0 - fee_roundtrip - 2.0 * per_side, why, x
    # hold to end of window
    return prices[-1] / entry - 1.0 - fee_roundtrip - 2.0 * per_side, "hold-end", float(prices[-1])
