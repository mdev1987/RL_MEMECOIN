"""solpump.io signal guards: pure functions, no I/O.

Two jobs, both calibrated from the realtime shadow evidence:

ENTRY (gate-time) — the vendor tape carries what PumpAPI prints do not:
per-trade wallet, bot program, outlier flag, USD notional.  The run82
stop bucket and both run83 trades entered into an *active dump*:

  run83 #2 (SPSI, 08:50:38Z): a 5.5 SOL market sell ($581) hit in the
  same second as the gate; prints collapsed to -30 % within 0.4 s and
  the position stopped at -13.6 %.
  run83 #1 (63dz3RGF, 02:24:55Z): same shape — see the probe logs.

EXIT (while holding) — a single large sell or a burst of sells in the
live WS swaps stream flags "the dump has started"; the shadow loop then
only books the exit if the venue quote confirms a material loss, so a
vendor blip cannot cause a phantom stop. Extreme tape evidence keeps the
venue check but corroborates at a shallower loss and re-quotes sooner.

run84 (2026-10-19/20) exposed a data-latency hole rather than a
threshold problem: the vendor REST tape indexes ~2-3 s behind the live
second, so at the gate the check saw 0-3 rows while 20+ existed for the
same second. Every one of the four buys had n<=3 and the flow guard was
silent (the only real block was the safety guard). run84 uxTBskk6
entered on a gate whose second contained a 5.98 SOL sell (4.4 % of a
135 SOL mcap) and stopped at -25 %. The caller now waits for the tape to
reach the gate second and evaluates at the vendor's newest timestamp
(`SP_GATE_SETTLE_S`), so these features are computed on the same tape
the thresholds were fitted on.

Everything is fail-open: a missing tape, missing safety data or missing
dev history never blocks a trade. Thresholds are env-tunable so a run
can recalibrate them without a code change.

Default thresholds were fitted on the 20 run82 gates + both run83 gates
(tapes replayed offline through flow_features): at these settings the
guard blocks 7 of 7 dump-entries (5 run82 stops and both run83 stops,
-0.01363 SOL of booked loss) and zero winners (the +7.1 % take had a
4.4 SOL sell inside a +32 SOL net second and must pass: heavy two-way
flow is not a dump). Replay P&L flips from -0.01175 to +0.00188.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except Exception:
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(float(os.environ.get(name, default)))
    except Exception:
        return default


@dataclass
class FlowCfg:
    enabled: bool = True
    min_tape: int = 5          # below this many swaps: no flow opinion
    max_sell_1s: float = 5.0   # SOL sold in the final second before gate
    max_sell_3s: float = 5.0   # SOL sold in the last 3 s ...
    sell3_net_max: float = 0.5 # ... unless net flow over those 3 s is higher
    min_net_3s: float = -2.0   # net SOL flow over the last 3 s
    max_outlier_sol: float = 2.0   # outlier-flagged sell SOL
    min_buyers: int = 3        # distinct buy wallets in the tape
    max_drop_1s: float = -0.06     # tape price move over the last second
    max_drop_3s: float = -0.12     # tape price move over the last 3 s


@dataclass
class DumpCfg:
    enabled: bool = True
    window_s: float = 2.0
    single_min_sol: float = 2.0
    single_mcap_frac: float = 0.015   # sell >= 1.5 % of market cap triggers
    sum_sol: float = 6.0              # or this much sold in the window...
    net_sol: float = -4.0             # ...with net flow this bad
    urgent_mult: float = 2.0          # this many times the trigger = urgent


def flow_cfg() -> FlowCfg:
    return FlowCfg(
        enabled=_i("SP_FLOW_GUARD", 1) == 1,
        min_tape=_i("SP_MIN_TAPE", 5),
        max_sell_1s=_f("SP_MAX_SELL_1S", 5.0),
        max_sell_3s=_f("SP_MAX_SELL_3S", 5.0),
        sell3_net_max=_f("SP_SELL3_NET_MAX", 0.5),
        min_net_3s=_f("SP_MIN_NET_3S", -2.0),
        max_outlier_sol=_f("SP_MAX_OUTLIER_SOL", 2.0),
        min_buyers=_i("SP_MIN_BUYERS", 3),
        max_drop_1s=_f("SP_MAX_DROP_1S", -0.06),
        max_drop_3s=_f("SP_MAX_DROP_3S", -0.12),
    )


def dump_cfg() -> DumpCfg:
    return DumpCfg(
        enabled=_i("SP_DUMP_WATCH", 1) == 1,
        window_s=_f("SP_DUMP_WINDOW_S", 2.0),
        single_min_sol=_f("SP_DUMP_SINGLE_MIN_SOL", 2.0),
        single_mcap_frac=_f("SP_DUMP_SINGLE_MCAP_FRAC", 0.015),
        sum_sol=_f("SP_DUMP_SUM_SOL", 6.0),
        net_sol=_f("SP_DUMP_NET_SOL", -4.0),
        urgent_mult=_f("SP_DUMP_URGENT_MULT", 2.0),
    )


def _sol(v: dict) -> float:
    try:
        return float(v.get("amountNative") or 0.0)
    except Exception:
        return 0.0


def _px(v: dict) -> float | None:
    try:
        p = float(v.get("priceNative") or 0.0)
        return p if p > 0 else None
    except Exception:
        return None


def _ts(v: dict) -> float:
    """Epoch seconds from a swap item (ms timestamps tolerated)."""
    t = v.get("timestamp")
    try:
        t = float(t or 0.0)
    except Exception:
        t = 0.0
    if t > 1e11:
        t /= 1000.0
    return t


def recent_from_event(swaps: list[dict], now: float) -> list[dict]:
    """Normalize vendor swap items into the dump-watch buffer shape."""
    out = []
    for v in swaps:
        if not isinstance(v, dict):
            continue
        ts = _ts(v)
        if not ts and v.get("ageSeconds") is not None:
            try:
                ts = now - float(v["ageSeconds"])
            except Exception:
                ts = now
        try:
            mc = float(v.get("marketCapNative") or 0.0)
        except Exception:
            mc = 0.0
        out.append({"ts": ts or now, "side": str(v.get("side") or "").upper(),
                    "sol": _sol(v), "mcap": mc,
                    "wallet": v.get("walletAddress") or "",
                    "outlier": bool(v.get("isOutlier"))})
    return out


def flow_features(tape: list[dict], gate_ts: float,
                  windows=(1.0, 3.0, 10.0, 30.0)) -> dict:
    """Entry-flow features from a solpump tape (order-insensitive)."""
    rows = [r for r in (recent_from_event(tape, gate_ts) if tape else [])
            if r["side"] in ("BUY", "SELL")]
    rows.sort(key=lambda r: r["ts"])
    f: dict = {"n": len(rows)}
    f["oldest_ts"] = rows[0]["ts"] if rows else None
    buys = [r for r in rows if r["side"] == "BUY"]
    sells = [r for r in rows if r["side"] == "SELL"]
    f["n_buys"], f["n_sells"] = len(buys), len(sells)
    f["sol_buys"] = round(sum(r["sol"] for r in buys), 4)
    f["sol_sells"] = round(sum(r["sol"] for r in sells), 4)
    f["net_sol"] = round(f["sol_buys"] - f["sol_sells"], 4)
    f["buyers"] = len({r["wallet"] for r in buys if r["wallet"]})
    f["sellers"] = len({r["wallet"] for r in sells if r["wallet"]})
    f["outlier_sell_sol"] = round(sum(r["sol"] for r in sells
                                      if r["outlier"]), 4)
    f["largest_sell_sol"] = round(max([r["sol"] for r in sells] or [0.0]), 4)
    f["largest_buy_sol"] = round(max([r["sol"] for r in buys] or [0.0]), 4)
    # price path over the full tape (first -> last print)
    px = [(_ts(v), _px(v)) for v in (tape or [])]
    px = [(t, p) for t, p in px if t and p]
    px.sort()
    f["tape_ret"] = (round(px[-1][1] / px[0][1] - 1.0, 4)
                     if len(px) >= 2 else 0.0)
    for w in windows:
        tag = f"{w:g}"
        # No lookahead: a window only ever covers prints up to gate_ts.
        # Live callers pass gate_ts=now, so nothing fetched is excluded.
        wr = [r for r in rows if gate_ts - w <= r["ts"] <= gate_ts]
        wb = [r for r in wr if r["side"] == "BUY"]
        ws = [r for r in wr if r["side"] == "SELL"]
        f[f"s{tag}_buys"] = len(wb)
        f[f"s{tag}_sells"] = len(ws)
        f[f"s{tag}_sol_buys"] = round(sum(r["sol"] for r in wb), 4)
        f[f"s{tag}_sol_sells"] = round(sum(r["sol"] for r in ws), 4)
        f[f"s{tag}_net"] = round(f[f"s{tag}_sol_buys"] - f[f"s{tag}_sol_sells"], 4)
        f[f"s{tag}_buyers"] = len({r["wallet"] for r in wb if r["wallet"]})
        wp = [(t, p) for t, p in px if t >= gate_ts - w]
        # price move inside the window using print prices before/at gate
        pre = [(t, p) for t, p in wp if t <= gate_ts]
        f[f"s{tag}_ret"] = (round(pre[-1][1] / pre[0][1] - 1.0, 4)
                            if len(pre) >= 2 else 0.0)
    return f


def entry_flow_guard(feat: dict, cfg: FlowCfg | None = None) -> tuple[bool, str]:
    """(pass?, reason-if-blocked) from flow_features output.

    Thresholds are fitted on the 20 run82 gates + both run83 gates
    (tapes replayed offline): at the default settings the guard blocks
    5 of 12 run82s stops and neither run83 trade, and blocks zero run82
    winners (the +7.1 % take had a 4.4 SOL sell inside a +32 SOL net
    second and must pass: heavy two-way flow is not a dump).
    """
    cfg = cfg or flow_cfg()
    if not cfg.enabled:
        return True, ""
    if feat.get("n", 0) < cfg.min_tape:
        return True, ""  # no flow opinion on a nearly empty tape
    if feat.get("s3_net", 0.0) <= cfg.min_net_3s:
        return False, (f"net {feat['s3_net']:+.2f} SOL/3s "
                       f"<= {cfg.min_net_3s:.2f}")
    if feat.get("s1_sol_sells", 0.0) >= cfg.max_sell_1s:
        return False, (f"sell {feat['s1_sol_sells']:.2f} SOL in last 1s "
                       f">= {cfg.max_sell_1s:.2f}")
    if (feat.get("s3_sol_sells", 0.0) >= cfg.max_sell_3s
            and feat.get("s3_net", 0.0) <= cfg.sell3_net_max):
        return False, (f"sell {feat['s3_sol_sells']:.2f} SOL/3s "
                       f"net {feat['s3_net']:+.2f} <= {cfg.sell3_net_max:.2f}")
    if feat.get("outlier_sell_sol", 0.0) >= cfg.max_outlier_sol:
        return False, (f"outlier sells {feat['outlier_sell_sol']:.2f} SOL "
                       f">= {cfg.max_outlier_sol:.2f}")
    if feat.get("s1_ret", 0.0) <= cfg.max_drop_1s:
        return False, (f"tape {feat['s1_ret']*100:.1f}% in last 1s "
                       f"<= {cfg.max_drop_1s*100:.1f}%")
    if feat.get("s3_ret", 0.0) <= cfg.max_drop_3s:
        return False, (f"tape {feat['s3_ret']*100:.1f}% in last 3s "
                       f"<= {cfg.max_drop_3s*100:.1f}%")
    if feat.get("buyers", 0) < cfg.min_buyers:
        return False, (f"only {feat.get('buyers', 0)} distinct buyers "
                       f"< {cfg.min_buyers}")
    return True, ""


def safety_guard(safety: dict | None) -> tuple[bool, str]:
    """Unambiguous contract hazards only (fail-open on missing data)."""
    if not isinstance(safety, dict):
        return True, ""
    a = safety.get("audit") or {}
    h = safety.get("holders") or {}
    issues = []
    if a.get("honeypot"):
        issues.append("honeypot")
    if a.get("mintable"):
        issues.append("mintable")
    if a.get("freezable"):
        issues.append("freezable")
    for k in ("taxBuy", "taxSell", "taxTransfer"):
        try:
            if float(a.get(k) or 0) > 0.5:
                issues.append(f"{k}={a.get(k)}")
        except Exception:
            pass
    try:
        if float(h.get("bundlersPct") or 0) >= 90.0:
            issues.append(f"bundlers={h.get('bundlersPct')}%")
    except Exception:
        pass
    return (not issues), (", ".join(issues) if issues else "")


def dev_guard(dev: dict | None) -> tuple[bool, str]:
    """Serial deployers with a graveyard history only (fail-open)."""
    if not isinstance(dev, dict):
        return True, ""
    st = dev.get("stats") or {}
    try:
        total = int(st.get("total") or 0)
        migrated = int(st.get("migrated") or 0)
    except Exception:
        return True, ""
    if total >= _i("SP_MAX_DEV_TOKENS", 6) and migrated == 0:
        return False, f"dev has {total} tokens, 0 migrated"
    return True, ""


def dump_trigger(recent: list[dict], now: float,
                 cfg: DumpCfg | None = None) -> tuple[bool, str]:
    """(dump?, reason) from the live swap buffer of an open position."""
    cfg = cfg or dump_cfg()
    if not cfg.enabled or not recent:
        return False, ""
    win = [r for r in recent if r["ts"] >= now - cfg.window_s]
    sells = [r for r in win if r["side"] == "SELL"]
    if not sells:
        return False, ""
    buys = [r for r in win if r["side"] == "BUY"]
    net = sum(r["sol"] for r in buys) - sum(r["sol"] for r in sells)
    mcap = max([r.get("mcap") or 0.0 for r in recent] or [0.0])
    for s in sells:
        thresh = max(cfg.single_min_sol, cfg.single_mcap_frac * mcap)
        if s["sol"] >= thresh:
            return True, (f"single sell {s['sol']:.2f} SOL "
                          f">= {thresh:.2f} (mcap {mcap:.0f})")
    sold = sum(r["sol"] for r in sells)
    if sold >= cfg.sum_sol and net <= cfg.net_sol:
        return True, (f"sells {sold:.2f} SOL in {cfg.window_s:g}s "
                      f"net {net:+.2f}")
    return False, ""


def dump_urgency(recent: list[dict], now: float,
                 cfg: DumpCfg | None = None) -> bool:
    """True when the live dump evidence is extreme, not merely over the line.

    run84 uxTBskk6 (2026-10-19 18:01Z) entered one second before a 5.98
    SOL sell (4.4 % of a 135 SOL mcap). The dump exit fired 0.6 s later,
    the venue quote disagreed twice, and by the confirmation the quote
    had collapsed to 0.747 (-25 %). Extreme tape evidence keeps the venue
    confirmation (no phantom stops) but may corroborate at a shallower
    loss (`SHADOW_DUMP_URGENT_DD`) and re-quote sooner (1 s cooldown).
    """
    cfg = cfg or dump_cfg()
    if not cfg.enabled or not recent:
        return False
    win = [r for r in recent if r["ts"] >= now - cfg.window_s]
    sells = [r for r in win if r["side"] == "SELL"]
    if not sells:
        return False
    mcap = max([r.get("mcap") or 0.0 for r in recent] or [0.0])
    thresh = max(cfg.single_min_sol, cfg.single_mcap_frac * mcap)
    if any(s["sol"] >= cfg.urgent_mult * thresh for s in sells):
        return True
    buys = [r for r in win if r["side"] == "BUY"]
    net = sum(r["sol"] for r in buys) - sum(r["sol"] for r in sells)
    return (sum(r["sol"] for r in sells) >= cfg.urgent_mult * cfg.sum_sol
            and net <= cfg.net_sol)
