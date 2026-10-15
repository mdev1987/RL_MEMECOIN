"""Replay data loader: bundle-grouping (3ms) + latency buffer, no lookahead."""
from __future__ import annotations
import json


def group_bundles(events, bundle_ms=3):
    """Group same-token events within bundle_ms as one atomic unit."""
    out = []
    cur = []
    for e in sorted(events, key=lambda x: (x.get("mint", ""), x.get("timestamp", 0))):
        if not cur:
            cur = [e]
            continue
        same = e.get("mint") == cur[-1].get("mint")
        dt = abs((e.get("timestamp", 0) or 0) - (cur[-1].get("timestamp", 0) or 0)) * 1000
        if same and dt <= bundle_ms:
            cur.append(e)
        else:
            out.append(cur)
            cur = [e]
    if cur:
        out.append(cur)
    return out


def load_replay_jsonl(path, limit=10000):
    evts = []
    with open(path) as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            line = line.strip()
            if line:
                evts.append(json.loads(line))
    return evts
