#!/usr/bin/env python3
"""Retag a wheel platform tag without rewriting ELF (not auditwheel).

Used when a wheel was built inside a manylinux image but cibuildwheel left a
plain linux_* tag because CIBW_REPAIR_WHEEL_COMMAND was empty. PyPI rejects
linux_x86_64; manylinux_2_34_x86_64 is accepted.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


def retag(src: Path, platform_tag: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        work.mkdir()
        with zipfile.ZipFile(src) as zf:
            zf.extractall(work)

        dist_infos = list(work.glob("*.dist-info"))
        if len(dist_infos) != 1:
            raise SystemExit(f"expected one .dist-info, found {dist_infos}")
        di = dist_infos[0]
        wheel_path = di / "WHEEL"
        text = wheel_path.read_text()
        if not re.search(r"(?m)^Tag:", text):
            text = text.rstrip() + f"\nTag: py3-none-{platform_tag}\n"
        else:
            # Replace only the platform portion of existing tags.
            def _sub(m: re.Match[str]) -> str:
                tag = m.group(1)
                parts = tag.split("-")
                if len(parts) >= 3:
                    parts[-1] = platform_tag
                    return f"Tag: {'-'.join(parts)}"
                return f"Tag: {tag.rsplit('-', 1)[0]}-{platform_tag}"

            text = re.sub(r"(?m)^Tag: (.+)$", _sub, text)
        wheel_path.write_text(text)

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

        new_name = re.sub(
            r"(linux_[^.]+|manylinux_[^.]+|musllinux_[^.]+)\.whl$",
            f"{platform_tag}.whl",
            src.name,
        )
        if new_name == src.name and platform_tag not in src.name:
            stem = src.name[: -len(".whl")]
            # last tag component is platform
            parts = stem.split("-")
            parts[-1] = platform_tag
            new_name = "-".join(parts) + ".whl"
        out = output_dir / new_name
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(list(files) + [di / "RECORD"], key=lambda x: str(x.relative_to(work))):
                zf.write(p, p.relative_to(work).as_posix())
        return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="Input .whl (glob ok via shell)")
    ap.add_argument("--platform-tag", required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    # Allow shell-expanded globs passed as a single path.
    src = Path(args.input)
    if not src.is_file():
        matches = sorted(Path().glob(args.input))
        if len(matches) != 1:
            print(f"input not found or ambiguous: {args.input}", file=sys.stderr)
            return 2
        src = matches[0]

    out = retag(src, args.platform_tag, Path(args.output_dir))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
