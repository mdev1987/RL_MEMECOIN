"""Realtime shadow trader: live market signals, signed-never-sent fills.

Live PumpAPI ticks -> v3 entry gate (shared signals.decide_entry) ->
SHADOW Jupiter order (full /order + guards + local sign, NEVER executes)
-> paper positions tracked on live marks -> shared exit rule ->
shadow ledger + Telegram cards (via="shadow").

Entries are birth-anchored: the v3 gate reads the FIRST 11 prints of a
mint's life, so a tape only starts for mints whose `create` event we
saw, once per mint. Without this, a first-seen print deep in a mint's
life makes an arbitrary mid-life window look like "early" (postmortem
2026-10-17: 21/23 live entries fired 3-3522 prints late and bought
micro-burst tops; stops in 9-275 s).

No real orders in any configuration: place_order is always called with
shadow=True, and LIVE_TRADING is never consulted. The funded wallet only
pays nothing; the key signs locally for parity measurement.

Usage: .venv/bin/python -m bot.shadow_loop [--secs 1800]
Deposits: data/shadow_wallet.json, data/shadow_decisions.jsonl
"""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

from bot.replay_eval import is_pump_pool
from bot.wallet import Wallet
from bot.ledger import append as ledger_append, row as ledger_row
from bot.jup import (order_quote, order_quote_ex, price_deviation,
                     roundtrip_cost_pct, token_decimals, SOL, LAMPORTS)
from bot import live as L
from bot import signals as S
from bot import solpump as SP
from bot import sp_guards as SPG
from notifier import get_notifier

log = logging.getLogger("shadow_loop")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

REPO = Path(__file__).resolve().parents[1]
URL = "wss://stream.pumpapi.io"
SIZE_SOL = float(os.environ.get("SHADOW_SIZE_SOL", "0.01"))
# Shadow fills go through the live executor's guards (LIVE_MAX_SOL cap);
# keep the default at dust scale so signals never trip the cap.
MAXOPEN = int(os.environ.get("SHADOW_MAXOPEN", "2"))
ENTRY_N = 11  # need entry_lookback+1 buys before the gate can run
# Entry data-quality guards (run82 postmortem). The retired /order
# priceImpact cap was uncorrelated with outcome; these two measure the
# things that actually cost money on a fresh mint:
#   deviation: tape print vs venue quote at the gate (normal 1.2-1.6 %,
#              stale-tape entry 17.4 % -> -20 % in 3 s)
#   round trip: immediate sell-back cost of the quoted buy (thin pools
#              are exactly the ones whose stops gap through -12 %)
MAX_DEVIATION = float(os.environ.get("LIVE_MAX_DEVIATION_PCT", "5.0")) / 100.0
MAX_ROUNDTRIP = float(os.environ.get("LIVE_MAX_ROUNDTRIP_PCT", "8.0"))
# A tape trigger the venue does not corroborate is vetoed; cool down so
# one persistently mis-scaled tape cannot storm the quote API.
VETO_COOL_S = float(os.environ.get("SHADOW_VETO_COOL_S", "5.0"))
# solpump.io data layer (goal 2026-10-19 "profitable with all ws/api from
# solpump.io"): at every v3 signal the vendor tape/safety/dev history are
# read before a venue quote is spent; while holding, the live WS swaps
# stream arms a dump exit that still needs venue corroboration (a
# SHADOW_DUMP_EXIT_DD loss) before anything is booked.
SP_ENABLED = SP.enabled()
DUMP_DD = float(os.environ.get("SHADOW_DUMP_EXIT_DD", "0.05"))
# Extreme vendor dump evidence: still venue-confirmed, but corroborate at
# a shallower loss and re-quote sooner (run84 uxTBskk6 lost 25 % while the
# venue quote lagged the tape dump by ~10 s).
DUMP_URGENT_DD = float(os.environ.get("SHADOW_DUMP_URGENT_DD", "0.03"))
DUMP_VETO_COOL_S = float(os.environ.get("SHADOW_DUMP_VETO_COOL_S", "1.0"))
# The vendor REST tape indexes ~2-3 s behind the live second (measured
# 2026-10-20: newest row aged 1.6-3.9 s on a hot mint). At the gate the
# check used to read 0-3 rows while 20+ existed for that second, so the
# entry guard failed open on exactly the dump entries it was fitted to
# block. Wait for the tape to reach the gate second (bounded).
SP_SETTLE_S = float(os.environ.get("SP_GATE_SETTLE_S", "4.0"))
SP_SETTLE_POLL_S = float(os.environ.get("SP_GATE_SETTLE_POLL_S", "0.4"))
SP_TAPE_STALE_S = float(os.environ.get("SP_GATE_STALE_S", "10.0"))
# Liveness: run82 had no heartbeat, so a dead stream looked like a quiet
# market. Log counters every 5 min; warn at 60 s of total silence and
# fail the run at 10 min (a half-open socket must not fake a 24 h run).
HEARTBEAT_S = float(os.environ.get("SHADOW_HEARTBEAT_S", "300"))
SILENT_WARN_S = float(os.environ.get("SHADOW_SILENT_WARN_S", "60"))
SILENT_EXIT_S = float(os.environ.get("SHADOW_SILENT_EXIT_S", "600"))
PRUNE_S = 60.0
IDLE_DROP_S = 1800.0
MAX_MINTS = 5000
CREATES_TTL_S = 3600.0  # birth anchors: only useful until first prints
TAPED_CAP = 1_000_000   # one-shot registry soft cap (clear + warn)
WALLET = str(REPO / "data" / "shadow_wallet.json")
LEDGER = str(REPO / "data" / "shadow_decisions.jsonl")


