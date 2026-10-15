"""Offline fixtures from validated on-chain transactions (no RPC in tests)."""
BUY_FIXTURE = {
    "ix_name": "buy_exact_quote_in",
    "pool_base_token_reserves": 47821746268213,
    "pool_quote_token_reserves": 351373799319,
    "virtual_quote_reserves": 17581956634,
    "user_quote_amount_in": 309081,
    "base_amount_out": 40060990,
    "lp_fee": 619, "protocol_fee": 155, "coin_creator_fee": 2319, "buyback_fee": 77,
    "quote_amount_in": 312174, "quote_amount_in_with_lp_fee": 309700,
    "max_quote_amount_in": 312174, "cashback": 0, "holder_rewards": 0,
}
SELL_FIXTURE = {
    "pool_base_token_reserves": 31768178482296,
    "pool_quote_token_reserves": 538474446047,
    "virtual_quote_reserves": 17583880469,
    "base_amount_in": 37802652, "quote_amount_out": 661682,
    "lp_fee": 1324, "protocol_fee": 331, "coin_creator_fee": 4301, "buyback_fee": 165,
    "quote_amount_out_without_lp_fee": 660358, "user_quote_amount_out": 655726,
    "cashback": 0, "holder_rewards": 0,
}
