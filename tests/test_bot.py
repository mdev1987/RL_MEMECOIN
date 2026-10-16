"""Deterministic robustness tests: sim exactness, env no-lookahead, risk, bundle."""
import numpy as np
from pumpswap_sim import predict_buy_exact_in, predict_buy_exact_out_quote, predict_sell_gross
from bot import BotConfig, PumpSwapEnv, LinearPolicy
from bot.risk import RiskState, check_order
from bot.data import group_bundles


def test_sim_exact():
    B, Q, V = 47_821_746_268_213, 351_373_799_319, 17_581_956_634
    x = 309_081
    assert predict_buy_exact_in(B, Q + V, x) == 40_060_990, "buy_exact_in -1 failed"
    y = 10_221_480_639
    B2, R2 = 84_859_551_632_093, 201_849_351_934 + 17_580_288_693
    assert predict_buy_exact_out_quote(B2, R2, y) == 26_433_866, "buy exact-out ceil failed"
    assert predict_sell_gross(556_058_326_516, 31_768_178_482_296, 37_802_652) == 661_682


def test_env_no_lookahead():
    cfg = BotConfig(max_steps=50, seed=1)
    env = PumpSwapEnv(cfg)
    o = env.reset()
    assert o.shape == (5,)
    eq0 = env.equity
    o2, r, d, info = env.step(0)
    assert env.equity == eq0, "hold must not change equity"


def test_risk_caps():
    cfg = BotConfig(max_position_sol=0.5, max_daily_loss_sol=0.2)
    st = RiskState(day_pnl=-0.3)
    ok, why = check_order(cfg, st, "buy", 0.1, 1.0, 1.0)
    assert not ok and why == "daily-loss", why
    st2 = RiskState()
    ok2, _ = check_order(cfg, st2, "buy", 5.0, 1.0, 1.0)
    assert not ok2, "position cap failed"


def test_bundle_grouping():
    ev = [{"mint": "A", "timestamp": 1000.0}, {"mint": "A", "timestamp": 1000.002},
          {"mint": "A", "timestamp": 1001.0}]
    g = group_bundles(ev, bundle_ms=3)
    assert len(g) == 2 and len(g[0]) == 2, f"bundle grouping failed: {g}"


def test_policy_train_step():
    pol = LinearPolicy(seed=0)
    obs = [np.zeros(5), np.ones(5)]
    pol.update(obs, [0, 1], [0.01, -0.02])
    assert np.isfinite(pol.W).all()


if __name__ == "__main__":
    for fn in [test_sim_exact, test_env_no_lookahead, test_risk_caps,
               test_bundle_grouping, test_policy_train_step]:
        fn()
        print(f"PASS {fn.__name__}")

def test_strategy_selective():
    import numpy as np
    from bot.strategy import run_selective
    up = list(1.0 * (1 + 0.01) ** np.arange(60))
    acts = ["buy"] * 60
    r, why, exit_px = run_selective(up, acts)
    assert r > 0 and why in ("take", "hold-end", "trail"), (r, why)
    assert exit_px is not None and abs(r - (exit_px / up[10] - 1.0 - 0.013)) < 1e-9, (r, exit_px)
    flat = [1.0] * 60
    r2, why2, x2 = run_selective(flat, ["sell"] * 60)
    assert r2 == 0.0 and why2 == "filtered", (r2, why2)
    assert x2 is None


def test_replay_split_no_leak():
    from bot.replay_eval import split_paths
    fake = [{"mint": f"m{i}"} for i in range(20)]
    tr, te = split_paths(fake)
    assert not (set(d["mint"] for d in tr) & set(d["mint"] for d in te))

def test_sim_fixtures_offline():
    from sim import pumpswap_event_calculator
    from sim.fixtures import BUY_FIXTURE, SELL_FIXTURE
    r = pumpswap_event_calculator("BuyEvent", BUY_FIXTURE)
    assert r["curve_error_raw"] == 0 and r["lp_identity_error_raw"] == 0
    assert r["total_quote_identity_error_raw"] == 0 and r["buyback_allocation_error_raw"] == 0
    s = pumpswap_event_calculator("SellEvent", SELL_FIXTURE)
    assert s["curve_error_raw"] == 0 and s["trader_net_error_raw"] == 0
    assert s["lp_identity_error_raw"] == 0 and s["buyback_allocation_error_raw"] == 0


