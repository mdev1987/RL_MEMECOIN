"""PumpSwap simulator with validated reserve and fee accounting.

Validated against on-chain BuyEvent/SellEvent (Steps 68-107, 68/68 batch):
- effective quote = raw quote vault + virtual_quote_reserves (signed)
- buy_exact_quote_in[_v2]: token_out = B*(x-1)//(Q+V+x-1)
  lp_identity: quote_with_lp - user - lp == 0
  total_identity: quote_in - quote_with_lp - protocol - creator == 0
- buy (exact-base-out): quote_in = ceil(Q*y/(B-y)) == quote_amount_in
  lp_identity: quote_with_lp - quote_in - lp == 0
- sell: gross = Q*x//(B+x), net = gross-lp-protocol-creator == user_net
  lp_identity: gross - lp - quote_without_lp == 0
- buyback = floor(protocol/2), cashback == 0, holder_rewards != creator (informational only)
"""
from __future__ import annotations

LAMPORTS_PER_SOL = 1_000_000_000
WSOL_MINT = "So11111111111111111111111111111111111111112"

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58_encode(raw: bytes) -> str:
    z = len(raw) - len(raw.lstrip(b"\x00"))
    n = int.from_bytes(raw, "big")
    ch = []
    while n:
        n, r = divmod(n, 58)
        ch.append(B58[r])
    return "1" * z + "".join(reversed(ch))


_WIDTHS = {
    "u8": (1, False), "i8": (1, True),
    "u16": (2, False), "i16": (2, True),
    "u32": (4, False), "i32": (4, True),
    "u64": (8, False), "i64": (8, True),
    "u128": (16, False), "i128": (16, True),
}


def decode_all_fields(data: bytes, fields: list[dict]) -> dict:
    """Decode Borsh primitives. First 8 bytes = Anchor discriminator."""
    off = 8
    out: dict = {}
    for f in fields:
        name, kind = f["name"], f["type"]
        if kind == "pubkey":
            raw = data[off:off + 32]
            if len(raw) != 32:
                raise ValueError("Incomplete pubkey")
            out[name] = b58_encode(raw)
            off += 32
        elif kind == "bool":
            out[name] = bool(data[off])
            off += 1
        elif kind == "string":
            ln = int.from_bytes(data[off:off + 4], "little")
            off += 4
            out[name] = data[off:off + ln].decode()
            off += ln
        elif kind in _WIDTHS:
            w, s = _WIDTHS[kind]
            raw = data[off:off + w]
            if len(raw) != w:
                raise ValueError(f"Incomplete field {name}")
            out[name] = int.from_bytes(raw, "little", signed=s)
            off += w
        else:
            raise ValueError(f"Unsupported type {kind!r} for {name!r}")
    return out


def ceil_fee(amount: int, bps: int) -> int:
    amount, bps = int(amount), int(bps)
    return (amount * bps + 9_999) // 10_000 if bps > 0 else 0


def predict_buy_tokens(base_reserve: int, eff_quote: int, user_quote_in: int) -> int:
    """Legacy approx (off by ~+129 raw). Kept for compat; prefer exact below."""
    return (int(base_reserve) * int(user_quote_in)) // (int(eff_quote) + int(user_quote_in))


def predict_buy_exact_in(base_reserve: int, eff_quote: int, user_quote_in: int) -> int:
    """Exact for buy_exact_quote_in[_v2]: -1 lamport adjustment."""
    x = int(user_quote_in) - 1
    if x <= 0:
        return 0
    return (int(base_reserve) * x) // (int(eff_quote) + x)


def predict_buy_exact_out_quote(base_reserve: int, eff_quote: int, base_out: int) -> int:
    """Exact for buy (exact base out): ceil(R*y/(B-y)) == quote_amount_in."""
    B, R, y = int(base_reserve), int(eff_quote), int(base_out)
    denom = B - y
    if denom <= 0 or y <= 0:
        raise ValueError("Invalid base reserve/output")
    return (R * y + denom - 1) // denom


def predict_sell_gross(eff_quote: int, base_reserve: int, token_in: int) -> int:
    return (int(eff_quote) * int(token_in)) // (int(base_reserve) + int(token_in))


def apply_buy(start_q: int, start_b: int, net_in: int, lp_fee: int, token_out: int) -> tuple[int, int]:
    return start_q + net_in + lp_fee, start_b - token_out


def apply_sell(start_q: int, start_b: int, gross_out: int, lp_fee: int, token_in: int) -> tuple[int, int]:
    return start_q - gross_out + lp_fee, start_b + token_in


