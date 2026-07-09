#!/usr/bin/env python3
"""Bundle runtime .so files into an unrepaired ttnn wheel (no auditwheel).

auditwheel repair on pin 8dfb324 corrupts ELF. This script only *copies*
missing shared libraries next to the already-packaged libs under
ttnn/build/lib (RUNPATH already includes $ORIGIN) and optionally rewrites
RPATH to $ORIGIN with patchelf — without relocating sections the way
auditwheel does.

Intended as CIBW_REPAIR_WHEEL_COMMAND inside the manylinux build container,
where /project/build_Release/lib and OpenMPI prefix still exist.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def _needed(so: Path) -> list[str]:
    out = subprocess.check_output(["readelf", "-d", str(so)], text=True)
    names: list[str] = []
    for line in out.splitlines():
        if "NEEDED" in line and "[" in line:
            names.append(line.split("[", 1)[1].split("]", 1)[0])
    return names


def _find_lib(name: str, search_dirs: list[Path]) -> Path | None:
    for d in search_dirs:
        if not d.is_dir():
            continue
        exact = d / name
        if exact.is_file():
            return exact
        # SONAME may be a symlink target; also try prefix match
        matches = sorted(d.glob(name + "*"))
        for m in matches:
            if m.is_file() or m.is_symlink():
                return m
    return None


def _copy_lib(src: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Copy real file + preserve soname symlink if src is symlink
    if src.is_symlink():
        target = src.resolve()
        dest_real = dest_dir / target.name
        if not dest_real.exists():
            shutil.copy2(target, dest_real)
        link = dest_dir / src.name
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(dest_real.name)
    else:
        dest = dest_dir / src.name
        if not dest.exists():
            shutil.copy2(src, dest)
        # Also create SONAME symlink if readelf reports one different from filename
        try:
            out = subprocess.check_output(["readelf", "-d", str(src)], text=True)
            for line in out.splitlines():
                if "SONAME" in line and "[" in line:
                    soname = line.split("[", 1)[1].split("]", 1)[0]
                    if soname != src.name:
                        link = dest_dir / soname
                        if not link.exists() and not link.is_symlink():
                            link.symlink_to(src.name)
        except subprocess.CalledProcessError:
            pass


def _set_rpath_origin(so: Path) -> None:
    if shutil.which("patchelf") is None:
        return
    # Only rewrite RPATH/RUNPATH; do not --force-rpath relocate sections.
    subprocess.check_call(
        ["patchelf", "--set-rpath", "$ORIGIN", str(so)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def bundle(wheel: Path, dest_dir: Path, search_dirs: list[Path]) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        work.mkdir()
        with zipfile.ZipFile(wheel) as zf:
            zf.extractall(work)

        lib_dir = work / "ttnn" / "build" / "lib"
        if not lib_dir.is_dir():
            raise SystemExit(f"missing {lib_dir} inside wheel")

        # Seed queue from packaged .so NEEDED lists
        queue: list[str] = []
        for so in list(lib_dir.glob("*.so")) + list(work.glob("ttnn/_ttnn*.so")):
            queue.extend(_needed(so))

        seen: set[str] = set()
        bundled: list[str] = []
        while queue:
            name = queue.pop(0)
            if name in seen:
                continue
            seen.add(name)
            # Skip glibc / compiler runtime — provided by manylinux / host
            if name.startswith(("libc.so", "libm.so", "libdl.so", "librt.so", "libpthread.so", "ld-linux", "libgcc_s", "libstdc++")):
                continue
            if (lib_dir / name).exists() or any(lib_dir.glob(name + "*")):
                continue
            src = _find_lib(name, search_dirs)
            if src is None:
                print(f"WARN: could not find {name}", file=sys.stderr)
                continue
            _copy_lib(src, lib_dir)
            bundled.append(src.name)
            # Recurse into newly copied lib
            real = (lib_dir / src.resolve().name) if src.is_symlink() else (lib_dir / src.name)
            if real.is_file():
                queue.extend(_needed(real))

        # Fix absolute RUNPATHs on bundled project libs so $ORIGIN wins after install
        for so in lib_dir.glob("*.so*"):
            if so.is_symlink() or not so.is_file():
                continue
            if so.name.startswith(("libtt_", "libdevice", "libtracy", "_ttnn", "libmpi", "libopen-", "libpmix", "libhwloc", "libnuma", "libevent")):
                _set_rpath_origin(so)

        out = dest_dir / wheel.name
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(work.rglob("*")):
                if p.is_file():
                    zf.write(p, p.relative_to(work).as_posix())
        print(f"bundled={bundled}")
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
        help="Directory to search for missing .so (repeatable)",
    )
    args = ap.parse_args()

    defaults = [
        Path("/project/build_Release/lib"),
        Path("/project/build_Release/lib64"),
        Path("/opt/openmpi-v5.0.7-ulfm/lib"),
        Path("/usr/lib64"),
        Path("/usr/lib"),
        Path("/lib64"),
        Path("/lib"),
    ]
    search = [Path(p) for p in args.search_dir] + defaults
    bundle(Path(args.wheel), Path(args.dest_dir), search)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
