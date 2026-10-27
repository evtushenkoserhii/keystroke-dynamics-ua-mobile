#!/usr/bin/env python3
"""
Build sample/ from the full package: three sessions of one participant, in the
same layout as data/, so that the repository can be understood without
downloading 389 MB.

Usage
    python make_sample.py --dataset . --participant p_7fc74a3a3c5f

Why one participant and these three sessions: they are steps 1, 2 and 3 of the
guided sequence, which covers all three tasks and both keyboard layouts, on a
phone with a working gyroscope, in the newest exporter version. Everything a
reader needs to see the shape of the data is there, and nothing in the sample
is a special case.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

try:
    import pandas as pd
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(f"Missing dependency: {exc.name}") from exc

CSV = {"lineterminator": "\n"}
GZ = {"method": "gzip", "mtime": 0}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--participant", default="p_7fc74a3a3c5f")
    ap.add_argument("--steps", default="1,2,3")
    args = ap.parse_args()

    steps = [int(x) for x in args.steps.split(",")]
    data = args.dataset / "data"
    out = args.dataset / "sample"
    (out / "sensors").mkdir(parents=True, exist_ok=True)

    s = pd.read_csv(data / "sessions.csv")
    p = pd.read_csv(data / "participants.csv")
    d = pd.read_csv(data / "devices.csv")
    k = pd.read_csv(data / "key_events.csv.gz")

    rec = p[p["participant_id"] == args.participant]
    if rec.empty:
        raise SystemExit(f"no such participant record: {args.participant}")
    sess = s[(s["participant_id"] == args.participant) &
             (s["guided_step"].isin(steps))]
    if len(sess) != len(steps):
        raise SystemExit(f"expected {len(steps)} sessions, found {len(sess)}")
    sids = list(sess["session_id"])

    rec.to_csv(out / "participants.csv", index=False, **CSV)
    d[d["device_id"].isin(set(rec["device_id"]))].to_csv(
        out / "devices.csv", index=False, **CSV)
    sess.to_csv(out / "sessions.csv", index=False, **CSV)
    k[k["session_id"].isin(set(sids))].to_csv(
        out / "key_events.csv.gz", index=False, compression=GZ, **CSV)

    total = 0
    for sid in sids:
        src = data / "sensors" / f"{sid}.parquet"
        if not src.exists():
            src = data / "sensors" / f"{sid}.csv.gz"
        if not src.exists():
            raise SystemExit(f"no sensor file for {sid}")
        shutil.copy2(src, out / "sensors" / src.name)
        total += src.stat().st_size

    rows = int(sess["sensor_sample_count"].sum())
    events = int(k["session_id"].isin(set(sids)).sum())
    print(f"  sessions {len(sids)}  key events {events}  sensor rows {rows}")
    print(f"  sensors  {total / 1e6:.2f} MB")
    print(f"written to {out}")


if __name__ == "__main__":
    main()
