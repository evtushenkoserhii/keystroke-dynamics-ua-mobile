#!/usr/bin/env python3
"""
Pack the published package into one archive for a data repository.

Zenodo accepts at most 100 files in a record and this package has over 500, one
Parquet file per session, so the sensors cannot be uploaded loose. The archive
this script builds holds the package exactly as it is laid out here, so that
unpacking it gives a working copy in which code/verify.py passes.

Usage
    python make_release_zip.py --dataset . --out kdua-mobile-1.0.zip

The archive is deterministic: entries are sorted, timestamps are fixed, and
nothing is compressed a second time. Parquet and .gz are already compressed, so
storing them saves minutes and costs about a percent of size. Two runs over the
same files therefore give the same bytes, and the printed SHA-256 can be
published next to the record.
"""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

# Everything that belongs in the published package. Anything else in the folder
# (notes, a .git directory, an editor's leftovers) is left out on purpose.
INCLUDE_FILES = ["README.md", "README.uk.md", "CITATION.cff", "CHANGELOG.md",
                 "LICENSE-DATA", "LICENSE-CODE", "datapackage.json",
                 "checksums.sha256", "fingerprint.sha256"]
INCLUDE_DIRS = ["data", "docs", "code", "splits", "sample"]
SKIP_SUFFIXES = {".pyc"}
SKIP_NAMES = {"__pycache__", ".DS_Store", "Thumbs.db"}
FIXED_DATE = (2026, 1, 1, 0, 0, 0)


def collect(dataset: Path) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for name in INCLUDE_FILES:
        p = dataset / name
        if p.is_file():
            out.append((p, name))
    for folder in INCLUDE_DIRS:
        base = dataset / folder
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix in SKIP_SUFFIXES or p.name in SKIP_NAMES:
                continue
            if any(part in SKIP_NAMES for part in p.parts):
                continue
            out.append((p, p.relative_to(dataset).as_posix()))
    return sorted(out, key=lambda t: t[1])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--prefix", default="",
                    help="optional folder name inside the archive")
    args = ap.parse_args()

    items = collect(args.dataset)
    if not items:
        raise SystemExit(f"nothing to pack in {args.dataset}")

    total = 0
    with zipfile.ZipFile(args.out, "w", compression=zipfile.ZIP_STORED,
                         allowZip64=True) as z:
        for path, name in items:
            arcname = f"{args.prefix.rstrip('/')}/{name}" if args.prefix else name
            info = zipfile.ZipInfo(arcname, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            with path.open("rb") as f:
                z.writestr(info, f.read())
            total += path.stat().st_size

    h = hashlib.sha256()
    with args.out.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)

    print(f"  files    {len(items)}")
    print(f"  content  {total / 1e6:.1f} MB")
    print(f"  archive  {args.out.stat().st_size / 1e6:.1f} MB")
    print(f"  sha256   {h.hexdigest()}")
    print(f"written to {args.out}")


if __name__ == "__main__":
    main()