def test_sim_properties():
    from sim import quote_buy, quote_sell
    q0, b0 = 368_955_755_953, 47_821_746_268_213
    tok, fb, (q1, b1) = quote_buy((q0, b0), 0.05)
    assert tok > 0 and b1 == b0 - tok
    # roundtrip loses money after fees (raw units)
    net, fs, _ = quote_sell((q1, b1), tok)
    assert net / 1e9 < 0.05, "roundtrip should not profit after fees"
    # monotonicity
    t1, _, _ = quote_buy((q0, b0), 0.01)
    t2, _, _ = quote_buy((q0, b0), 0.02)
    assert t2 > t1


def test_timestamp_contract():
    from features.contract import check_cutoff
    assert check_cutoff([("f", 10.0)], decision_ts=11.0, latency_s=0.8)
    try:
        check_cutoff([("leak", 10.9)], decision_ts=11.0, latency_s=0.8)
        raise SystemExit("contract failed to catch leak")
    except AssertionError:
        pass


def test_gate_g1():
    from eval.gate import gate_g1
    g = gate_g1({"d1": [0.02, 0.03], "d2": [0.01, 0.04]})
    assert g["pass"] and g["lower95"] > 0
    g2 = gate_g1({"d1": [-0.05, 0.01], "d2": [-0.02, 0.0]})
    assert not g2["pass"]

def test_wallet_ledger():
    import os
    from bot.wallet import Wallet
    p = "/tmp/ut_wallet.json"
    try: os.remove(p)
    except Exception: pass
    w = Wallet(path=p, start=1.0, daily_stop=0.10, dd_stop=0.30, max_pos=0.05)
    ok, _ = w.can_open(0.05, "a")
    assert ok
    ok, _ = w.can_open(0.06, "b")
    assert not ok
    w.apply_close("a", 0.02)
    ok, _ = w.can_open(0.05, "a")
    assert not ok
    w2 = Wallet(path=p, start=1.0)
    assert abs(w2.s.balance - 1.02) < 1e-9 and w2.s.wins == 1


def test_wallet_rate_limit():
    from bot.wallet import Wallet
    p = "/tmp/ut_wallet_ratelimit.json"
    import os
    try: os.remove(p)
    except Exception: pass
    w = Wallet(path=p, start=1.0, max_pos=1.0, max_per_hour=2)
    for m in ("a", "b"):
        ok, _ = w.can_open(0.05, m)
        assert ok, m
        w.apply_close(m, 0.0)
    ok, why = w.can_open(0.05, "c")
    assert not ok and why == "rate-limit", why


def test_evaluate_runs():
    from bot.replay_eval import evaluate
    import numpy as np
    up = list(1.0 * (1 + 0.01) ** np.arange(60))
    paths = [{"mint": "m1", "pool": "p", "prices": up, "actions": ["buy"] * 60, "liq": 35.0},
             {"mint": "m2", "pool": "p", "prices": [1.0] * 60, "actions": ["sell"] * 60, "liq": 5.0}]
    m = evaluate(paths)
    assert m["n"] == 2 and m["traded"] == 1, m
    assert m["reasons"].get("illiquid") == 1, m["reasons"]


def test_realistic_latency_adverse():
    import numpy as np
    from bot.strategy import run_selective
    px = list(1.0 * (1.01) ** np.arange(11)) + [2.0] + [2.0] * 60
    acts = ["buy"] * len(px)
    r0, w0, _ = run_selective(px, acts)
    assert r0 > 0.5 and w0 == "take", (r0, w0)
    r1, w1, x1 = run_selective(px, acts, latency_bars=1)
    assert w1 == "hold-end" and abs(r1 + 0.013) < 1e-9, (r1, w1, x1)


