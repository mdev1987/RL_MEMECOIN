"""Feature timestamp contract: every feature must have available_at <= decision - latency."""
from __future__ import annotations


def check_cutoff(rows, decision_ts, latency_s=0.8):
    """rows: iterable of (name, available_at_ts). Raises on violation."""
    bad = [(n, ts) for n, ts in rows if ts > decision_ts - latency_s]
    if bad:
        raise AssertionError(f"leaky features (cutoff violated): {bad}")
    return True
