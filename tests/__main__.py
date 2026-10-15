"""Test runner: .venv/bin/python -m tests (no pytest needed)."""
from __future__ import annotations
import traceback
import tests.test_bot as t


def main() -> int:
    fns = sorted(n for n in dir(t) if n.startswith("test_"))
    fails = 0
    for n in fns:
        try:
            getattr(t, n)()
            print(f"PASS {n}")
        except Exception as exc:
            fails += 1
            print(f"FAIL {n}: {exc}")
            traceback.print_exc(limit=5)
    print(f"{len(fns) - fails}/{len(fns)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