def test_realistic_fail_fee_only():
    import numpy as np
    from bot.strategy import run_selective
    up = list(1.0 * (1 + 0.01) ** np.arange(60))
    r, why, x = run_selective(up, ["buy"] * 60, fail_rate=1.0, fail_seed="m1",
                               fixed_cost_sol=0.001, size_sol=0.05)
    assert why == "failed-tx" and x is None and abs(r + 0.04) < 1e-12, (r, why)
    r2, _, _ = run_selective(up, ["buy"] * 60, fail_rate=1.0, fail_seed="m1",
                             fixed_cost_sol=0.001, size_sol=0.05)
    assert r2 == r, "fail roll must be deterministic per seed"


def test_wallet_apply_fee():
    import os
    from bot.wallet import Wallet
    p = "/tmp/ut_wallet_fee.json"
    try: os.remove(p)
    except Exception: pass
    w = Wallet(path=p, start=1.0, max_pos=1.0)
    w.apply_fee("m9", 0.002)
    assert abs(w.s.balance - 0.998) < 1e-9 and w.s.wins == 0 and w.s.losses == 0
    assert "m9" in w.s.seen and w.s.hour_trades == 1


def test_wallet_seen_ttl():
    import os
    import time
    from bot.wallet import Wallet
    p = "/tmp/ut_wallet_ttl.json"
    try: os.remove(p)
    except Exception: pass
    w = Wallet(path=p, start=1.0, max_pos=1.0, seen_ttl_hours=1)
    w.apply_close("m1", 0.01)
    ok, why = w.can_open(0.05, "m1")
    assert not ok and why == "duplicate", why
    w.s.seen["m1"] = time.time() - 3700  # older than 1h TTL
    ok, why = w.can_open(0.05, "m1")
    assert ok, why


def test_wallet_seen_migration():
    import json
    import os
    from bot.wallet import Wallet
    p = "/tmp/ut_wallet_mig.json"
    try: os.remove(p)
    except Exception: pass
    json.dump({"balance": 1.0, "start": 1.0, "seen": ["a", "b"]}, open(p, "w"))
    w = Wallet(path=p, start=1.0)
    assert isinstance(w.s.seen, dict) and set(w.s.seen) == {"a", "b"}
    ok, _ = w.can_open(0.05, "a")
    assert not ok  # migrated entries still within TTL


def test_wallet_day_rollover():
    import os
    from bot.wallet import Wallet
    from bot import wallet as wmod
    p = "/tmp/ut_wallet_day.json"
    try: os.remove(p)
    except Exception: pass
    w = Wallet(path=p, start=1.0, max_pos=1.0)
    w.apply_close("m1", -0.05)
    assert abs(w.s.day_pnl + 0.05) < 1e-9
    real_today = wmod._today
    wmod._today = lambda: "2999-01-01"  # force a new day
    try:
        ok, _ = w.can_open(0.05, "m2")
        assert ok
        assert w.s.day_pnl == 0.0 and w.s.day == "2999-01-01"
    finally:
        wmod._today = real_today


def test_entry_liq_min_gate():
    from bot.strategy import entry_liq_ok
    assert entry_liq_ok([35.0] * 11)
    assert not entry_liq_ok([35.0] * 10 + [5.0])  # max passes, min fails
    assert not entry_liq_ok([25.0] * 11)  # v3 floor is 30 SOL
    assert not entry_liq_ok([35.0] * 5)


def test_rug_total_loss():
    import numpy as np
    from bot.strategy import run_selective
    # healthy ramp into entry, then reserves collapse 99% (liquidity pull)
    px = list(1.0 * (1.01) ** np.arange(30))
    acts = ["buy"] * 30
    liq = [100.0] * 15 + [0.5] * 15
    r, why, x = run_selective(px, acts, liq_series=liq)
    assert (r, why, x) == (-1.0, "rug", None), (r, why, x)
    # no liq series -> legacy path unaffected
    r2, w2, _ = run_selective(px, acts)
    assert w2 != "rug", (r2, w2)