def sweep_due(p: dict, now: float, time_s: float = 3600.0,
              stale_s: float = 600.0) -> str | None:
    """Flow-independent exit check. Returns 'hold-end'/'stale'/None."""
    age = now - p["t"]
    idle = now - p.get("last_ts", p["t"] * 1000) / 1000
    if age > time_s:
        return "hold-end"
    if idle > stale_s:
        return "stale"
    return None


MARK_HI = 10.0   # mark/cost above this is suspect without venue agreement
MARK_LO = 0.1


def quote_fill_sol(q: dict | None) -> float | None:
    """SOL value of a read-only sell quote, or None."""
    if not q or not q.get("outAmount"):
        return None
    try:
        v = int(q["outAmount"]) / LAMPORTS
    except Exception:
        return None
    return v if v > 0 else None


OURS_MARKERS = ("order error", "HTTP 401", "HTTP 403", "HTTP 429",
                "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504")
VENUE_MARKERS = ("HTTP 400", "no quote")


def venue_exit_reason(why: str, size: float, peak: float, fill: float,
                      age_s: float, urgent: bool = False) -> str | None:
    """Venue-confirmed exit: the executable quote has the final say.

    Shadow marks are tape prints, but a sell only ever gets the venue
    quote (run82: two tape-blip "stops" filled at -2.7 %/-3.5 % while
    the venue was fine). Re-evaluate stop/trail/take on the quote that
    would actually fill; time-based exits (hold-end/stale/rug) are not
    price triggers and are never vetoed. Returns the reason to book, or
    None to keep holding.
    """
    if why == "dump":
        # the vendor tape flagged an active dump while holding; the venue
        # quote must corroborate a material loss or we keep holding.
        # Extreme tape evidence (>= urgent_mult x the trigger) corroborates
        # at a shallower loss: run84 uxTBskk6's venue quote sat at 1.01
        # for 10 s after a 4.4 %-of-mcap sell, then gapped to 0.747.
        dd = DUMP_URGENT_DD if urgent else DUMP_DD
        return "dump" if fill <= size * (1.0 - dd) else None
    if why not in ("stop", "trail", "take"):
        return why
    return S.decide_exit(size, peak, fill, age_s)


def quote_failure_kind(qerr: str) -> str:
    """'ours' (network/auth/quota) | 'venue' (no route) | 'other'.

    Only 'venue' may count toward rug-give-up: seen live 2026-10-17, the
    venue build path failed ("Insufficient funds": a shadow wallet never
    takes delivery) while the mint quoted fine — those are OUR artifacts,
    never proof the position is worthless.
    """
    if any(x in qerr for x in OURS_MARKERS):
        return "ours"
    if any(x in qerr for x in VENUE_MARKERS):
        return "venue"
    return "other"


def mark_suspect(mark: float, size: float) -> bool:
    """True when a tape mark is implausibly far from cost basis.

    A single print can be mis-scaled (seen live: a 337x split between
    the tape price and what the venue would actually pay). Such marks
    must never update peak or trigger exits on their own.
    """
    if size <= 0 or mark <= 0:
        return True
    r = mark / size
    return r > MARK_HI or r < MARK_LO


def tradable_event(e: dict) -> bool:
    """True only for SOL-quoted pump events (the validated universe).

    replay/OOS paths (`load_paths`) only ever contain quoteMint==SOL
    pairs. Pump now also launches pairs quoted in USDC or other meme
    tokens: their tape prices are in quote-asset units, the v3 liq
    filter is SOL-denominated, and the SOL venue route cannot act on
    them anyway. Seen live (run81): 8 of 11 birth-window gate passes
    were such pairs, all ghost-skipped at the venue cross-check.
    """
    return (e.get("quoteMint") == SOL
            and is_pump_pool({"pool": e.get("pool"),
                              "protocol": e.get("protocol")}))


