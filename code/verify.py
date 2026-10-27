#!/usr/bin/env python3
"""
Check a downloaded copy of the KDUA-Mobile package.

Two different checks, because they answer two different questions:

  checksums.sha256    the bytes of every published file. Answers "did my
                      download arrive intact". These sums belong to the
                      published files and cannot be reproduced by converting
                      the archives again on another machine: pyarrow writes its
                      own version into every Parquet footer.

  fingerprint.sha256  a hash of the content. Answers "is this the same data".
                      Tables are hashed as the bytes of their written files,
                      which are byte-identical on any platform; sensor files are
                      hashed as frame contents, which survives both the Parquet
                      version and a conversion to CSV.

Usage
    python verify.py --dataset .
    python verify.py --dataset . --quick     # tables only, skips 389 MB of sensors
    python verify.py --dataset . --write     # rewrite both files from the package

--write is the last step of making a release, after the derived tables, the
protocol and the sample exist: it recomputes checksums.sha256 over every
published data file and rewrites fingerprint.sha256. Without it the manifest
written during conversion covers only what existed at that moment.

Exit status is 0 when everything matches and 1 when anything does not, so this
can sit in a release pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

try:
    import pandas as pd
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(f"Missing dependency: {exc.name}") from exc

TABLES = [("participants", "participants.csv"),
          ("devices", "devices.csv"),
          ("sessions", "sessions.csv"),
          ("key_events", "key_events.csv.gz")]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def frame_digest(df) -> str:
    """Must stay identical to _frame_digest in convert.py."""
    h = hashlib.sha256()
    for col in df.columns:
        a = df[col].to_numpy()
        h.update(str(col).encode("utf-8"))
        if a.dtype.kind in "biufc":
            h.update(a.dtype.str.encode("utf-8"))
            h.update(a.tobytes())
        else:
            h.update(b"txt")
            h.update("\x00".join("" if v is None else str(v)
                                 for v in a).encode("utf-8"))
    return h.hexdigest()


def read_manifest(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, name = line.partition("  ")
        out[name.strip().replace("\\", "/")] = digest
    return out


PUBLISHED = ("data", "splits", "sample")


def published_files(dataset: Path) -> list[Path]:
    out = []
    for folder in PUBLISHED:
        base = dataset / folder
        if base.exists():
            out += [p for p in base.rglob("*") if p.is_file()]
    return sorted(out)


def check_checksums(dataset: Path) -> list[str]:
    manifest = read_manifest(dataset / "checksums.sha256")
    problems = []
    present = {p.relative_to(dataset).as_posix()
               for p in published_files(dataset)}
    for name, digest in manifest.items():
        path = dataset / name
        if not path.exists():
            problems.append(f"missing file: {name}")
            continue
        if file_sha256(path) != digest:
            problems.append(f"byte mismatch: {name}")
    for name in sorted(present - set(manifest)):
        problems.append(f"file not in the manifest: {name}")
    print(f"  checksums.sha256  {len(manifest)} entries, "
          f"{len(manifest) - len([p for p in problems if 'manifest' not in p])} verified")
    return problems


def check_fingerprint(dataset: Path, quick: bool) -> list[str]:
    published = read_manifest(dataset / "fingerprint.sha256")
    parts = []
    problems = []

    for name, fn in TABLES:
        digest = file_sha256(dataset / "data" / fn)
        parts.append((name, digest))
        if name in published and published[name] != digest:
            problems.append(f"table content differs: {name}")

    if quick:
        print("  fingerprint       tables only, sensors skipped (--quick),")
        print("                    so the overall value is not checked")
        return problems

    sens = hashlib.sha256()
    files = sorted((dataset / "data" / "sensors").glob("*.parquet")) or \
        sorted((dataset / "data" / "sensors").glob("*.csv.gz"))
    for f in files:
        sid = f.name.split(".")[0]
        df = pd.read_parquet(f) if f.suffix == ".parquet" else pd.read_csv(f)
        sens.update(f"{sid} {frame_digest(df)}\n".encode("utf-8"))
    parts.append(("sensors", sens.hexdigest()))
    if "sensors" in published and published["sensors"] != sens.hexdigest():
        problems.append(f"sensor content differs over {len(files)} files")

    overall = hashlib.sha256()
    for name, digest in parts:
        overall.update(f"{name} {digest}\n".encode("utf-8"))
    total = overall.hexdigest()
    print(f"  fingerprint       {total}")
    if "overall" in published:
        if published["overall"] == total:
            print("                    matches the published value")
        else:
            problems.append("overall fingerprint differs from the published value")
    return problems


def write_fingerprint(dataset: Path) -> str:
    """
    Recompute fingerprint.sha256 from the package, keeping the header the
    conversion wrote: the definition lives in convert.py and is repeated here
    only so that a release can be hashed without the raw archives.

    The value that was in the file is read first and reported, because a check
    run after a rewrite compares the file against itself and can only pass. The
    line printed here is the only one that says anything.
    """
    target = dataset / "fingerprint.sha256"
    before = read_manifest(target).get("overall") if target.exists() else None

    parts = [(name, file_sha256(dataset / "data" / fn)) for name, fn in TABLES]
    sens = hashlib.sha256()
    files = sorted((dataset / "data" / "sensors").glob("*.parquet")) or \
        sorted((dataset / "data" / "sensors").glob("*.csv.gz"))
    for f in files:
        sid = f.name.split(".")[0]
        df = pd.read_parquet(f) if f.suffix == ".parquet" else pd.read_csv(f)
        sens.update(f"{sid} {frame_digest(df)}\n".encode("utf-8"))
    parts.append(("sensors", sens.hexdigest()))
    overall = hashlib.sha256()
    for name, digest in parts:
        overall.update(f"{name} {digest}\n".encode("utf-8"))
    total = overall.hexdigest()

    header = [l for l in (target.read_text(encoding="utf-8").splitlines()
                          if target.exists() else []) if l.startswith("#")]
    if not header:
        header = ["# Content fingerprint of the published package."]
    body = header + [""] + [f"{d}  {n}" for n, d in parts] + ["", f"{total}  overall", ""]
    target.write_text("\n".join(body), encoding="utf-8", newline="\n")
    print(f"  fingerprint.sha256 rewritten, {len(files)} sensor files")
    if before is None:
        print("                     no previous value to compare with")
    elif before == total:
        print(f"                     unchanged: {total}")
    else:
        print(f"                     CHANGED from {before}")
        print(f"                                to {total}")
        print("                     the data are not what they were; find out why")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--quick", action="store_true",
                    help="skip the sensor files")
    ap.add_argument("--write", action="store_true",
                    help="rewrite checksums.sha256 and fingerprint.sha256")
    args = ap.parse_args()

    if args.write:
        lines = []
        for path in published_files(args.dataset):
            name = path.relative_to(args.dataset).as_posix()
            lines.append(f"{file_sha256(path)}  {name}")
        (args.dataset / "checksums.sha256").write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(f"  checksums.sha256  rewritten, {len(lines)} files")
        write_fingerprint(args.dataset)

    problems = []
    if (args.dataset / "checksums.sha256").exists():
        problems += check_checksums(args.dataset)
    else:
        print("  checksums.sha256  absent, skipped")
    if (args.dataset / "fingerprint.sha256").exists():
        problems += check_fingerprint(args.dataset, args.quick)
    else:
        print("  fingerprint.sha256 absent, skipped")

    if problems:
        print("\nproblems:")
        for p in problems:
            print(f"  ! {p}")
        sys.exit(1)
    print("\neverything checks out")


if __name__ == "__main__":
    main()