def test_entry_thresh_threading():
    import numpy as np
    from bot.strategy import run_selective
    up = list(1.0 * (1 + 0.01) ** np.arange(60))
    r0, w0, _ = run_selective(up, ["buy"] * 60)
    assert w0 != "filtered"
    r1, w1, _ = run_selective(up, ["buy"] * 60,
                              entry_thresh=(0.5, 0.55, -0.08))
    assert (r1, w1) == (0.0, "filtered"), (r1, w1)


def test_ledger_row_append():
    import json
    import os
    from bot.ledger import append, row
    p = "/tmp/ut_decisions.jsonl"
    try: os.remove(p)
    except Exception: pass
    append(p, row(file="11.jsonl.zst", mint="m1", reason="take",
                  r_net=0.5, pnl_sol=0.025, balance_after=1.025,
                  wins=1, losses=0))
    d = json.loads(open(p).read().strip())
    assert d["mint"] == "m1" and d["reason"] == "take"
    assert d["pnl_sol"] == 0.025 and "ts" in d


def test_bad_tick_guard():
    from bot.strategy import run_selective, path_has_bad_tick
    # 25x single-bar jump -> corrupt, must skip not trade
    px = [1.0] * 20 + [25.0] + [25.0] * 20
    assert path_has_bad_tick(px)
    r, why, x = run_selective(px, ["buy"] * len(px))
    assert (r, why, x) == (0.0, "bad-tick", None), (r, why, x)
    # healthy 1%/bar ramp has no bad tick
    import numpy as np
    good = list(1.0 * (1.01) ** np.arange(60))
    assert not path_has_bad_tick(good)


def test_bad_tick_outlier_261x():
    # regression for 2026-10-12 +26154% event (4X6mcyv4ocju):
    # entry-filter passes, but a 0.0006 -> 389.0 bar is bad data.
    # must be bad-tick even without liq_series (rug needs liq).
    from bot.strategy import run_selective
    px = [0.000581, 0.000576, 0.000576, 0.000576, 0.000576,
          0.000572, 0.000581, 0.000587, 0.000593, 0.000599,
          0.000599, 0.000602] + [389.88011633875107] + [0.158] * 20
    acts = ["buy"] * len(px)
    r, why, x = run_selective(px, acts, latency_bars=1, liq_series=None)
    assert why == "bad-tick" and r == 0.0 and x is None, (r, why, x)


def test_v2_default_filter_stricter():
    import numpy as np
    from bot.strategy import run_selective
    # +3% over 10 bars passed v1 (min_ret 0.02) but must fail v2 (min_ret 0.05)
    px = list(1.0 * (1.003) ** np.arange(60))
    r, why, _ = run_selective(px, ["buy"] * 60)
    assert (r, why) == (0.0, "filtered"), (r, why)
    # +11% ramp still passes v2
    up = list(1.0 * (1.01) ** np.arange(60))
    r2, w2, _ = run_selective(up, ["buy"] * 60)
    assert w2 != "filtered", (r2, w2)


def test_pump_pool_predicate_both_schemas():
    from bot.replay_eval import is_pump_pool
    assert is_pump_pool({"pool": "pump-amm"})
    assert is_pump_pool({"pool": "pump"})
    assert is_pump_pool({"pool": "91X3n4MxyeYxVp29hirHGBGKFMZP4VNP9e9gv2X2ed2p",
                         "protocol": "PUMPSWAP"})
    assert not is_pump_pool({"pool": "meteora-dlmm", "protocol": "METEORA"})
    assert not is_pump_pool({"pool": "raydium-v4", "protocol": "RAYDIUM"})
    assert not is_pump_pool({})


