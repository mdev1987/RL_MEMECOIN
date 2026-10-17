"""Persistent paper wallet ledger with risk halts. Deterministic, JSON-backed."""
from __future__ import annotations
import json
import os
import time
from dataclasses import asdict, dataclass, field


@dataclass
class WalletState:
    balance: float = 1.0
    start: float = 1.0
    peak: float = 1.0
    day_pnl: float = 0.0
    day: str = ""
    wins: int = 0
    losses: int = 0
    halted: str = ""
    # mint -> epoch seconds of last attempt; entries older than the TTL
    # are re-tradeable (dedup is time-bound, not permanent).
    seen: dict = field(default_factory=dict)
    hour: str = ""
    hour_trades: int = 0

    @property
    def max_dd_pct(self):
        return (self.peak - self.balance) / self.peak * 100 if self.peak > 0 else 0.0

    @property
    def win_rate(self):
        t = self.wins + self.losses
        return 100.0 * self.wins / t if t else 0.0


def _today():
    return time.strftime("%Y-%m-%d", time.gmtime())


def _hour():
    return time.strftime("%Y-%m-%dT%H", time.gmtime())


class Wallet:
    def __init__(self, path="/tmp/opencode/paper_wallet.json", start=1.0,
                 daily_stop=0.10, dd_stop=0.30, max_pos=0.05, max_per_hour=30,
                 seen_ttl_hours=24):
        self.path = path
        self.daily_stop = daily_stop
        self.dd_stop = dd_stop
        self.max_pos = max_pos
        self.max_per_hour = max_per_hour
        self.seen_ttl = seen_ttl_hours * 3600.0
        self.s = self._load(start)

    def _load(self, start):
        import dataclasses
        try:
            d = json.loads(open(self.path).read())
            kw = {}
            for f in dataclasses.fields(WalletState):
                if f.name in d:
                    kw[f.name] = d[f.name]
                elif f.default is not dataclasses.MISSING:
                    kw[f.name] = f.default
                elif getattr(f, "default_factory", dataclasses.MISSING) is not dataclasses.MISSING:
                    kw[f.name] = f.default_factory()
            # migrate legacy list-format seen -> dict, stamped now so old
            # entries expire after one TTL instead of being permanent
            if isinstance(kw.get("seen"), list):
                now = time.time()
                kw["seen"] = {m: now for m in kw["seen"]}
            s = WalletState(**kw)
            if not isinstance(s.seen, dict):
                s.seen = {}
            if s.day != _today():
                s.day, s.day_pnl = _today(), 0.0
            return s
        except Exception:
            return WalletState(balance=start, start=start, peak=start, day=_today())

    def save(self):
        # prune expired entries so the ledger stays bounded
        now = time.time()
        self.s.seen = {m: ts for m, ts in self.s.seen.items()
                       if now - ts < self.seen_ttl}
        tmp = self.path + ".tmp"
        open(tmp, "w").write(json.dumps(asdict(self.s)))
        os.replace(tmp, self.path)

    def _reset_window(self):
        h = _hour()
        if self.s.hour != h:
            self.s.hour, self.s.hour_trades = h, 0
        if self.s.day != _today():
            # day rollover for long-running daemons (halt flags persist
            # until reviewed; only the daily PnL budget resets)
            self.s.day, self.s.day_pnl = _today(), 0.0

    def _is_duplicate(self, mint):
        ts = self.s.seen.get(mint)
        return ts is not None and (time.time() - ts) < self.seen_ttl

    def _dd_hit(self):
        """Drawdown halt test, safe when start is unset (live, start=0).

        start>0 (paper): percentage of the starting balance.
        start==0 (live ledger): absolute dd_stop SOL below the high-water
        mark. Seen 2026-10-17: the raw dd_stop/start division crashed the
        live loop on its first tradeable signal during the parity soak.
        """
        if self.s.start > 0:
            return self.s.max_dd_pct >= self.dd_stop / self.s.start * 100
        return self.s.peak > 0 and self.s.balance <= self.s.peak - self.dd_stop

    def can_open(self, size, mint):
        self._reset_window()
        if self.s.halted:
            return False, f"halted:{self.s.halted}"
        if size > self.max_pos + 1e-9:
            return False, "position-cap"
        if self._is_duplicate(mint):
            return False, "duplicate"
        if self.s.hour_trades >= self.max_per_hour:
            return False, "rate-limit"
        if self.s.day_pnl <= -self.daily_stop:
            self.s.halted = "daily-loss"
            return False, "daily-loss"
        if self._dd_hit():
            self.s.halted = "drawdown"
            return False, "drawdown"
        return True, "ok"

    def apply_fee(self, mint, cost_sol):
        """Failed-tx path: pay fixed costs only, no position, no win/loss."""
        self._reset_window()
        self.s.hour_trades += 1
        self.s.balance -= cost_sol
        self.s.day_pnl -= cost_sol
        self.s.seen[mint] = time.time()
        if self.s.day_pnl <= -self.daily_stop:
            self.s.halted = "daily-loss"
        if self._dd_hit():
            self.s.halted = "drawdown"
        self.save()
        return self.s.halted

    def apply_close(self, mint, pnl):
        self._reset_window()
        self.s.hour_trades += 1
        self.s.balance += pnl
        self.s.day_pnl += pnl
        self.s.peak = max(self.s.peak, self.s.balance)
        self.s.seen[mint] = time.time()
        if pnl > 0:
            self.s.wins += 1
        else:
            self.s.losses += 1
        if self.s.day_pnl <= -self.daily_stop:
            self.s.halted = "daily-loss"
        if self._dd_hit():
            self.s.halted = "drawdown"
        self.save()
        return self.s.halted
