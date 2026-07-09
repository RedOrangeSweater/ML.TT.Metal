#!/usr/bin/env python3
"""Skip Tracy capture/csvexport ExternalProjects when ENABLE_TRACY is OFF."""
from __future__ import annotations

from pathlib import Path


def main() -> int:
    p = Path("cmake/tracy.cmake")
    text = p.read_text()
    if "LOCAL_SKIP_TRACY_TOOLS" in text:
        print("already patched")
        return 0
    old = (
        "# Our current fork of tracy does not have CMake support for these subdirectories\n"
        "# Once we update, we can change this\n"
        "include(ExternalProject)\n"
        "ExternalProject_Add(\n"
        "    tracy_csv_tools"
    )
    new = (
        "# Our current fork of tracy does not have CMake support for these subdirectories\n"
        "# Once we update, we can change this\n"
        "# LOCAL_SKIP_TRACY_TOOLS\n"
        "if(ENABLE_TRACY)\n"
        "include(ExternalProject)\n"
        "ExternalProject_Add(\n"
        "    tracy_csv_tools"
    )
    if old not in text:
        raise SystemExit("tracy.cmake anchor missing")
    text = text.replace(old, new, 1)
    text = text.rstrip() + "\nendif() # ENABLE_TRACY / LOCAL_SKIP_TRACY_TOOLS\n"
    p.write_text(text)
    print("patched", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