def test_load_paths_new_schema():
    import io
    import json
    import zstandard as zstd
    from bot.replay_eval import load_paths
    p = "/tmp/ut_newschema.jsonl.zst"
    cctx = zstd.ZstdCompressor()
    lines = []
    for i in range(50):
        lines.append(json.dumps({
            "action": "buy" if i % 3 else "sell",
            "quoteMint": "So11111111111111111111111111111111111111112",
            "price": 0.001 * (1.005 ** i), "pool": "PoolAddr11111111111111111111111111111111",
            "protocol": "PUMPSWAP", "block": 1000 + i, "timestamp": 1700000000.0 + i,
            "mint": "TestMint111111111111111111111111111111111", "quoteInPool": 50.0,
        }))
    # meteora decoy must be excluded
    lines.append(json.dumps({
        "action": "buy", "quoteMint": "So11111111111111111111111111111111111111112",
        "price": 1.0, "pool": "DlmmAddr1111111111111111111111111111111",
        "protocol": "METEORA", "block": 1000, "timestamp": 1700000000.0,
        "mint": "DecoyMint11111111111111111111111111111111", "quoteInPool": 500.0,
    }))
    with open(p, "wb") as f:
        f.write(cctx.compress("\n".join(lines).encode()))
    paths, n = load_paths(p, max_lines=1000)
    assert n == 51, n
    assert len(paths) == 1 and paths[0]["mint"].startswith("TestMint"), paths
    assert len(paths[0]["prices"]) == 50


def test_per_file_rotation_covers_all():    # per-file visit counters must cover every index within
    # len/gcd(len,SLICE) visits; the old global stride visited only
    # 4 offsets for len=140 and permanently missed idx 41,48,77,80.
    import math
    for ln in (140, 157, 156, 147, 135, 138, 117):
        sl = 25
        seen_offsets = set()
        visits = 0
        for v in range(ln * 2):
            off = (v * sl) % ln
            seen_offsets.add(off)
            visits += 1
            if len(seen_offsets) >= ln / math.gcd(ln, sl):
                break
        covered = set()
        for off in seen_offsets:
            for k in range(sl):
                covered.add((off + k) % ln)
        assert covered == set(range(ln)), (ln, len(covered))
        # old global stride counterexample: len=140 visited {15,50,85,120}
        if ln == 140:
            old = {15, 50, 85, 120}
            old_covered = {(o + k) % ln for o in old for k in range(sl)}
            assert 41 not in old_covered and 77 not in old_covered


def test_jup_quote_fail_open():
    import os
    from unittest.mock import patch
    from bot import jup
    assert jup.fmt_quote(None, "buy") is None
    line = jup.fmt_quote({"outAmount": "123", "priceImpactPct": "0.5",
                          "route": [(100, "PumpSwap")]}, "buy")
    assert "123" in line and "PumpSwap" in line
    # no API key -> None without network
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("JUPITER_API_KEY", None)
        assert jup.order_quote("A", "B", 1000) is None
    # HTTP error -> None
    class _Bad:
        ok = False
        status_code = 400
        text = "no route"
    with patch.dict(os.environ, {"JUPITER_API_KEY": "x"}):
        with patch("bot.jup.requests.get", return_value=_Bad()):
            assert jup.order_quote("A", "B", 1000) is None
    # ok path parses route
    class _Ok:
        ok = True

        def json(self):
            return {"inAmount": "1000", "outAmount": "555",
                    "priceImpactPct": "1.2",
                    "routePlan": [{"percent": 100,
                                   "swapInfo": {"label": "PumpSwap"}}]}
    with patch.dict(os.environ, {"JUPITER_API_KEY": "x"}):
        with patch("bot.jup.requests.get", return_value=_Ok()):
            q = jup.order_quote("A", "B", 1000)
            assert q["outAmount"] == "555" and q["route"] == [(100, "PumpSwap")]


def test_jup_decimals_cache_and_fail():
    from unittest.mock import patch
    from bot import jup
    jup._decimals_cache.clear()
    jup._decimals_cache["M"] = 6
    assert jup.token_decimals("M", "key") == 6  # cache hit, no network
    with patch("bot.jup.requests.post", side_effect=TimeoutError()):
        assert jup.token_decimals("N*N", "") is None  # no key -> None fast
        assert jup.token_decimals("N2", "key") is None  # net fail -> None
    assert jup.enabled() in (True, False)


