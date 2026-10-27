#!/usr/bin/env python3
"""
Reference feature computation for the KDUA-Mobile dataset.

Produces two tables from data/key_events.csv.gz and data/sessions.csv:

  data/features/keystrokes.csv.gz  one row per key press: hold time and the
                                   geometry of the touch that produced it
  data/features/digraphs.csv.gz    one row per adjacent pair of presses: the
                                   four latencies DD, UD, UU, DU

Nothing here is the only right way to compute these. The point of publishing it
is that a number quoted from this dataset can be traced to a definition.

Usage
    python -m pip install -r requirements.txt
    python features.py --dataset dataset/

Definitions, with H for hold and the two keys of a pair written 1 and 2:

    hold        up1 - down1                 how long the key was held
    DD          down2 - down1               press to press, the usual "flight"
    UD          down2 - up1                 release to press; negative when the
                                            second key goes down before the
                                            first comes up, which is normal in
                                            fast two-thumb typing
    UU          up2 - up1
    DU          up2 - down1                 the whole pair, hold included

All four are in milliseconds, derived from t_rel_ns, which is nanoseconds since
the start of the session on a single clock.

Order matters: events are ordered by the sequence number the collector assigned
at the moment of recording, never by timestamp. A press and its release are
paired by key position within the session, not by proximity in time.
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    import pandas as pd
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        f"Missing dependency: {exc.name}.\n"
        "    python -m pip install -r requirements.txt"
    ) from exc

NS_PER_MS = 1_000_000.0

# A pair of presses further apart than this is not a digraph but a pause: the
# participant stopped, read the next word, or was interrupted. Kept as a column
# rather than dropped, so that the threshold stays the reader's choice.
LONG_PAUSE_MS = 2000.0


def load(dataset: Path):
    s = pd.read_csv(dataset / "data" / "sessions.csv")
    k = pd.read_csv(dataset / "data" / "key_events.csv.gz",
                    dtype_backend="numpy_nullable")
    return s, k


def keystrokes(k: pd.DataFrame) -> pd.DataFrame:
    """One row per press, with its hold time."""
    k = k.sort_values(["session_id", "seq"], kind="mergesort")
    downs = k[k["action"] == "down"].copy()
    ups = k[k["action"] == "up"].copy()

    # Pair the nth press of a key with the nth release of that key inside the
    # session. Pairing by nearest timestamp breaks exactly where the data are
    # most interesting: when two keys are held at once.
    for frame in (downs, ups):
        frame["occurrence"] = frame.groupby(
            ["session_id", "key_class", "key_row", "key_col"],
            dropna=False).cumcount()

    keys = ["session_id", "key_class", "key_row", "key_col", "occurrence"]
    out = downs.merge(
        ups[keys + ["t_rel_ns", "seq"]], on=keys, how="inner",
        suffixes=("_down", "_up"))

    out["hold_ms"] = (out["t_rel_ns_up"] - out["t_rel_ns_down"]) / NS_PER_MS
    out = out.rename(columns={"t_rel_ns_down": "t_rel_ns",
                              "seq_down": "seq_down", "seq_up": "seq_up"})
    cols = ["session_id", "seq_down", "seq_up", "t_rel_ns", "hold_ms",
            "key_class", "key_row", "key_col", "key_code",
            "offset_x", "offset_y", "touch_size", "pressure",
            "touch_major", "touch_minor", "key_w", "key_h"]
    out = out[[c for c in cols if c in out.columns]]
    # A negative hold is impossible and would mean the pairing failed.
    bad = int((out["hold_ms"] < 0).sum())
    if bad:
        raise SystemExit(f"{bad} presses paired with an earlier release: "
                         "the ordering assumption is wrong, stop and look")
    return out.sort_values(["session_id", "seq_down"], kind="mergesort")


def digraphs(ks: pd.DataFrame) -> pd.DataFrame:
    """One row per adjacent pair of presses within a session."""
    a = ks.sort_values(["session_id", "seq_down"], kind="mergesort").copy()
    b = a.shift(-1)
    same = a["session_id"] == b["session_id"]

    d = pd.DataFrame({
        "session_id": a["session_id"],
        "seq_down_1": a["seq_down"],
        "key_class_1": a["key_class"],
        "key_class_2": b["key_class"],
        "key_code_1": a.get("key_code"),
        "key_code_2": b.get("key_code"),
        "hold_1_ms": a["hold_ms"],
        "hold_2_ms": b["hold_ms"],
        "dd_ms": (b["t_rel_ns"] - a["t_rel_ns"]) / NS_PER_MS,
        "ud_ms": (b["t_rel_ns"] - a["t_rel_ns"]) / NS_PER_MS - a["hold_ms"],
    })
    d["uu_ms"] = d["dd_ms"] + d["hold_2_ms"] - d["hold_1_ms"]
    d["du_ms"] = d["dd_ms"] + d["hold_2_ms"]
    d = d[same].copy()
    d["long_pause"] = d["dd_ms"] > LONG_PAUSE_MS
    # The digraph's identity, usable only where key identity is published.
    d["digraph"] = [
        f"{int(x)}_{int(y)}" if pd.notna(x) and pd.notna(y) else pd.NA
        for x, y in zip(d["key_code_1"], d["key_code_2"])
    ]
    return d


def report(ks: pd.DataFrame, dg: pd.DataFrame, s: pd.DataFrame) -> None:
    print(f"  presses with a hold time   {len(ks)}")
    print(f"  digraphs                   {len(dg)}  "
          f"({int(dg['long_pause'].sum())} longer than {LONG_PAUSE_MS:.0f} ms)")
    print(f"  sessions covered           {ks['session_id'].nunique()} of {len(s)}")
    h = ks["hold_ms"]
    print(f"  hold ms       median {h.median():6.1f}   p5 {h.quantile(.05):6.1f}"
          f"   p95 {h.quantile(.95):6.1f}")
    for col in ("dd_ms", "ud_ms", "uu_ms", "du_ms"):
        v = dg.loc[~dg["long_pause"], col]
        print(f"  {col:9s}   median {v.median():6.1f}   p5 {v.quantile(.05):6.1f}"
              f"   p95 {v.quantile(.95):6.1f}")
    neg = int((dg.loc[~dg["long_pause"], "ud_ms"] < 0).sum())
    print(f"  overlapping pairs (UD < 0) {neg} of {int((~dg['long_pause']).sum())}"
          f"  = {100 * neg / max(1, int((~dg['long_pause']).sum())):.1f} %")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True,
                    help="the dataset folder, the one holding data/")
    args = ap.parse_args()

    s, k = load(args.dataset)
    ks = keystrokes(k)
    dg = digraphs(ks)

    out = args.dataset / "data" / "features"
    out.mkdir(parents=True, exist_ok=True)
    # Same determinism as the main tables: an explicit line terminator and no
    # timestamp in the gzip header, so the files are comparable across machines.
    gz = {"method": "gzip", "mtime": 0}
    ks.to_csv(out / "keystrokes.csv.gz", index=False, lineterminator="\n",
              compression=gz)
    dg.to_csv(out / "digraphs.csv.gz", index=False, lineterminator="\n",
              compression=gz)
    report(ks, dg, s)
    print(f"written to {out}")


if __name__ == "__main__":
    main()