def tape_should_start(m: str, creates: dict, taped: set) -> bool:
    """True only for a mint whose birth we saw and have never taped.

    The v3 entry gate reads the FIRST 11 prints of a mint's life. That
    window only exists if the mint's `create` event arrived while we
    were connected — otherwise the "early" window is an arbitrary
    mid-life slice (postmortem 2026-10-17: 21 of 23 live shadow entries
    fired 3-3522 prints late and bought micro-burst tops; stop-outs in
    9-275 s; the missed birth window of one mint ran +3966%). One tape
    per mint, ever.
    """
    return m in creates and m not in taped


def new_tape(mint: str, ts: int):
    return {"mint": mint, "t0": ts, "prices": [], "acts": [],
            "liq": [], "buyers": [], "sells": 0, "last_ts": ts,
            "done": False}


def push_print(t: dict, px: float, act: str, liq: float,
               signer: str | None = None, entry_n: int = ENTRY_N) -> bool:
    """Append one print to a fresh tape; True exactly once, on the print
    that completes the entry window (the gate event).

    After the window the tape is done and stops growing. Seen live: with
    positions open at MAXOPEN for an hour, tapes never reached "done"
    and their print arrays grew without bound until the process was
    OOM-killed mid-run.
    """
    if t["done"]:
        return False
    t["prices"].append(px)
    t["acts"].append(act)
    t["liq"].append(liq)
    if act == "buy":
        if signer and signer not in t["buyers"]:
            t["buyers"].append(signer)
    else:
        t["sells"] += 1
    if len(t["prices"]) >= entry_n:
        t["done"] = True
        return True
    return False


def tape_newest(tape: list[dict] | None) -> float:
    """Newest vendor swap timestamp (epoch s), 0 when empty."""
    now = time.time()
    return max((SP.swap_ts(v, now) for v in (tape or [])), default=0.0)


