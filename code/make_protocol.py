#!/usr/bin/env python3
"""
Build the fixed verification protocol of the KDUA-Mobile dataset.

Writes splits/verification_protocol.json: which sessions enrol a person, which
session is the probe, and every pair to be scored, labelled by what kind of
comparison it is. The point of fixing it is that two papers quoting an error
rate on this dataset should be quoting the same experiment.

Usage
    python make_protocol.py --dataset dataset/

Design decisions, each of which costs something and is therefore stated:

* Only the transcription task is used. All participants typed the same 89
  characters, so two sessions are comparable without aligning different texts.
  The fixed phrase is 16 characters, too short for a per-digraph template; the
  free text has no key identity at all.

* The unit of enrolment is a (person, device) record, not a person. The same
  person on another phone is a different record, deliberately, because the
  cross-device comparison is one of the things this dataset exists to measure.

* Two sessions enrol, one probes. Every record has exactly three transcription
  sessions, one per condition (sitting, standing, on a surface). The probe is
  the third session in the recorded order and the other two enrol, so a probe
  is always a condition the template has not seen. That is the hard version of
  the task and the honest one: a template trained on all three conditions and
  tested on one of them would flatter every method applied to it.

* Pairs are enumerated exhaustively, not sampled, so no random seed enters the
  protocol at all. The kinds are kept apart because they do not mean the same
  thing:

  genuine_same_device    the same person, the same phone
  genuine_cross_device   the same person, a different phone of theirs
  impostor_same_device   a different person, the same phone. The interesting
                         one: hardware is held constant, so the error rate is
                         about the person
  impostor_cross_device  a different person on a different phone, which is the
                         usual benchmark pair and the one that flatters a
                         system, because it can be won on the device alone

* Person-level partition into dev and eval halves, for anyone fitting anything.
  A person appears in one half only, with their records and both their devices.
  Splitting by session or by record would leak.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import pandas as pd
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(f"Missing dependency: {exc.name}") from exc

TASK = "transcribe_ua"
# The researcher's own two phones. Any record on them is a borrowed device
# whatever the questionnaire says; two participants ticked "own" by mistake.
REFERENCE_DEVICES = ["d_f3bbcafe5e0a", "d_f41461b5266d"]


def build(dataset: Path) -> dict:
    s = pd.read_csv(dataset / "data" / "sessions.csv")
    p = pd.read_csv(dataset / "data" / "participants.csv")

    t = s[(s["task_code"] == TASK) & (s["guided_step"].between(2, 6))]
    t = t.sort_values(["participant_id", "guided_step"], kind="mergesort")

    enrol, probe, skipped = {}, {}, []
    counts = t.groupby("participant_id").size()
    # Every participant record of the dataset is considered, including one that
    # has no transcription session left at all after cleaning. Iterating the
    # groups alone would drop it in silence.
    for pid in sorted(p["participant_id"]):
        sids = list(t.loc[t["participant_id"] == pid, "session_id"])
        if len(sids) < 3:
            skipped.append({"participant_id": pid,
                            "transcription_sessions": len(sids)})
            continue
        enrol[pid] = sids[:2]
        probe[pid] = sids[2]
    del counts

    rec = p.set_index("participant_id")
    records = {
        pid: {
            "person_id": rec.at[pid, "person_id"],
            "device_id": rec.at[pid, "device_id"],
            "own_device": "borrowed" if rec.at[pid, "device_id"] in REFERENCE_DEVICES
                          else rec.at[pid, "own_device"],
        }
        for pid in enrol
    }

    pairs = {"genuine_same_device": [], "genuine_cross_device": [],
             "impostor_same_device": [], "impostor_cross_device": []}
    for a in sorted(records):          # template record
        for b in sorted(records):      # probe record
            same_person = records[a]["person_id"] == records[b]["person_id"]
            same_device = records[a]["device_id"] == records[b]["device_id"]
            if a == b:
                pairs["genuine_same_device"].append([a, b])
            elif same_person:
                pairs["genuine_cross_device"].append([a, b])
            elif same_device:
                pairs["impostor_same_device"].append([a, b])
            else:
                pairs["impostor_cross_device"].append([a, b])

    # Person-level halves. Ordered by person id, alternating, so that the two
    # halves hold a similar share of the people who used two devices.
    people = sorted({r["person_id"] for r in records.values()})
    multi = sorted({r["person_id"] for r in records.values()
                    if sum(1 for x in records.values()
                           if x["person_id"] == r["person_id"]) > 1})
    single = [x for x in people if x not in multi]
    dev, ev = [], []
    for i, person in enumerate(multi):
        (dev if i % 2 == 0 else ev).append(person)
    for i, person in enumerate(single):
        (dev if i % 2 == 0 else ev).append(person)

    fingerprint = ""
    fp = dataset / "fingerprint.sha256"
    if fp.exists():
        for line in fp.read_text(encoding="utf-8").splitlines():
            if line.endswith("overall"):
                fingerprint = line.split()[0]

    return {
        "name": "KDUA-Mobile verification protocol",
        "version": "1.0",
        "dataset_fingerprint": fingerprint,
        "task": TASK,
        "built_by": "code/make_protocol.py",
        "rules": {
            "unit": "(person, device) record",
            "enrolment": "the first two transcription sessions in recorded order",
            "probe": "the third transcription session, a condition unseen by the template",
            "pairs": "exhaustive over records, no sampling",
            "split": "person level; a person is in one half only",
        },
        "records": records,
        "enrolment_sessions": enrol,
        "probe_sessions": probe,
        "records_skipped": skipped,
        "person_partition": {"dev": dev, "eval": ev},
        "pairs": pairs,
        "counts": {k: len(v) for k, v in pairs.items()} | {
            "records": len(records),
            "people": len(people),
            "people_on_two_devices": len(multi),
            "records_own_device": sum(1 for r in records.values()
                                      if r["own_device"] == "own"),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True)
    args = ap.parse_args()

    proto = build(args.dataset)
    out = args.dataset / "splits"
    out.mkdir(parents=True, exist_ok=True)
    target = out / "verification_protocol.json"
    # newline="\n" so the file is byte-identical on Windows and on Linux: its
    # hash is in checksums.sha256.
    target.write_text(json.dumps(proto, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8", newline="\n")

    for k, v in proto["counts"].items():
        print(f"  {k:24s} {v}")
    if proto["records_skipped"]:
        print(f"  records skipped          {len(proto['records_skipped'])}"
              f"  {proto['records_skipped']}")
    print(f"written to {target}")


if __name__ == "__main__":
    main()
