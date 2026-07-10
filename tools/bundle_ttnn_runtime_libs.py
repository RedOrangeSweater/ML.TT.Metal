#!/usr/bin/env python3
"""Copy-only repair for unrepaired ttnn wheels (no auditwheel, no patchelf).

On pin 8dfb324 the unrepaired cibuildwheel output is missing only
libtracy.so.0.10.0 under ttnn/build/lib. OpenMPI/hwloc stay as system
runtime deps (install via apt / image OpenMPI prefix).

patchelf --set-rpath on this pin corrupts ELF (.init/.plt leave the
executable LOAD) and import ttnn SIGSEGV. This script therefore:

1. Copies libtracy.so.0.10.0 (+ libtracy.so symlink) into ttnn/build/lib
2. Leaves every pre-existing ELF byte-identical (SHA256 checked)
3. Rebuilds RECORD and writes the repaired wheel

Intended as CIBW_REPAIR_WHEEL_COMMAND inside the manylinux build
container, where /project/build_Release/lib{,64} still exist.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

TRACY_SONAME = "libtracy.so.0.10.0"
TRACY_LINK = "libtracy.so"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _find_tracy(search_dirs: list[Path]) -> Path:
    for d in search_dirs:
        if not d.is_dir():
            continue
        candidate = d / TRACY_SONAME
        if candidate.is_file():
            return candidate.resolve()
        # Sometimes only the unversioned symlink exists
        link = d / TRACY_LINK
        if link.is_file() or link.is_symlink():
            return link.resolve()
    raise FileNotFoundError(
        f"{TRACY_SONAME} not found in: " + ", ".join(str(p) for p in search_dirs)
    )


def _rewrite_record(work: Path) -> None:
    dist_infos = list(work.glob("*.dist-info"))
    if len(dist_infos) != 1:
        raise SystemExit(f"expected one .dist-info, found {dist_infos}")
    di = dist_infos[0]
    files = [p for p in work.rglob("*") if p.is_file() and p.name != "RECORD"]
    lines: list[str] = []
    for p in sorted(files, key=lambda x: str(x.relative_to(work))):
        data = p.read_bytes()
        digest = (
            base64.urlsafe_b64encode(hashlib.sha256(data).digest())
            .rstrip(b"=")
            .decode()
        )
        lines.append(f"{p.relative_to(work).as_posix()},sha256={digest},{len(data)}")
    lines.append(f"{di.relative_to(work).as_posix()}/RECORD,,")
    (di / "RECORD").write_text("\n".join(lines) + "\n")


def repair(wheel: Path, dest_dir: Path, search_dirs: list[Path]) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    tracy_src = _find_tracy(search_dirs)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        work.mkdir()
        with zipfile.ZipFile(wheel) as zf:
            zf.extractall(work)

        lib_dir = work / "ttnn" / "build" / "lib"
        if not lib_dir.is_dir():
            raise SystemExit(f"missing {lib_dir} inside wheel")

        # Snapshot SHA256 of every pre-existing file under ttnn/build/lib
        before: dict[str, str] = {}
        for p in lib_dir.rglob("*"):
            if p.is_file() and not p.is_symlink():
                before[p.relative_to(work).as_posix()] = _sha256(p)

        # Also snapshot the extension module
        for p in (work / "ttnn").glob("_ttnn*.so"):
            before[p.relative_to(work).as_posix()] = _sha256(p)

        dest_tracy = lib_dir / TRACY_SONAME
        if dest_tracy.exists() or dest_tracy.is_symlink():
            raise SystemExit(
                f"{TRACY_SONAME} already present; refusing to overwrite "
                "(would hide a packaging bug)"
            )
        shutil.copy2(tracy_src, dest_tracy)

        link = lib_dir / TRACY_LINK
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(TRACY_SONAME)

        # Invariant: every previously present ELF is byte-identical
        for rel, expected in before.items():
            actual = _sha256(work / rel)
            if actual != expected:
                raise SystemExit(
                    f"ELF invariant violated for {rel}: "
                    f"before={expected} after={actual}"
                )

        _rewrite_record(work)

        out = dest_dir / wheel.name
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(work.rglob("*")):
                if p.is_file() or p.is_symlink():
                    # zipfile follows symlinks by default when writing file content;
                    # write symlink members as the target file content under the
                    # symlink name is wrong for SONAME resolution — store the
                    # real tracy once and a second member for the link name that
                    # is also the real bytes (pip/zip on Linux extracts both as
                    # files; ld.so resolves via SONAME filename).
                    zf.write(p.resolve() if p.is_symlink() else p, p.relative_to(work).as_posix())
        print(f"copied_tracy={tracy_src}")
        print(f"invariant_checked={len(before)}")
        print(out)
        return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("wheel")
    ap.add_argument("--dest-dir", required=True)
    ap.add_argument(
        "--search-dir",
        action="append",
        default=[],
        help="Directory to search for libtracy (repeatable)",
    )
    args = ap.parse_args()

    defaults = [
        Path("/project/build_Release/lib"),
        Path("/project/build_Release/lib64"),
        Path("/project/build/lib"),
        Path("/project/build/lib64"),
    ]
    search = [Path(p) for p in args.search_dir] + defaults
    repair(Path(args.wheel), Path(args.dest_dir), search)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
