"""Telegram trade cards — markdown style with icons (sync facade).

Ports the card builders (open/close/summary/startup/alert) to this repo's
sync style: ``telegramify-markdown`` renders entities, delivery goes over
plain HTTPS with ``python-telegram-bot`` types avoided entirely. Silent
no-op when ``TELEGRAM_BOT_TOKEN`` / ``TELEGRAM_CHAT_ID`` (or ``TG_*``
aliases) are missing, so the bot runs console-only.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import requests
import telegramify_markdown

log = logging.getLogger(__name__)

SEP = "•"
_MIN_GAP_S = 3.0
_MAX_PER_MIN = 18


def _creds():
    import os
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TG_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("TG_CHAT")
    return token, chat


class TelegramNotifier:
    def __init__(self) -> None:
        self._token, self._chat = _creds()
        self._enabled = bool(self._token and self._chat)
        self._last = 0.0
        self._sent: list[float] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _post(self, text: str) -> bool:
        try:
            rendered, entities = telegramify_markdown.convert(
                text, latex_escape=False)
            payload: dict[str, Any] = {"chat_id": self._chat, "text": rendered}
            if entities:
                payload["entities"] = [
                    {"type": e.type, "offset": e.offset, "length": e.length,
                     **({"url": e.url} if getattr(e, "url", None) else {})}
                    for e in entities
                ]
            for attempt in range(5):
                try:
                    r = requests.post(
                        f"https://api.telegram.org/bot{self._token}/sendMessage",
                        json=payload, timeout=15)
                    if r.status_code == 200:
                        return True
                    try:
                        body = r.json()
                    except Exception:
                        body = {}
                    if r.status_code == 429:
                        wait = float(body.get("parameters", {})
                                     .get("retry_after", 5)) + 1.0
                        log.info("telegram flood control — retry after %.0fs", wait)
                        time.sleep(wait)
                        continue
                    log.warning("telegram send HTTP %s: %s",
                                r.status_code, r.text[:150])
                    return False
                except requests.Timeout:
                    time.sleep(5.0)
                except Exception as exc:
                    log.warning("telegram send failed (attempt %d): %s",
                                attempt + 1, exc)
                    time.sleep(2 * (attempt + 1))
            return False
        except Exception as exc:
            log.warning("telegram render failed: %s", exc)
            return False

    def send(self, text: str) -> bool:
        if not self._enabled:
            log.debug("telegram disabled — dropping: %s", text[:80])
            return False
        now = time.monotonic()
        self._sent = [t for t in self._sent if now - t < 60.0]
        if len(self._sent) >= _MAX_PER_MIN:
            log.warning("telegram rate limit — dropping message")
            return False
        wait = _MIN_GAP_S - (now - self._last)
        if wait > 0:
            time.sleep(wait)
        ok = self._post(text)
        self._last = time.monotonic()
        self._sent.append(self._last)
        return ok

    def test(self) -> bool:
        if not self._enabled:
            print("[telegram] disabled")
            return False
        try:
            me = requests.get(
                f"https://api.telegram.org/bot{self._token}/getMe",
                timeout=15).json()
            print(f"[telegram] connected as @{me['result']['username']}")
            return True
        except Exception as exc:
            print(f"[telegram] connection failed: {exc}")
            return False

    @staticmethod
    def _fmt_px(px: float) -> str:
        return f"{px:.14f}".rstrip("0").rstrip(".") or "0"

    @staticmethod
    def _fmt_dur(seconds: float) -> str:
        s = int(max(seconds, 0))
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        if h:
            return f"{h}h {m:02d}m"
        if m:
            return f"{m}m {sec:02d}s"
        return f"{sec}s"

    def send_startup(self, summary: str = "") -> None:
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        self.send(f"🚀 **Bot Started**\n{SEP} `{now}`\n{SEP} {summary}")

    def send_alert(self, title: str, detail: str = "") -> None:
        body = f"⚠️ **{title}**"
        if detail:
            body += f"\n{SEP} {detail}"
        self.send(body)

    def send_open(self, ca: str, name: str, price: float,
                  size_sol: float | None = None,
                  balance_before: float | None = None,
                  balance_after: float | None = None,
                  open_count: int | None = None,
                  max_positions: int | None = None,
                  win_rate: float | None = None,
                  dex: str | None = None,
                  buys: int | None = None,
                  liq_usd: float | None = None,
                  rug: Any | None = None,
                  jup: str | None = None) -> None:
        lines = [f"🟢 **OPENED** `{name}`", f"📍 `{ca}`"]
        meta = []
        if dex:
            meta.append(f"🌐 Dex `{dex}`")
        if liq_usd:
            meta.append(f"💧 LP `${liq_usd:,.0f}`")
        if meta:
            lines.append(" ".join(meta))
        entry = f"💵 Entry `${self._fmt_px(price)}`"
        if size_sol is not None:
            entry += f"  💰 Size `{size_sol:g}` SOL"
        lines.append(entry)
        extra = []
        if buys is not None:
            extra.append(f"🔥 Buys/h `{buys}`")
        if rug is not None:
            extra.append(f"🛡️ Rug `{rug}`")
        if extra:
            lines.append("  ".join(extra))
        if open_count is not None and max_positions is not None:
            lines.append(f"📊 Positions `{open_count}/{max_positions}`")
        if balance_before is not None and balance_after is not None:
            lines.append(f"💼 Balance `{balance_before:.4f}` → "
                         f"`{balance_after:.4f}` SOL")
        if jup:
            lines.append(jup)
        if win_rate is not None:
            lines.append(f"🏆 WinRate `{win_rate:.1f}%`")
        self.send("\n".join(lines))

    def send_close(self, ca: str, name: str, reason: str, mult: float,
                   pnl_sol: float, hold_s: float | None = None,
                   entry_px: float | None = None,
                   exit_px: float | None = None,
                   size_sol: float | None = None,
                   balance_before: float | None = None,
                   balance_after: float | None = None,
                   open_count: int | None = None,
                   max_positions: int | None = None,
                   win_rate: float | None = None,
                   dex: str | None = None,
                   via: str | None = None,
                   jup: str | None = None) -> None:
        label, icon = {
            "TP": ("TAKE PROFIT", "🎯"), "SL": ("STOP LOSS", "🛑"),
            "STOP": ("STOP LOSS", "🛑"), "TRAIL": ("TRAILING STOP", "🛑"),
            "TIME": ("TIMEOUT", "⏱️"), "RUG": ("RUG PULL", "🧨"),
        }.get(reason, (reason.upper(), "💰"))
        win = pnl_sol > 0
        sign = "+" if win else ""
        pct = (mult - 1.0) * 100.0
        icon = "✅" if win else "❌"
        lines = [f"{icon} **{label}** `{name}`", f"📍 `{ca}`"]
        meta = []
        if dex:
            meta.append(f"🌐 Dex `{dex}`")
        if via:
            meta.append(f"📡 `{via}`")
        if meta:
            lines.append(" ".join(meta))
        if entry_px is not None:
            part = (f" → 📉 Exit `${self._fmt_px(exit_px)}`"
                    if exit_px is not None else "")
            lines.append(f"📈 Entry `${self._fmt_px(entry_px)}`{part}")
        pnl = (f"{'✅' if win else '❌'} PnL `{sign}{pnl_sol:.4f}` SOL "
               f"(`{sign}{pct:.1f}%`, `{mult:.2f}x`)")
        if size_sol is not None:
            pnl += f"  💰 Size `{size_sol:g}` SOL"
        lines.append(pnl)
        if hold_s is not None:
            lines.append(f"⏱️ Duration `{self._fmt_dur(hold_s)}`")
        if open_count is not None and max_positions is not None:
            lines.append(f"📊 Positions `{open_count}/{max_positions}`")
        if balance_before is not None and balance_after is not None:
            lines.append(f"💼 Balance `{balance_before:.4f}` → "
                         f"`{balance_after:.4f}` SOL")
        if jup:
            lines.append(jup)
        if win_rate is not None:
            lines.append(f"🏆 WinRate `{win_rate:.1f}%`")
        self.send("\n".join(lines))

    def send_summary(self, open_n: int, closed_n: int,
                     win_rate: float, pnl_sol: float) -> None:
        self.send(f"💰 **Summary**\n{SEP} Open `{open_n}` {SEP} Closed `{closed_n}`\n"
                  f"{SEP} WinRate `{win_rate:.1f}%`\n{SEP} PnL `{pnl_sol:+.4f}` SOL")

    def send_stopped(self, open_n: int, closed_n: int,
                     win_rate: float, pnl_sol: float) -> None:
        self.send(f"🏁 **Bot Stopped**\n{SEP} Open `{open_n}` {SEP} Closed `{closed_n}`\n"
                  f"{SEP} WinRate `{win_rate:.1f}%`\n{SEP} PnL `{pnl_sol:+.4f}` SOL")


_notifier: TelegramNotifier | None = None


def get_notifier() -> TelegramNotifier:
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier


def send(text: str) -> bool:
    return get_notifier().send(text)
