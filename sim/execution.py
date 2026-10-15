"""Pure stateless execution: quote/apply with latency, impact, failure costs."""
from __future__ import annotations
import numpy as np
from pumpswap_sim import (
    predict_buy_exact_in, predict_buy_exact_out_quote, predict_sell_gross,
    apply_buy, apply_sell, LAMPORTS_PER_SOL,
)


def sample_latency(rng, base_ms=800, jitter_ms=400):
    return float(max(0, rng.normal(base_ms, jitter_ms)))


def quote_buy(state, sol_in, fee_bps=(20, 5, 75), tip_lamports=5_000):
    """state=(q_eff, b_res) raw units. Returns (tokens_raw, fees, new_state)."""
    q, b = int(state[0]), int(state[1])
    x = int(round(float(sol_in) * LAMPORTS_PER_SOL))
    if x <= 1:
        raise ValueError("dust input")
    tok = predict_buy_exact_in(b, q, x)
    lp = (x * fee_bps[0] + 9_999) // 10_000
    pr = (x * fee_bps[1] + 9_999) // 10_000
    cr = (x * fee_bps[2] + 9_999) // 10_000
    nq, nb = apply_buy(q, b, x, lp, tok)
    return tok, {"lp": lp, "protocol": pr, "creator": cr, "tip": int(tip_lamports),
                 "gross_lamports": x + lp + pr + cr}, (nq, nb)


def quote_sell(state, tokens_in, fee_bps=(20, 5, 75), tip_lamports=5_000):
    q, b = int(state[0]), int(state[1])
    t = int(tokens_in)
    gross = predict_sell_gross(q, b, t)
    lp = (gross * fee_bps[0] + 9_999) // 10_000
    pr = (gross * fee_bps[1] + 9_999) // 10_000
    cr = (gross * fee_bps[2] + 9_999) // 10_000
    net = gross - lp - pr - cr
    if net < 0:
        raise ValueError("fees exceed gross")
    nq, nb = apply_sell(q, b, gross, lp, t)
    return net, {"lp": lp, "protocol": pr, "creator": cr, "tip": int(tip_lamports),
                 "gross_lamports": gross}, (nq, nb)