def _live_order(**kw):
    o = {"inAmount": "10000000", "outAmount": "9000000",
         "otherAmountThreshold": "8000000", "priceImpact": "-0.5",
         "signatureFeePayer": "TAKER", "prioritizationFeeLamports": 5000,
         "transaction": "dHg=", "requestId": "r1", "router": "metis"}
    o.update(kw)
    return o


def test_live_guards():
    from bot import live
    ok, why = live.check_guards(_live_order(), "TAKER", 1.0)
    assert ok, why
    ok, why = live.check_guards(_live_order(priceImpact="-6.0"), "TAKER", 1.0)
    assert not ok and "impact" in why, why
    ok, why = live.check_guards(
        _live_order(outAmount="7000000"), "TAKER", 1.0)
    assert not ok and "min-out" in why, why
    ok, why = live.check_guards(
        _live_order(signatureFeePayer="SPONSOR"), "TAKER", 1.0)
    assert not ok and "gasless" in why, why
    ok, why = live.check_guards(
        _live_order(prioritizationFeeLamports=999999999), "TAKER", 1.0)
    assert not ok and "priority" in why, why
    bad = _live_order()
    del bad["transaction"]
    ok, why = live.check_guards(bad, "TAKER", 1.0)
    assert not ok and "no transaction" in why, why


def test_live_place_order_gates():
    import os
    from unittest.mock import patch
    from bot import live
    with patch.dict(os.environ, {"LIVE_MAX_SOL": "0.01"}):
        # kill file refuses before any network/key
        with patch("bot.live.killed", return_value=True):
            try:
                live.place_order("A", "B", 100, 0.001)
                raise SystemExit("kill must refuse")
            except RuntimeError as e:
                assert "KILL" in str(e)
        # size cap refuses
        with patch("bot.live.killed", return_value=False):
            try:
                live.place_order("A", "B", 100, 99.0)
                raise SystemExit("cap must refuse")
            except RuntimeError as e:
                assert "LIVE_MAX_SOL" in str(e)


def test_live_shadow_never_executes():
    import os
    from unittest.mock import patch
    from bot import live

    class _KP:
        def pubkey(self):
            return "TAKER"

        def sign_message(self, msg):
            class _S:
                def verify(self, p, m):
                    return True
            return _S()

    order = _live_order()
    with patch.dict(os.environ, {"LIVE_MAX_SOL": "1.0"}):
        with patch("bot.live.killed", return_value=False), \
             patch("bot.live._load_keypair", return_value=_KP()), \
             patch("bot.live.get_order", return_value=order) as go, \
             patch("bot.live.sign_order", return_value="c2ln") as so, \
             patch("bot.live.execute_signed") as ex:
            rc = live.place_order("A", "B", 100, 0.01, shadow=True)
            assert rc.shadow and go.called and so.called and not ex.called


def test_live_execute_failure_mapping():
    import os
    from unittest.mock import patch
    from bot import live

    class _KP:
        def pubkey(self):
            return "TAKER"

        def sign_message(self, msg):
            class _S:
                def verify(self, p, m):
                    return True
            return _S()

    order = _live_order()
    with patch.dict(os.environ, {"LIVE_MAX_SOL": "1.0"}):
        with patch("bot.live.killed", return_value=False), \
             patch("bot.live._load_keypair", return_value=_KP()), \
             patch("bot.live.get_order", return_value=order), \
             patch("bot.live.sign_order", return_value="c2ln"), \
             patch("bot.live.execute_signed",
                   return_value={"status": "Failed", "error": "no land",
                                 "code": -1000}):
            try:
                live.place_order("A", "B", 100, 0.01)
                raise SystemExit("must raise")
            except RuntimeError as e:
                assert "retryable=True" in str(e), e


