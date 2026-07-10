#!/usr/bin/env python3
"""Fail if repaired wheel changed any ELF that already existed in the raw wheel.

Used as a CI gate after copy-only tracy bundling. Only new files (libtracy*)
may appear; every pre-existing member must stay byte-identical.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path


def _is_so_member(name: str) -> bool:
    base = Path(name).name
    return base.endswith(".so") or ".so." in base


def _sha_map(wheel: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with zipfile.ZipFile(wheel) as zf:
        for name in zf.namelist():
            if not _is_so_member(name):
                continue
            out[name] = hashlib.sha256(zf.read(name)).hexdigest()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-wheel", type=Path, required=True)
    ap.add_argument("--repaired-wheel", type=Path, required=True)
    ap.add_argument(
        "--allow-added-prefix",
        action="append",
        default=["ttnn/build/lib/libtracy"],
        help="Path prefix for members allowed to be newly added",
    )
    args = ap.parse_args()

    raw = _sha_map(args.raw_wheel)
    repaired = _sha_map(args.repaired_wheel)

    changed = sorted(n for n in raw if repaired.get(n) != raw[n])
    added = sorted(set(repaired) - set(raw))
    removed = sorted(set(raw) - set(repaired))

    bad_added = [
        n
        for n in added
        if not any(n.startswith(p) for p in args.allow_added_prefix)
    ]

    print(f"raw_sos={len(raw)} repaired_sos={len(repaired)}")
    print(f"unchanged={len(raw) - len(changed)}")
    print(f"changed={changed}")
    print(f"added={added}")
    print(f"removed={removed}")

    if changed or removed or bad_added:
        print("ELF_INVARIANT_FAIL", file=sys.stderr)
        if bad_added:
            print(f"unexpected_added={bad_added}", file=sys.stderr)
        return 1

    if not any("libtracy.so.0.10.0" in n for n in added):
        print("ELF_INVARIANT_FAIL: libtracy.so.0.10.0 not added", file=sys.stderr)
        return 1

    print("ELF_INVARIANT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
