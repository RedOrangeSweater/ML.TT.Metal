#!/usr/bin/env python3
"""Copy-only repair for unrepaired ttnn wheels (no auditwheel, no patchelf).

On pin 8dfb324 the unrepaired cibuildwheel output is missing runtime shared
libraries under ttnn/build/lib: libtracy.so.0.10.0 plus the OpenMPI 5.0.7-ULFM
closure (libmpi.so.40 -> libopen-pal, libpmix, libevent*, libhwloc, libnuma and
their system deps). Without them `import ttnn` fails off the build host with
`undefined symbol: MPIX_Comm_revoke` (system OpenMPI 4.x lacks ULFM) or a
missing libmpi.

auditwheel / patchelf --set-rpath on this pin corrupt ELF (.init/.plt leave the
executable LOAD) and `import ttnn` SIGSEGVs. This script therefore performs a
pure *copy* repair and relies on the RUNPATH already baked into the project libs
(which already contains `$ORIGIN`), so no ELF rewrite is needed:

1. Copies libtracy.so.0.10.0 (+ libtracy.so symlink) into ttnn/build/lib
2. Copies the recursive NEEDED closure (OpenMPI + deps) into ttnn/build/lib,
   skipping glibc / compiler runtime provided by the manylinux host
3. Leaves every pre-existing ELF byte-identical (SHA256 checked)
4. Rebuilds RECORD and writes the repaired wheel

Intended as CIBW_REPAIR_WHEEL_COMMAND inside the manylinux build container,
where /project/build_Release/lib{,64} and /opt/openmpi-v5.0.7-ulfm/lib exist.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

TRACY_SONAME = "libtracy.so.0.10.0"
TRACY_LINK = "libtracy.so"

# Libraries provided by the manylinux host / glibc / compiler runtime. Bundling
# these would risk ABI conflicts, so they are left as external NEEDED entries.
SKIP_PREFIXES = (
    "libc.so",
    "libm.so",
    "libdl.so",
    "librt.so",
    "libpthread.so",
    "ld-linux",
    "libgcc_s",
    "libstdc++",
    "libresolv.so",
    "libutil.so",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _needed(so: Path) -> list[str]:
    """Return the DT_NEEDED names of an ELF shared object."""
    try:
        out = subprocess.check_output(["readelf", "-d", str(so)], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    names: list[str] = []
    for line in out.splitlines():
        if "(NEEDED)" in line and "[" in line:
            names.append(line.split("[", 1)[1].split("]", 1)[0])
    return names


def _soname(so: Path) -> str | None:
    try:
        out = subprocess.check_output(["readelf", "-d", str(so)], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    for line in out.splitlines():
        if "(SONAME)" in line and "[" in line:
            return line.split("[", 1)[1].split("]", 1)[0]
    return None


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


def _find_lib(name: str, search_dirs: list[Path]) -> Path | None:
    for d in search_dirs:
        if not d.is_dir():
            continue
        exact = d / name
        if exact.exists():
            return exact
        matches = sorted(d.glob(name + "*"))
        for m in matches:
            if m.is_file() or m.is_symlink():
                return m
    return None


def _present(lib_dir: Path, name: str) -> bool:
    if (lib_dir / name).exists():
        return True
    return any(lib_dir.glob(name + "*"))


def _copy_lib(src: Path, name: str, lib_dir: Path) -> Path:
    """Copy the real file behind ``src`` into ``lib_dir`` and make sure both its
    real basename and the requested SONAME ``name`` resolve to it. Returns the
    path to the copied real file (for NEEDED recursion)."""
    real = src.resolve()
    dest_real = lib_dir / real.name
    if not dest_real.exists():
        shutil.copy2(real, dest_real)
    # Ensure a member named exactly `name` exists (ld.so resolves by SONAME).
    if name != real.name:
        link = lib_dir / name
        if not link.exists() and not link.is_symlink():
            link.symlink_to(real.name)
    # Also expose the ELF SONAME if it differs from the file name.
    soname = _soname(dest_real)
    if soname and soname != real.name and not _present(lib_dir, soname):
        (lib_dir / soname).symlink_to(real.name)
    return dest_real


def _bundle_closure(work: Path, lib_dir: Path, search_dirs: list[Path]) -> list[str]:
    """Copy the recursive NEEDED closure of the packaged libs into ``lib_dir``.

    Pure copy: never rewrites RPATH/RUNPATH (the project libs already carry
    ``$ORIGIN`` in RUNPATH, so co-located libs are found at import time)."""
    queue: list[str] = []
    for so in list(lib_dir.glob("*.so")) + list(lib_dir.glob("*.so.*")):
        if so.is_file() and not so.is_symlink():
            queue.extend(_needed(so))
    for so in (work / "ttnn").glob("_ttnn*.so"):
        queue.extend(_needed(so))

    seen: set[str] = set()
    bundled: list[str] = []
    while queue:
        name = queue.pop(0)
        if name in seen:
            continue
        seen.add(name)
        if name.startswith(SKIP_PREFIXES):
            continue
        if _present(lib_dir, name):
            continue
        src = _find_lib(name, search_dirs)
        if src is None:
            print(f"WARN: could not find {name}", file=sys.stderr)
            continue
        real = _copy_lib(src, name, lib_dir)
        bundled.append(real.name)
        queue.extend(_needed(real))
    return bundled


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

    # cibuildwheel only copies *.whl from {dest_dir} back to the host via
    # /output. Writes under /project do NOT persist. Keep an unrepaired twin
    # next to the repaired wheel so CI can run the ELF invariant gate.
    raw_out = dest_dir / f"UNREPAIRED.{wheel.name}"
    shutil.copy2(wheel, raw_out)
    print(f"saved_unrepaired={raw_out}")

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

        # Copy the recursive NEEDED closure (OpenMPI ULFM + deps) next to the
        # project libs. Pure copy; RUNPATH ($ORIGIN) already resolves them.
        bundled = _bundle_closure(work, lib_dir, search_dirs)

        # Invariant: every previously present ELF is byte-identical (we only add
        # new files, never rewrite existing ones -> no SIGSEGV-inducing ELF edit)
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
                    # real lib once and a second member for the link name that
                    # is also the real bytes (pip/zip on Linux extracts both as
                    # files; ld.so resolves via SONAME filename).
                    zf.write(p.resolve() if p.is_symlink() else p, p.relative_to(work).as_posix())
        print(f"copied_tracy={tracy_src}")
        print(f"bundled_closure={bundled}")
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
        help="Directory to search for runtime .so (repeatable)",
    )
    args = ap.parse_args()

    defaults = [
        Path("/project/build_Release/lib"),
        Path("/project/build_Release/lib64"),
        Path("/project/build/lib"),
        Path("/project/build/lib64"),
        Path("/opt/openmpi-v5.0.7-ulfm/lib"),
        Path("/usr/lib64"),
        Path("/usr/lib"),
        Path("/lib64"),
        Path("/lib"),
    ]
    search = [Path(p) for p in args.search_dir] + defaults
    repair(Path(args.wheel), Path(args.dest_dir), search)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