def test_live_sign_roundtrip():
    """Sign path without network: build a real v0 message locally,
    serialize like /order would, then sign_order must verify."""
    import base64
    from solders.hash import Hash
    from solders.instruction import Instruction
    from solders.keypair import Keypair
    from solders.message import MessageV0
    from solders.pubkey import Pubkey
    from solders.transaction import VersionedTransaction
    from bot import live

    kp = Keypair()
    ix = Instruction(program_id=Pubkey.default(), data=b"\x00", accounts=[])
    msg = MessageV0.try_compile(kp.pubkey(), [ix], [],
                                Hash(bytes(32)))
    wire = base64.b64encode(bytes(VersionedTransaction.populate(
        msg, [kp.sign_message(bytes(msg))]))).decode()
    order = _live_order(transaction=wire)
    out = live.sign_order(order, kp)
    back = VersionedTransaction.from_bytes(base64.b64decode(out))
    assert bytes(back.message) == bytes(msg)


def test_live_loop_refuses():
    import os
    from unittest.mock import patch
    from bot import live_loop

    class _Ntf:
        def send_alert(self, *a, **k):
            self.last = (a, k)

    with patch.dict(os.environ,
                    {"LIVE_TRADING": "0", "LIVE_CONFIRM": "NO",
                     "_LIVE_FLAG": ""}, clear=False), \
         patch("bot.live_loop.get_notifier", return_value=_Ntf()):
        try:
            live_loop.main(require_live_flag=True)
            raise SystemExit("must refuse")
        except SystemExit as e:
            assert "LIVE REFUSED" in str(e), e


def patch_dict_clean():
    import os
    from unittest.mock import patch
    return patch.dict(os.environ,
                      {"LIVE_TRADING": "0", "LIVE_CONFIRM": "NO",
                       "_LIVE_FLAG": ""}, clear=False)


def test_live_fee_cap_guard():
    import os
    from unittest.mock import patch
    from bot import live
    base = _live_order()
    with patch.dict(os.environ, {"LIVE_MAX_FEE_BPS": "200"}):
        ok, _ = live.check_guards(base, "TAKER", 1.0)
        assert ok
        ok, why = live.check_guards(dict(base, feeBps=500), "TAKER", 1.0)
        assert not ok and "fee" in why, why


def test_live_receipt_actuals():
    import os
    from unittest.mock import patch
    from bot import live

    class _KP:
        def pubkey(self):
            return "TAKER"

        def sign_message(self, msg):
            class _S:
                def verify(self, p, m):
                    return True
            return _S()

    order = _live_order()
    res = {"status": "Success", "signature": "sig1", "slot": "9",
           "totalInputAmount": "10000000", "totalOutputAmount": "8990000"}
    with patch.dict(os.environ, {"LIVE_MAX_SOL": "1.0", "HELIUS_API_KEY": ""}):
        with patch("bot.live.killed", return_value=False), \
             patch("bot.live._load_keypair", return_value=_KP()), \
             patch("bot.live.get_order", return_value=order), \
             patch("bot.live.sign_order", return_value="c2ln"), \
             patch("bot.live.execute_signed", return_value=res):
            rc = live.place_order("A", "B", 100, 0.01)
            assert not rc.shadow and rc.total_in == "10000000"
            assert rc.total_out == "8990000"


def test_jup_fmt_uses_price_impact_points():    from bot import jup
    line = jup.fmt_quote({"outAmount": "7", "priceImpact": -0.1,
                          "route": [(100, "X")]}, "sell")
    assert "-0.1%" in line and "priceImpactPct" not in line


def test_signals_entry_parity():
    import numpy as np
    from bot import signals as S
    from bot.strategy import run_selective
    up = list(1.0 * (1.01) ** np.arange(60))
    take, feat = S.decide_entry(up, ["buy"] * 60, [50.0] * 60)
    assert take and feat is not None
    r, why, _ = run_selective(up, ["buy"] * 60, liq_series=[50.0] * 60)
    assert r != 0.0 and why not in ("filtered", "too-short", "bad-tick")
    flat = [1.0] * 60
    take2, _ = S.decide_entry(flat, ["sell"] * 60, [50.0] * 60)
    assert not take2
    take3, _ = S.decide_entry(up, ["buy"] * 60, [5.0] * 60)
    assert not take3  # thin pool rejected like paper's liq gate