def sp_gate_check(mint: str, birth_ms: int,
                  gate_ts: float | None = None) -> tuple[bool, str, dict]:
    """solpump.io gate: tape flow + safety + dev history (fail-open).

    Called at every v3 signal through asyncio.to_thread (requests is
    synchronous). Pulls the vendor tape back to the mint's birth anchor,
    computes flow features as of the gate second, then checks the
    unambiguous contract hazards. A missing tape/safety/dev (vendor down,
    brand-new mint) never blocks: v3 still decides.

    The vendor REST tape indexes ~2-3 s behind the live second, so a
    gate-time read used to see 0-3 rows while 20+ existed for that same
    second (run84: every one of the 4 buys had n<=3, and the guard was
    silent; uxTBskk6's 5.98 SOL dump sell was stamped in the gate second
    but invisible). Wait for the tape to reach the gate second (bounded),
    then evaluate at the vendor's newest timestamp instead of wall now —
    otherwise the lag leaves the final 1 s window empty and the dump is
    invisible again.
    """
    gate_ts = gate_ts or time.time()
    floor = (birth_ms / 1000.0) - 5.0 if birth_ms else gate_ts - 120.0
    tape = SP.swaps_since(mint, floor, max_pages=4) or []
    cfg = SPG.flow_cfg()
    t0 = time.time()
    newest = tape_newest(tape)
    if cfg.enabled and SP_SETTLE_S > 0:
        while (newest < gate_ts - 0.5
               and time.time() - t0 < SP_SETTLE_S):
            time.sleep(SP_SETTLE_POLL_S)
            more = SP.swaps_since(mint, floor, max_pages=4)
            if more:
                tape = more
            newest = tape_newest(tape)
    wait_s = round(time.time() - t0, 2)
    now = time.time()
    if not newest or newest < gate_ts - SP_TAPE_STALE_S:
        feat: dict = {"n": 0}  # vendor lagging/absent: no flow opinion
    else:
        eval_ts = min(max(gate_ts, newest), now)
        rows = [v for v in tape if SP.swap_ts(v, now) <= eval_ts]
        feat = SPG.flow_features(rows, eval_ts)
    feat["wait_s"] = wait_s
    feat["tape_age"] = round(now - newest, 2) if newest else None
    ok, why = SPG.entry_flow_guard(feat, cfg)
    if ok:
        ok, why = SPG.safety_guard(SP.safety(mint))
    if ok:
        ok, why = SPG.dev_guard(SP.dev_tokens(mint))
    return ok, why, feat


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=0.0,
                    help="bounded run seconds (0 = forever)")
    a = ap.parse_args()
    import websockets
    ntf = get_notifier()
    hk = os.environ.get("HELIUS_API_KEY", "")
    try:
        taker = str(L._load_keypair().pubkey())
    except Exception as exc:
        log.error("shadow needs a signing key: %s", exc)
        raise SystemExit(f"shadow needs key: {exc}")
    w = Wallet(path=WALLET, start=1.0, daily_stop=0.10, dd_stop=0.30,
               max_pos=SIZE_SOL)
    ntf.send_startup(f"🕶️ Shadow mode • size {SIZE_SOL:g} SOL • taker {taker[:8]} • "
                     f"live market, signed-never-sent")
    log.info("shadow active taker=%s size=%s", taker[:8], SIZE_SOL)
    mints: dict[str, dict] = {}
    poss: dict[str, dict] = {}
    creates: dict[str, int] = {}
    taped: set[str] = set()
    t_end = time.time() + a.secs if a.secs > 0 else float("inf")
    last_prune = time.time()
    last_full_warn = 0.0
    sp_feed = None  # solpump.io live WS feed (goal 2026-10-19)

    def close_position(mint: str, why: str, mark: float) -> None:
        if why == "rug":
            # Unclosable exit (no venue quotes the mint): zero realizable
            # value. NEVER the last print, which may be stale-high and
            # would book fantasy profit (seen live: +491x on a corpse).
            mark = 0.0
        p = poss.pop(mint)
        mints.pop(mint, None)  # window is over: tape is moot after close
        if sp_feed is not None:
            for ch in ("swaps", "price", "chart_markers"):
                sp_feed.unsubscribe(f"token:{SP.QUOTE}:{mint}:{ch}")
        pnl = mark - p["size"]
        halted = w.apply_close(mint, pnl)
        ledger_append(LEDGER, ledger_row(
            file="live", mint=mint, reason="shadow-" + why,
            r_net=pnl / p["size"], pnl_sol=pnl,
            balance_after=w.s.balance, wins=w.s.wins, losses=w.s.losses))
        total = w.s.wins + w.s.losses
        ntf.send_close(
            ca=mint, name=mint[:12],
            reason="TP" if why == "take" else ("STOP" if why == "stop"
                    else ("TRAIL" if why == "trail"
                          else ("DUMP" if why == "dump"
                                else ("RUG" if why == "rug" else "TIME")))),
            mult=mark / p["size"] if p["size"] > 0 else 1.0,
            pnl_sol=pnl, hold_s=time.time() - p["t"],
            entry_px=p.get("entry_px"), exit_px=mark, size_sol=p["size"],
            balance_before=w.s.balance - pnl, balance_after=w.s.balance,
            win_rate=100.0 * w.s.wins / total if total else 0.0,
            dex="jupiter", via="shadow")
        log.info("SHADOW SELL %s %s pnl=%+.5f bal=%.4f halted=%s",
                 mint[:8], why, pnl, w.s.balance, halted)

    async def run():
        nonlocal last_prune, last_full_warn, sp_feed
        t0 = time.time()
        hb_t = t0
        last_msg = t0
        silent_warned = False
        st = {"prints": 0, "creates": 0, "gates": 0, "buys": 0}

        def on_sp_event(topic: str, event: str, data, meta) -> None:
            """solpump.io WS -> open positions: tape buffer + dump watch."""
            parts = topic.split(":")
            if len(parts) < 4 or parts[0] != "token":
                return
            p = poss.get(parts[2])
            if p is None:
                return
            if parts[3] == "swaps":
                rows = SPG.recent_from_event(SP.swaps_from_event(data),
                                             time.time())
                if rows:
                    buf = p.setdefault("sp_recent", [])
                    buf.extend(rows)
                    if len(buf) > 400:
                        del buf[:-400]
                    st["sp_swaps"] = st.get("sp_swaps", 0) + len(rows)
                    hit, dw = SPG.dump_trigger(buf, time.time())
                    if hit and not p.get("dump"):
                        p["dump"] = True
                        p["dump_why"] = dw
                        p["dump_urgent"] = SPG.dump_urgency(buf, time.time())
                        st["sp_dumps"] = st.get("sp_dumps", 0) + 1
                        log.info("SHADOW sp-dump %s %s%s", parts[2][:8], dw,
                                 " [urgent]" if p["dump_urgent"] else "")
            elif parts[3] == "price":
                px = SP.price_from_event(data)
                if px:
                    p["sp_px"] = px
            elif parts[3] == "chart_markers":
                st["sp_markers"] = st.get("sp_markers", 0) + 1
                log.info("SHADOW sp-marker %s %s", parts[2][:8],
                         json.dumps(data)[:200])

        if SP_ENABLED:
            sp_feed = SP.Feed(on_sp_event)
            sp_feed.start()
            fe = await asyncio.to_thread(SP.fee_estimate, "SOL", "MEDIUM")
            log.info("SHADOW solpump on: feed=%s fee=%s", sp_feed.status(),
                     json.dumps(fe)[:240] if fe else "n/a")
        async with websockets.connect(URL, max_size=50_000_000) as ws:
            log.info("shadow stream connected")
            while time.time() < t_end:
                now = time.time()
                if now - hb_t >= HEARTBEAT_S:
                    hb_t = now
                    log.info("SHADOW heartbeat prints=%d creates=%d sig=%d "
                             "gates=%d buys=%d sp_block=%d sp_swaps=%d "
                             "sp_dumps=%d ws=%s open=%d mints=%d uptime=%.1fh",
                             st["prints"], st["creates"], st.get("sig", 0),
                             st["gates"], st["buys"], st.get("sp_skips", 0),
                             st.get("sp_swaps", 0), st.get("sp_dumps", 0),
                             (sp_feed.status() if sp_feed else "off"),
                             len(poss), len(mints), (now - t0) / 3600.0)
                silent = now - last_msg
                if silent > SILENT_EXIT_S:
                    raise RuntimeError(
                        f"stream silent for {silent:.0f}s (no frames) — "
                        "half-open socket, ending run")
                if silent > SILENT_WARN_S and not silent_warned:
                    silent_warned = True
                    log.warning("SHADOW stream silent for %.0fs", silent)
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                except asyncio.TimeoutError:
                    continue
                last_msg = time.time()
                silent_warned = False
                try:
                    e = json.loads(raw)
                except Exception:
                    continue
                act = e.get("action")
                m = e.get("mint")
                if act == "create" and m:
                    # birth anchor (see tape_should_start): timestamps only
                    if tradable_event(e):
                        creates[m] = int(e.get("timestamp")
                                         or int(time.time() * 1000))
                        st["creates"] += 1
                    continue
                if act not in ("buy", "sell") or not m:
                    continue
                if not tradable_event(e):
                    continue
                px = e.get("price")
                if not px or float(px) <= 0:
                    continue
                px = float(px)
                ts = int(e.get("timestamp") or int(time.time() * 1000))
                st["prints"] += 1
                t = mints.get(m)
                if t is None:
                    if not tape_should_start(m, creates, taped):
                        continue
                    if len(mints) >= MAX_MINTS:
                        if time.time() - last_full_warn > 300.0:
                            last_full_warn = time.time()
                            log.warning(
                                "tape table at cap (%d) — birth anchor "
                                "at risk", len(mints))
                        continue
                    taped.add(m)
                    t = mints[m] = new_tape(m, ts)
                t["last_ts"] = ts
                # aligned per-print series (buys AND sells), mirroring
                # replay slot aggregation: one mark per print. Bounded:
                # the tape stops growing once the entry window closes.
                gate_event = push_print(
                    t, px, act,
                    float(e["quoteInPool"]) if e.get("quoteInPool") else 0.0,
                    signer=e.get("txSigner"))
                # live mark for open paper positions (last-print marks)
                if m in poss and t["prices"]:
                    p = poss[m]
                    p["last_ts"] = ts
                    mark = px * p["qty_tokens"]
                    if mark_suspect(mark, p["size"]):
                        # mis-scaled print: corroborate with the venue
                        # (read-only) before acting on it; at most once a
                        # minute so one bad mint can't storm the API.
                        now_t = time.time()
                        if now_t < p.get("corro_until", 0.0):
                            continue
                        p["corro_until"] = now_t + 60.0
                        q = order_quote(m, SOL, p["qty_base"])
                        vm = None
                        if q and q.get("outAmount"):
                            vm = int(q["outAmount"]) / LAMPORTS
                        p["anomalies"] = p.get("anomalies", 0) + 1
                        if not vm:
                            if p["anomalies"] <= 3:
                                log.warning(
                                    "SHADOW mark anomaly %s ratio=%.0fx "
                                    "venue=no-quote (skipped)",
                                    m[:8], mark / p["size"])
                            continue
                        if p["anomalies"] <= 3:
                            log.warning(
                                "SHADOW mark anomaly %s ratio=%.0fx "
                                "-> venue %.2fx (venue mark used)",
                                m[:8], mark / p["size"], vm / p["size"])
                        mark = vm
                    p["last_px"] = (mark / p["qty_tokens"] if p["qty_tokens"]
                                    else px)
                    p["peak"] = max(p.get("peak", 0.0), mark)
                    why = S.decide_exit(p["size"], p["peak"], mark,
                                        time.time() - p["t"])
                    if why is None and p.get("dump"):
                        why = "dump"  # vendor tape flagged the dump
                    if why is None or w.s.halted:
                        continue
                    if time.time() < p.get("cool_until", 0.0):
                        continue  # backing off after a venue miss
                    if time.time() < p.get("veto_until", 0.0):
                        continue  # venue vetoed this tape trigger recently
                    # Shadow exits are quote-fills: the wallet never took
                    # delivery of the tokens (signed-never-sent), so a sell
                    # build can only fail with "Insufficient funds" — seen
                    # live in run76b as two false -100% rugs while the
                    # mints quoted at 85-105% of cost. Value the exit at
                    # the venue's read-only quote (the same estimator
                    # paper uses) and close there. The token-dependent
                    # build path is exercised in dust with real fills.
                    q, qerr = order_quote_ex(m, SOL, p["qty_base"])
                    fill = quote_fill_sol(q)
                    if fill:
                        vwhy = venue_exit_reason(
                            why, p["size"], p.get("peak", 0.0), fill,
                            time.time() - p["t"],
                            urgent=p.get("dump_urgent", False))
                        if vwhy is None:
                            cool = (DUMP_VETO_COOL_S if why == "dump"
                                    else VETO_COOL_S)
                            p["veto_until"] = time.time() + cool
                            p["vetoes"] = p.get("vetoes", 0) + 1
                            if p["vetoes"] <= 3:
                                log.info(
                                    "SHADOW exit veto %s tape=%s rr=%.3f "
                                    "venue_rr=%.3f (venue disagrees)",
                                    m[:8], why, mark / p["size"],
                                    fill / p["size"])
                            continue
                        why = vwhy
                        p.pop("cool_until", None)
                        p["misses"] = 0
                        log.info("SHADOW exit fill %s out=%.6f SOL",
                                 m[:8], fill)
                        close_position(m, why, fill)
                        continue
                    kind = quote_failure_kind(qerr)
                    p["cool_until"] = time.time() + 60.0
                    log.info("SHADOW exit no-quote %s: %s", m[:8], qerr)
                    if kind == "ours" and ("HTTP 401" in qerr
                                           or "HTTP 403" in qerr) \
                            and L.once_auth_alert():
                        ntf.send_alert("🔑 Jupiter order auth failing",
                                       f"shadow exits degraded: "
                                       f"{qerr[:120]}")
                    if kind == "venue":
                        p["misses"] = p.get("misses", 0) + 1
                        if L.rug_give_up(p["misses"]):
                            log.warning(
                                "SHADOW rug-close %s after %d misses",
                                m[:8], p["misses"])
                            close_position(m, "rug", 0.0)  # dead mint:
                            # no venue quotes it, so it is worth zero, not
                            # the last (possibly stale-high) print
                    continue  # 'ours'/'other': back off, never a rug
                # entry gate on the window-completing print only: a signal
                # is acted on at its moment, never as a stale setup after
                # a slot frees up.
                if (gate_event and m not in poss and not w.s.halted
                        and len(poss) < MAXOPEN):
                    take, _ = S.decide_entry(
                        t["prices"][:ENTRY_N], t["acts"][:ENTRY_N],
                        t["liq"][:ENTRY_N])
                    if not take:
                        continue
                    ok, why_not = w.can_open(SIZE_SOL, m)
                    if not ok:
                        continue
                    # solpump.io data layer: the vendor tape carries
                    # per-trade wallet/bot/outlier flags that PumpAPI
                    # prints lack. Both run83 gates entered into an active
                    # dump (4-6 SOL SELL prints inside the gate second):
                    # read the vendor tape before spending a venue quote.
                    # The check waits for the (2-3 s lagging) REST tape to
                    # reach the gate second — see sp_gate_check.
                    if sp_feed is not None:
                        st["sig"] = st.get("sig", 0) + 1
                        sp_ok, sp_why, sp_feat = await asyncio.to_thread(
                            sp_gate_check, m, int(t["t0"]))
                        if not sp_ok:
                            st["sp_skips"] = st.get("sp_skips", 0) + 1
                            log.info(
                                "SHADOW sp-block %s: %s (tape n=%s buys=%s "
                                "sells=%s net3=%.2f s1sells=%.2f buyers=%s "
                                "wait=%.1fs)",
                                m[:8], sp_why, sp_feat.get("n"),
                                sp_feat.get("n_buys"), sp_feat.get("n_sells"),
                                sp_feat.get("s3_net", 0.0),
                                sp_feat.get("s1_sol_sells", 0.0),
                                sp_feat.get("buyers"),
                                sp_feat.get("wait_s", 0.0))
                            continue
                        log.info(
                            "SHADOW sp-pass %s n=%s buy=%.2f sell=%.2f "
                            "net3=%.2f s1sells=%.2f buyers=%s outlier=%.2f "
                            "wait=%.1fs",
                            m[:8], sp_feat.get("n"),
                            sp_feat.get("sol_buys", 0.0),
                            sp_feat.get("sol_sells", 0.0),
                            sp_feat.get("s3_net", 0.0),
                            sp_feat.get("s1_sol_sells", 0.0),
                            sp_feat.get("buyers"),
                            sp_feat.get("outlier_sell_sol", 0.0),
                            sp_feat.get("wait_s", 0.0))
                    # data-quality preflight: a read-only venue quote must
                    # broadly agree with the tape price the signal used; a
                    # mis-scaled tape (seen live: 337x) would otherwise buy
                    # a ghost. One extra quote per candidate — rare.
                    dec = token_decimals(m, hk) or 6
                    pq = order_quote(SOL, m,
                                     int(round(SIZE_SOL * LAMPORTS)))
                    if not pq or not pq.get("outAmount"):
                        log.info("SHADOW entry preflight no-quote %s", m[:8])
                        continue  # unquotable now: same as NoQuote below
                    tape_px = t["prices"][ENTRY_N - 1]
                    try:
                        vpx = SIZE_SOL / (int(pq["outAmount"]) / (10 ** dec))
                    except Exception:
                        continue
                    dev = price_deviation(tape_px, vpx)
                    rt = None
                    rt_why = "deviation"
                    if dev <= MAX_DEVIATION:
                        rt, rt_why = roundtrip_cost_pct(
                            m, int(pq["outAmount"]), SIZE_SOL)
                    st["gates"] += 1
                    log.info(
                        "SHADOW gate %s vpx=%.3g tape_px=%.3g dev=%.1f%% "
                        "rt=%s impact=%s route=%s", m[:8], vpx, tape_px,
                        dev * 100.0,
                        f"{rt:.1f}%" if rt is not None else "n/a",
                        pq.get("priceImpact"), pq.get("route"))
                    if dev > MAX_DEVIATION:
                        log.warning(
                            "SHADOW entry deviation %s tape_px=%.3g "
                            "venue_px=%.3g dev=%.1f%% > %.1f%% (skipped)",
                            m[:8], tape_px, vpx, dev * 100.0,
                            MAX_DEVIATION * 100.0)
                        continue
                    if rt is None:
                        log.info("SHADOW entry thin %s: no sell quote (%s)",
                                 m[:8], rt_why)
                        continue
                    if rt < -MAX_ROUNDTRIP:
                        log.info("SHADOW entry thin %s rt=%.1f%% < -%.1f%% "
                                 "(skipped)", m[:8], rt, MAX_ROUNDTRIP)
                        continue
                    try:
                        rc = L.place_order(
                            SOL, m, int(round(SIZE_SOL * LAMPORTS)),
                            SIZE_SOL, shadow=True)
                    except L.NoQuote as exc:
                        # counted skip (routine for fresh mints), never an
                        # error alert
                        log.info("SHADOW entry no-quote %s: %s", m[:8], exc)
                        if L.venue_auth_error(exc) and L.once_auth_alert():
                            ntf.send_alert("🔑 Jupiter order auth failing",
                                           f"shadow entries degraded: "
                                           f"{str(exc)[:120]}")
                        continue
                    except Exception as exc:
                        log.warning("SHADOW entry sign failed %s: %s",
                                    m[:8], exc)
                        continue
                    try:
                        qty_base = int(rc.out_amount)
                    except Exception:
                        continue
                    if qty_base <= 0:
                        continue
                    poss[m] = {"t": time.time(), "size": SIZE_SOL,
                               "qty_base": qty_base,
                               "qty_tokens": qty_base / (10 ** dec),
                               "entry_px": t["prices"][ENTRY_N - 1],
                               "entry_vpx": vpx,
                               "peak": 0.0, "sig": rc.signature,
                               "sp_recent": []}
                    st["buys"] += 1
                    if sp_feed is not None:
                        # live vendor streams for the held mint: swap tape
                        # (dump watch) + price + markers (event log)
                        for ch in ("swaps", "price", "chart_markers"):
                            sp_feed.subscribe(
                                f"token:{SP.QUOTE}:{m}:{ch}",
                                {"minUsd": "10"} if ch == "chart_markers"
                                else None)
                    ntf.send_open(
                        ca=m, name=m[:12], price=t["prices"][ENTRY_N - 1],
                        size_sol=SIZE_SOL, balance_before=w.s.balance,
                        balance_after=w.s.balance - SIZE_SOL,
                        open_count=len(poss),
                        max_positions=MAXOPEN, win_rate=w.s.win_rate,
                        dex="jupiter", buys=len(t["prices"]),
                        jup="🕶️ SHADOW BUY (signed-never-sent)")
                    log.info("SHADOW BUY %s epx=%s vpx=%.3g dec=%s qty_base=%s",
                             m, t["prices"][ENTRY_N - 1], vpx, dec, qty_base)
                # one-shot window: a completed tape is moot unless a
                # position still needs it for marks (kept until close).
                if t["done"] and m not in poss:
                    mints.pop(m, None)
                now = time.time()
                if now - last_prune > PRUNE_S:
                    cutoff = now * 1000 - IDLE_DROP_S * 1000
                    for mk in [k for k, v in mints.items()
                               if k not in poss and v["last_ts"] < cutoff]:
                        del mints[mk]
                    # completed non-position tapes are moot (one-shot);
                    # drop them promptly so the table cannot saturate
                    for mk in [k for k, v in mints.items()
                               if k not in poss and v.get("done")]:
                        del mints[mk]
                    for mk in [k for k, v in creates.items()
                               if now * 1000 - v
                               > CREATES_TTL_S * 1000]:
                        del creates[mk]
                    if len(taped) > TAPED_CAP:
                        log.warning("taped registry at %d — clearing",
                                    len(taped))
                        taped.clear()
                    last_prune = now
                    # flow-independent exits: dead mints get no prints, so
                    # TIME/STALE must fire here or positions sit forever.
                    for mk, p in list(poss.items()):
                        why = sweep_due(p, now)
                        if why is None and p.get("dump"):
                            why = "dump"  # vendor tape flagged the dump
                        if why is None:
                            _lp = p.get("last_px", 0.0) * p["qty_tokens"]
                            log.info("SHADOW hold %s rr=%.3f peak=%.5f age=%.0fs",
                                     mk[:8], _lp / p["size"] if p["size"] else 0,
                                     p.get("peak", 0.0), now - p["t"])
                            continue
                        # quote-fill exits (see the per-print exit above):
                        # no token-dependent build in shadow.
                        q, qerr = order_quote_ex(mk, SOL, p["qty_base"])
                        fill = quote_fill_sol(q)
                        if fill:
                            # same venue confirmation as the per-print path:
                            # a vendor dump flag alone must not book a
                            # phantom stop at a quote the venue never offered
                            vwhy = venue_exit_reason(
                                why, p["size"], p.get("peak", 0.0), fill,
                                now - p["t"],
                                urgent=p.get("dump_urgent", False))
                            if vwhy is None:
                                log.info(
                                    "SHADOW sweep exit veto %s tape=%s "
                                    "venue_rr=%.3f (venue disagrees)",
                                    mk[:8], why, fill / p["size"])
                                continue
                            log.info("SHADOW sweep exit fill out=%.6f SOL",
                                     fill)
                            close_position(mk, vwhy, fill)
                            continue
                        kind = quote_failure_kind(qerr)
                        log.info("SHADOW sweep no-quote %s: %s", mk[:8], qerr)
                        if kind == "ours" and ("HTTP 401" in qerr
                                               or "HTTP 403" in qerr) \
                                and L.once_auth_alert():
                            ntf.send_alert(
                                "🔑 Jupiter order auth failing",
                                f"sweep exits degraded: {qerr[:120]}")
                        if kind == "venue":
                            p["misses"] = p.get("misses", 0) + 1
                            if L.rug_give_up(p["misses"]):
                                log.warning(
                                    "SHADOW rug-close %s after %d misses",
                                    mk[:8], p["misses"])
                                close_position(mk, "rug", 0.0)  # as above:
                                # unclosable exit means zero realizable value
                        p["cool_until"] = time.time() + 60.0
                        continue  # 'ours'/'other': back off, never a rug

    crashed = None
    try:
        asyncio.run(run())
    except Exception as exc:
        crashed = exc
        log.exception("shadow loop crashed")
    log.info("shadow done bal=%.4f W=%d L=%d crashed=%s",
             w.s.balance, w.s.wins, w.s.losses, crashed or "no")


if __name__ == "__main__":
    main()