def check_fee_exact(gross: int, user: int, lp: int, protocol: int, creator: int) -> int:
    return int(gross) - int(user) - (int(lp) + int(protocol) + int(creator))


def pumpswap_event_calculator(event_name: str, ev: dict) -> dict:
    """Unified dispatcher mirroring notebook cell 115. Raw integer units, no state mutation."""
    def integer(name: str) -> int:
        if name not in ev or ev[name] is None:
            raise ValueError(f"Missing event field: {name}")
        return int(ev[name])

    def require_positive(name: str, value: int) -> None:
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value}")

    result: dict = {"event_name": event_name, "ix_name": ev.get("ix_name")}

    if event_name == "BuyEvent":
        ix = str(ev["ix_name"])
        B = integer("pool_base_token_reserves")
        Q = integer("pool_quote_token_reserves") + integer("virtual_quote_reserves")
        require_positive("effective base reserves", B)
        require_positive("effective quote reserves", Q)
        lp = integer("lp_fee")
        protocol = integer("protocol_fee")
        creator = integer("coin_creator_fee")
        buyback = integer("buyback_fee")
        quote_in = integer("quote_amount_in")
        quote_with_lp = integer("quote_amount_in_with_lp_fee")
        max_quote = integer("max_quote_amount_in")
        if ix in ("buy_exact_quote_in", "buy_exact_quote_in_v2"):
            user_input = integer("user_quote_amount_in")
            adj = user_input - 1
            if adj < 0:
                raise ValueError("Adjusted quote input cannot be negative.")
            predicted = B * adj // (Q + adj)
            actual = integer("base_amount_out")
            result.update({
                "curve_quantity": "base_output_raw",
                "predicted_curve_raw": predicted,
                "actual_curve_raw": actual,
                "curve_error_raw": predicted - actual,
                "lp_identity_error_raw": quote_with_lp - user_input - lp,
                "total_quote_identity_error_raw": quote_in - quote_with_lp - protocol - creator,
                "maximum_quote_check": quote_in <= max_quote,
            })
        elif ix == "buy":
            base_out = integer("base_amount_out")
            denom = B - base_out
            if base_out <= 0 or denom <= 0:
                raise ValueError("Base output must be positive and below base reserves.")
            predicted = (Q * base_out + denom - 1) // denom
            total_cost = quote_with_lp + protocol + creator
            result.update({
                "curve_quantity": "quote_cost_raw",
                "predicted_curve_raw": predicted,
                "actual_curve_raw": quote_in,
                "curve_error_raw": predicted - quote_in,
                "lp_identity_error_raw": quote_with_lp - quote_in - lp,
                "implied_total_quote_cost_raw": total_cost,
                "maximum_quote_check": total_cost <= max_quote,
            })
        else:
            raise ValueError(f"Unsupported buy instruction: {ix}")
        result["buyback_allocation_error_raw"] = buyback - protocol // 2
        result["cashback_raw"] = int(ev.get("cashback", 0))
        result["holder_rewards_raw"] = int(ev.get("holder_rewards", 0))
    elif event_name == "SellEvent":
        B = integer("pool_base_token_reserves")
        Q = integer("pool_quote_token_reserves") + integer("virtual_quote_reserves")
        base_in = integer("base_amount_in")
        require_positive("effective base reserves", B)
        require_positive("effective quote reserves", Q)
        require_positive("base input", base_in)
        gross_pred = Q * base_in // (B + base_in)
        gross_actual = integer("quote_amount_out")
        lp = integer("lp_fee")
        protocol = integer("protocol_fee")
        creator = integer("coin_creator_fee")
        buyback = integer("buyback_fee")
        quote_without_lp = integer("quote_amount_out_without_lp_fee")
        user_net = integer("user_quote_amount_out")
        predicted_net = gross_pred - lp - protocol - creator
        result.update({
            "curve_quantity": "gross_quote_output_raw",
            "predicted_curve_raw": gross_pred,
            "actual_curve_raw": gross_actual,
            "curve_error_raw": gross_pred - gross_actual,
            "predicted_trader_net_raw": predicted_net,
            "actual_trader_net_raw": user_net,
            "trader_net_error_raw": predicted_net - user_net,
            "lp_identity_error_raw": gross_actual - lp - quote_without_lp,
            "buyback_allocation_error_raw": buyback - protocol // 2,
            "cashback_raw": int(ev.get("cashback", 0)),
            "holder_rewards_raw": int(ev.get("holder_rewards", 0)),
        })
    else:
        raise ValueError(f"Unsupported event type: {event_name}")
    return result