def test_signals_exit_order():
    from bot import signals as S
    assert S.decide_exit(1.0, 1.5, 0.85, 60.0) == "stop"
    assert S.decide_exit(1.0, 1.5, 1.20, 60.0) == "trail"
    assert S.decide_exit(1.0, 1.5, 1.70, 60.0) == "take"
    assert S.decide_exit(1.0, 1.1, 1.10, 9999.0) == "hold-end"
    assert S.decide_exit(1.0, 1.1, 1.10, 60.0) is None
    assert S.decide_exit(0.0, 0.0, 0.0, 0.0) is None
    # stop wins over trail when both trigger
    assert S.decide_exit(1.0, 3.0, 0.80, 60.0) == "stop"


def test_noquote_is_skip_not_error():
    import os
    from unittest.mock import patch
    from bot import live
    assert issubclass(live.NoQuote, RuntimeError)

    class _Bad:
        ok = False
        status_code = 400
        text = "No routes found"

    class _Empty:
        ok = True

        def json(self):
            return {"routePlan": [], "router": "metis"}  # no outAmount

    with patch.dict(os.environ, {"JUPITER_API_KEY": "x"}):
        with patch("bot.live.requests.get", return_value=_Bad()):
            try:
                live.get_order("A", "B", 100, "T")
                raise SystemExit("must raise NoQuote")
            except live.NoQuote:
                pass
        with patch("bot.live.requests.get", return_value=_Empty()):
            try:
                live.get_order("A", "B", 100, "T")
                raise SystemExit("must raise NoQuote")
            except live.NoQuote:
                pass


def test_live_order_param_plumbing():
    import os
    from unittest.mock import patch
    from bot import live

    class _R:
        ok = True

        def json(self):
            return {"outAmount": "1", "routePlan": []}

    with patch.dict(os.environ, {"JUPITER_API_KEY": "x"}):
        with patch("bot.live.requests.get", return_value=_R()) as g:
            live.get_order("A", "B", 100, "T", slippage_bps="auto",
                           jito_tip_lamports=0)
            _, kw = g.call_args
            assert "slippageBps" not in kw["params"], kw
            assert "jitoTipLamports" not in kw["params"], kw
        with patch("bot.live.requests.get", return_value=_R()) as g:
            live.get_order("A", "B", 100, "T", slippage_bps=100,
                           jito_tip_lamports=1000)
            _, kw = g.call_args
            assert kw["params"]["slippageBps"] == "100", kw
            assert kw["params"]["jitoTipLamports"] == "1000", kw


def test_live_refuses_v1():
    from bot import live
    o = _live_order(transactionVersion=1)
    ok, why = live.check_guards(o, "TAKER", 1.0)
    assert not ok and "v1" in why, why
    o = _live_order(transactionVersion=0)
    ok, _ = live.check_guards(o, "TAKER", 1.0)
    assert ok


def test_live_key_names():
    import os
    from unittest.mock import patch
    from bot import live
    # neither name -> clear error (no network touched)
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("BS58_PRIVATE_KEY", None)
        os.environ.pop("PRIVATE_KEY", None)
        try:
            live._load_keypair()
            raise SystemExit("must raise")
        except RuntimeError as e:
            assert "BS58_PRIVATE_KEY" in str(e) and "PRIVATE_KEY" in str(e)
    # .env.signer name wins when both present (no network touched)
    from solders.keypair import Keypair
    B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

    def _b58(raw: bytes) -> str:
        n = int.from_bytes(raw, "big")
        s = ""
        while n > 0:
            n, r = divmod(n, 58)
            s = B58[r] + s
        return s or B58[0]

    raw = bytes(Keypair())
    with patch.dict(os.environ, {"BS58_PRIVATE_KEY": _b58(raw),
                                 "PRIVATE_KEY": "bogus-not-valid"}):
        kp = live._load_keypair()
        assert str(kp.pubkey()) == str(Keypair.from_bytes(raw).pubkey())
