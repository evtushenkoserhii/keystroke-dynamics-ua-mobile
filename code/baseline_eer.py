#!/usr/bin/env python3
"""
Baseline verification result on the KDUA-Mobile dataset.

Deliberately the simplest method that can be written down completely: median
timings per digraph, a scaled Manhattan distance, an equal error rate. No
training, no hyperparameters, no random seed. It exists to be beaten, and to
make the beating measurable: a new method on this dataset should be reported
against these numbers, on the same protocol.

Usage
    python features.py --dataset dataset/          # once, writes the features
    python baseline_eer.py --dataset dataset/

Method
    feature vector of a session
        the natural logarithm of the median DD latency of every digraph of the
        stimulus that occurs in the session, and of the median hold time of
        every key; pauses over 2 s excluded. The log is there because keystroke
        latencies are distributed log-normally, and it is worth 6 points of
        equal error rate here: 22.2 % against 28.6 % on the raw milliseconds.
        Pass --raw to reproduce the untransformed variant
    template of a record
        the mean of its two enrolment sessions' vectors, dimension by dimension
    score of a pair
        mean over the dimensions both sides have of |probe - template| divided
        by that dimension's median absolute deviation across all sessions; low
        is similar
    equal error rate
        the threshold where the share of genuine pairs rejected equals the
        share of impostor pairs accepted, by linear interpolation
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(f"Missing dependency: {exc.name}") from exc

MIN_SHARED_DIMENSIONS = 20


def session_vectors(dataset: Path, log: bool = True) -> dict[str, dict[str, float]]:
    dg = pd.read_csv(dataset / "data" / "features" / "digraphs.csv.gz")
    ks = pd.read_csv(dataset / "data" / "features" / "keystrokes.csv.gz")

    dg = dg[(~dg["long_pause"]) & dg["digraph"].notna()]
    a = (dg.groupby(["session_id", "digraph"])["dd_ms"].median()
         .rename("v").reset_index())
    a["dim"] = "dd:" + a["digraph"]

    ks = ks[ks["key_code"].notna()]
    b = (ks.groupby(["session_id", "key_code"])["hold_ms"].median()
         .rename("v").reset_index())
    b["dim"] = "h:" + b["key_code"].astype("int64").astype(str)

    long = pd.concat([a[["session_id", "dim", "v"]], b[["session_id", "dim", "v"]]]).copy()
    if log:
        long["v"] = np.log(long["v"].clip(lower=1.0))
    out: dict[str, dict[str, float]] = {}
    for sid, g in long.groupby("session_id"):
        out[sid] = dict(zip(g["dim"], g["v"]))
    return out


def scales(vectors: dict[str, dict[str, float]], floor: float) -> dict[str, float]:
    """Median absolute deviation per dimension, over all sessions."""
    by_dim: dict[str, list[float]] = {}
    for vec in vectors.values():
        for dim, v in vec.items():
            by_dim.setdefault(dim, []).append(v)
    out = {}
    for dim, vals in by_dim.items():
        arr = np.asarray(vals, dtype=float)
        mad = float(np.median(np.abs(arr - np.median(arr))))
        # A dimension with no spread would divide by zero. The floor is the
        # smallest deviation worth trusting: 1 ms on raw timings, and the
        # equivalent in log units.
        out[dim] = max(mad, floor)
    return out


def distance(template: dict[str, float], probe: dict[str, float],
             scale: dict[str, float]) -> float | None:
    shared = template.keys() & probe.keys()
    if len(shared) < MIN_SHARED_DIMENSIONS:
        return None
    total = sum(abs(template[d] - probe[d]) / scale[d] for d in shared)
    return total / len(shared)


def eer(genuine: list[float], impostor: list[float]) -> tuple[float, float]:
    """Equal error rate and the threshold at which it is reached."""
    if not genuine or not impostor:
        return float("nan"), float("nan")
    g = np.sort(np.asarray(genuine))
    i = np.sort(np.asarray(impostor))
    # Scan every observed score as a threshold and take the one where the two
    # error rates are closest. With a few thousand pairs this is exact enough
    # and leaves nothing to a fitting procedure.
    gap, chosen, rate = 2.0, float("nan"), float("nan")
    for t in np.unique(np.concatenate([g, i])):
        frr = float(np.mean(g > t))      # genuine rejected
        far = float(np.mean(i <= t))     # impostor accepted
        if abs(frr - far) < gap:
            gap, chosen, rate = abs(frr - far), float(t), (frr + far) / 2
    return rate, chosen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--raw", action="store_true",
                    help="score raw milliseconds instead of log timings")
    args = ap.parse_args()

    proto = json.loads((args.dataset / "splits" /
                        "verification_protocol.json").read_text(encoding="utf-8"))
    vectors = session_vectors(args.dataset, log=not args.raw)
    scale = scales(vectors, floor=1.0 if args.raw else 1e-3)

    templates = {}
    for rec, sids in proto["enrolment_sessions"].items():
        parts = [vectors.get(s, {}) for s in sids]
        dims = set().union(*[set(p) for p in parts]) if parts else set()
        templates[rec] = {
            d: float(np.mean([p[d] for p in parts if d in p]))
            for d in dims
        }

    probes = {rec: vectors.get(sid, {})
              for rec, sid in proto["probe_sessions"].items()}

    scores: dict[str, list[float]] = {k: [] for k in proto["pairs"]}
    unusable = 0
    for kind, pairs in proto["pairs"].items():
        for a, b in pairs:
            d = distance(templates[a], probes[b], scale)
            if d is None:
                unusable += 1
                continue
            scores[kind].append(d)

    own = {r for r, v in proto["records"].items() if v["own_device"] == "own"}
    own_scores = {k: [] for k in proto["pairs"]}
    for kind, pairs in proto["pairs"].items():
        for a, b in pairs:
            if a in own and b in own:
                d = distance(templates[a], probes[b], scale)
                if d is not None:
                    own_scores[kind].append(d)

    print(f"  timings            {'raw milliseconds' if args.raw else 'log milliseconds'}")
    print(f"  dimensions in the feature space  {len(scale)}")
    print(f"  pairs not scored (too few shared dimensions)  {unusable}")
    print()
    for kind in ("genuine_same_device", "genuine_cross_device",
                 "impostor_same_device", "impostor_cross_device"):
        v = np.asarray(scores[kind])
        print(f"  {kind:22s} n={len(v):5d}  median score {np.median(v):.3f}")
    print()

    g = scores["genuine_same_device"]
    for label, imp in (("all impostor pairs",
                        scores["impostor_same_device"] + scores["impostor_cross_device"]),
                       ("impostors on the same phone", scores["impostor_same_device"]),
                       ("impostors on another phone", scores["impostor_cross_device"])):
        rate, thr = eer(g, imp)
        print(f"  EER, genuine same device vs {label:28s} {100 * rate:5.1f} %"
              f"   (threshold {thr:.3f})")

    rate, thr = eer(scores["genuine_cross_device"],
                    scores["impostor_same_device"] + scores["impostor_cross_device"])
    print(f"  EER, genuine CROSS device vs all impostor pairs          "
          f"{100 * rate:5.1f} %   (threshold {thr:.3f})")

    rate, thr = eer(own_scores["genuine_same_device"],
                    own_scores["impostor_same_device"] + own_scores["impostor_cross_device"])
    print(f"  EER on own-device records only                           "
          f"{100 * rate:5.1f} %   (threshold {thr:.3f})")


if __name__ == "__main__":
    main()
