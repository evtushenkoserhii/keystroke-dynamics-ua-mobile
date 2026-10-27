#!/usr/bin/env python3
"""
Convert raw Keystroke Collector exports into the published dataset format.

Input   one or more keystroke_corpus_*.zip archives produced by the app.
        Each archive holds one JSON file per session plus manifest.json.
Output  a directory of CSV and Parquet files, plus SHA-256 checksums.

The archives are cumulative: a phone whose owner pressed "send" twice produced
two archives, the later containing the earlier. This script keeps the newest
archive per device and ignores the rest, so pointing it at the whole intake
folder is the intended usage. --input is searched recursively, so a tree of
one folder per collection day works as well as a flat directory.

Usage
    python -m pip install -r requirements.txt
    python convert.py --input intake/ --output dataset/ [--no-parquet]

Dependencies: pandas (required) and pyarrow (required for the Parquet sensor
files). With --no-parquet the sensors are written as gzipped CSV and pyarrow
is not needed. See requirements.txt next to this file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

try:
    import pandas as pd
except ModuleNotFoundError as exc:  # pragma: no cover - startup diagnostics
    raise SystemExit(
        "Missing dependency: {0}.\n"
        "Install it first:\n"
        "    python -m pip install -r requirements.txt\n"
        "or directly:\n"
        "    python -m pip install pandas pyarrow\n"
        "(pyarrow is needed only without --no-parquet)".format(exc.name)
    ) from exc

ACTION_NAMES = {0: "down", 1: "up", 2: "cancel"}

# The collector writes -1 where a field is deliberately blank (CLASS_ONLY mode)
# or unavailable. Left as -1 in a numeric column it is silently averaged into
# features by the first person who tries, so it becomes a real null here.
BLANKABLE = [
    "key_row", "key_col", "key_code",
    "touch_x", "touch_y", "offset_x", "offset_y", "key_w", "key_h",
]

SENSOR_COLUMNS = ["t_nanos", "t_recv_nanos", "x", "y", "z", "w", "accuracy"]

# Written-file determinism, so that two people converting the same archives on
# different operating systems can compare their checksum files at all.
CSV_PARAMS = {"lineterminator": "\n"}
GZIP_PARAMS = {"method": "gzip", "mtime": 0}

# Row and column order of the written tables. Without this the order follows
# whichever archive happened to be read first: pd.DataFrame(list_of_dicts) takes
# its columns from the first dict, so a session recorded with an older schema
# arriving first silently reshuffled sessions.csv. Two correct runs then differ
# in every line while holding exactly the same data.
TABLE_ORDER = {
    "participants": (
        ["participant_id", "person_id", "device_id", "age_group", "gender",
         "handedness", "typing_experience", "own_device", "consent_version"],
        ["participant_id"],
    ),
    "devices": (
        ["device_id", "manufacturer", "model", "android_release", "api_level",
         "screen_w_px", "screen_h_px", "density_dpi", "sensor_hardware",
         "best_sensor_delay_us", "screen_diag_in"],
        ["device_id"],
    ),
    "sessions": (
        ["session_id", "participant_id", "device_id", "task_code",
         "stimulus", "stimulus_sha1", "privacy_mode", "layout", "posture",
         "hold_style", "guided", "guided_step", "guided_order",
         "started_at_utc", "started_nanos", "duration_ms",
         "requested_sensor_period_us", "uptime_to_realtime_offset_nanos",
         "key_down_count", "caret_moves", "key_event_count",
         "sensor_sample_count", "schema_version", "app_version",
         "kb_view_w_px", "kb_view_h_px", "power_save_mode",
         "thermal_start", "thermal_end", "battery_start_pct",
         "battery_end_pct", "charging", "quality", "gyro_samples",
         "gyro_active_samples", "external_input", "dropped_key_events",
         "motion_active_fraction", "typed_chars", "quality_flag"],
        ["participant_id", "started_nanos", "session_id"],
    ),
    "key_events": (
        ["session_id", "seq", "action", "key_class", "key_row", "key_col",
         "key_code", "t_nanos", "touch_x", "touch_y", "offset_x", "offset_y",
         "touch_major", "touch_minor", "touch_size", "pressure", "pointer_id",
         "key_w", "key_h", "t_rel_ns"],
        ["session_id", "seq"],
    ),
}


# ---------------------------------------------------------------- reading

def scan_archives(input_dir: Path) -> list[tuple]:
    """
    First pass: decide which archive to use for each phone without parsing it.

    Reads only the manifest and the single smallest session of each archive —
    enough for the device id and the session count. Parsing every archive in
    full, as the previous version did, meant holding the whole collection in
    memory at once; at five hundred sessions that is several gigabytes and the
    process is killed before it writes anything.

    Supersession is decided by the number of sessions, not by file time: a
    cumulative export can only grow, and file timestamps survive copying
    between machines unreliably.
    """
    found: list[tuple] = []

    # Recursive: the intake is normally kept as one folder per collection day,
    # so --input is pointed at the tree, not at a single flat directory. A file
    # that happens to sit in two places is harmless, because supersession below
    # keeps one archive per device id.
    for path in sorted(input_dir.rglob("*.zip")):
        try:
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.namelist()
                         if n.endswith(".json") and not n.endswith("manifest.json")]
                if not names:
                    print(f"  ! {path.name}: no sessions, skipped")
                    continue
                manifest = {}
                if "manifest.json" in z.namelist():
                    manifest = json.loads(z.read("manifest.json"))
                # The smallest session is the cheapest place to find the device id.
                probe = min(names, key=lambda n: z.getinfo(n).file_size)
                doc = json.loads(z.read(probe))
        except (zipfile.BadZipFile, json.JSONDecodeError, KeyError) as e:
            print(f"  ! {path.name}: unreadable ({e.__class__.__name__}), skipped")
            continue

        did = (doc.get("session", {}) or {}).get("device_id") or f"file:{path.name}"
        found.append((path, did, len(names), manifest.get("app_version", "")))

    best: dict[str, tuple] = {}
    for rec in found:
        if rec[1] not in best or rec[2] > best[rec[1]][2]:
            best[rec[1]] = rec

    dropped = len(found) - len(best)
    if dropped:
        print(f"  {dropped} superseded archive(s) ignored")
    return list(best.values())


def iter_bundles(selected: list[tuple]):
    """
    Second pass: yield one archive at a time, its sessions lazily.

    The consumer must finish with a bundle before asking for the next one —
    which build_tables does — so at most one session document is alive.
    """
    for path, did, _count, app_version in selected:
        with zipfile.ZipFile(path) as z:
            names = sorted(n for n in z.namelist()
                           if n.endswith(".json") and not n.endswith("manifest.json"))

            def sessions(z=z, names=names):
                for name in names:
                    with z.open(name) as f:
                        yield json.load(f)

            yield {
                "path": path,
                "sessions": sessions(),
                "app_version": app_version,
                "device_id": did,
            }


# ---------------------------------------------------------------- tables

def _best_sensor_delay(hardware) -> int | None:
    """Smallest min_delay_us over all sensors, i.e. the fastest the device can go."""
    if not hardware:
        return None
    vals = [h.get("min_delay_us") for h in hardware if isinstance(h.get("min_delay_us"), int)]
    vals = [v for v in vals if v > 0]
    return min(vals) if vals else None


def _diagonal_in(dev: dict) -> float | None:
    w, h, dpi = dev.get("screen_w_px"), dev.get("screen_h_px"), dev.get("density_dpi")
    if not (w and h and dpi):
        return None
    return round(((w / dpi) ** 2 + (h / dpi) ** 2) ** 0.5, 2)


def build_tables(bundles: list[dict], sensor_writer=None) -> dict:
    """
    Build the published tables.

    `sensor_writer(session_id, frame)` is called for every session as soon as
    its sensor frame exists, and only the row count is kept afterwards. Holding
    all of them in memory is what the first full run died of: sixteen million
    rows spread over five hundred frames is several gigabytes, and the process
    was killed without writing anything. Streaming them out keeps the peak at
    one session.
    """
    participants: dict[str, dict] = {}
    devices: dict[str, dict] = {}
    sessions: list[dict] = []
    key_frames: list[pd.DataFrame] = []
    sensor_frames: dict = {}   # session_id -> frame, or row count when streamed

    for b in bundles:
        for doc in b["sessions"]:
            s = doc.get("session", {})
            p = doc.get("participant", {})
            d = doc.get("device", {})
            sid = s.get("session_id")
            if not sid:
                continue

            pid = s.get("participant_id", "")
            did = s.get("device_id") or b["device_id"]
            started = s.get("started_nanos")

            participants.setdefault(pid, {
                "participant_id": pid,
                "device_id": did,
                "link_code": p.get("link_code", ""),   # dropped after person_id
                "age_group": p.get("age_group", ""),
                "gender": p.get("gender", ""),
                "handedness": p.get("handedness", ""),
                "typing_experience": p.get("typing_experience", ""),
                "own_device": p.get("own_device", ""),
                "consent_version": p.get("consent_version", ""),
            })

            devices.setdefault(did, {
                "device_id": did,
                "manufacturer": d.get("manufacturer", ""),
                "model": d.get("model", ""),
                "android_release": d.get("android_release", ""),
                "api_level": d.get("api_level"),
                "screen_w_px": d.get("screen_w_px"),
                "screen_h_px": d.get("screen_h_px"),
                "density_dpi": d.get("density_dpi"),
                "sensor_hardware": json.dumps(
                    doc.get("sensor_hardware", []), ensure_ascii=False),
                # Fastest rate any sensor on this device can deliver. A real
                # phone reports a few milliseconds here; 200 ms across the
                # board is what an emulated sensor stack reports.
                "best_sensor_delay_us": _best_sensor_delay(doc.get("sensor_hardware")),
                # Physical screen diagonal in inches, for the same reason:
                # no phone is 7.7 inches at 240 dpi.
                "screen_diag_in": _diagonal_in(d),
            })

            row = dict(s)
            # Published to the day, not to the second. The exact clock time adds
            # nothing to any analysis - order within a sitting is in
            # guided_step, timing within a session is in t_rel_ns, and the
            # same-day pairing of two devices survives a date - while for
            # someone who was in the room it is one more key to join a record
            # to a person ("who was typing at 12:07").
            if row.get("started_at_utc"):
                row["started_at_utc"] = str(row["started_at_utc"])[:10]
            row["device_id"] = did
            row["schema_version"] = doc.get("schema_version")
            row["app_version"] = b["app_version"]
            # Keyboard window lives in the device block of the export but
            # belongs to the session: it changes with orientation and insets.
            row["kb_view_w_px"] = d.get("kb_view_w_px")
            row["kb_view_h_px"] = d.get("kb_view_h_px")
            for k, v in (doc.get("power") or {}).items():
                row[k if k.startswith(("power", "thermal", "battery", "charging"))
                    else f"power_{k}"] = v
            row["quality"] = json.dumps(doc.get("quality", []), ensure_ascii=False)
            sessions.append(row)

            kf = _key_frame(doc, sid, started)
            if kf is not None:
                key_frames.append(kf)

            sf = _sensor_frame(doc, sid, started)
            if sf is not None:
                if sensor_writer is not None:
                    sensor_writer(sid, sf)
                    sensor_frames[sid] = len(sf)
                else:
                    sensor_frames[sid] = sf
                del sf

    sessions_df = pd.DataFrame(sessions)

    # Share of gyroscope samples that showed the device moving. Derived here so
    # that filtering on it never requires opening a sensor file. Undefined (NaN)
    # on devices without a gyroscope — one of the first nine was a Galaxy A15,
    # which has none, and a zero there would falsely read as "perfectly still".
    if {"gyro_samples", "gyro_active_samples"} <= set(sessions_df.columns):
        tot = pd.to_numeric(sessions_df["gyro_samples"], errors="coerce")
        act = pd.to_numeric(sessions_df["gyro_active_samples"], errors="coerce")
        sessions_df["motion_active_fraction"] = (act / tot).where(tot > 0)

    return {
        "participants": pd.DataFrame(participants.values()),
        "devices": pd.DataFrame(devices.values()),
        "sessions": sessions_df,
        "key_events": (pd.concat(key_frames, ignore_index=True)
                       if key_frames else pd.DataFrame()),
        "_sensors": sensor_frames,
    }


def _origin(started, *frames) -> int:
    """
    Session start on the sensor clock.

    Prefer the recorded value; fall back to the earliest observed timestamp for
    archives written before that field existed.
    """
    if isinstance(started, (int, float)) and started > 0:
        return int(started)
    candidates = [f["t_nanos"].min() for f in frames
                  if f is not None and not f.empty and "t_nanos" in f]
    return int(min(candidates)) if candidates else 0


def _key_frame(doc: dict, sid: str, started) -> pd.DataFrame | None:
    cols = doc.get("key_event_columns")
    rows = doc.get("key_events")
    if not cols or not rows:
        return None

    df = pd.DataFrame(rows, columns=cols)
    df.insert(0, "session_id", sid)

    if "action" in df:
        df["action"] = df["action"].map(ACTION_NAMES).fillna(df["action"].astype(str))

    if "t_nanos" in df:
        df["t_rel_ns"] = df["t_nanos"] - _origin(started, df)

    for c in BLANKABLE:
        if c in df:
            df[c] = df[c].where(df[c] != -1)

    # Without a nullable integer type, a single blank turns the whole column to
    # float and key codes are published as 1092.0 — technically correct, and
    # wrong in every downstream join.
    for c in ("key_row", "key_col", "key_code", "pointer_id", "seq"):
        if c in df:
            df[c] = df[c].astype("Int64")

    return df


def _sensor_frame(doc: dict, sid: str, started) -> pd.DataFrame | None:
    block = doc.get("sensors") or {}
    cols = doc.get("sensor_columns") or SENSOR_COLUMNS

    parts = []
    for name, rows in block.items():
        if not rows:
            continue
        part = pd.DataFrame(rows, columns=cols)
        part.insert(0, "sensor_name", name)
        parts.append(part)

    if not parts:
        return None

    df = pd.concat(parts, ignore_index=True)
    df.insert(0, "session_id", sid)
    # w is the quaternion scalar part for rotation_vector and unused elsewhere;
    # leaving zeros in it invites averaging a meaningless column.
    if "w" in df:
        df["w"] = df["w"].where(df["sensor_name"] == "rotation_vector")
    df["t_rel_ns"] = df["t_nanos"] - _origin(started, df)
    return df.sort_values(["sensor_name", "t_nanos"], ignore_index=True)


# ---------------------------------------------------------------- anonymising

# Numbers reserved for staff, never issued on cards: 100 for the organiser,
# 200 for the lecturer hosting the session. Their records are dropped for two
# reasons. Their sessions are demonstrations and equipment checks, and both had
# seen the stimulus beforehand, so the timing is not comparable with a participant
# reading it for the first time. More decisively, the ethics submission names
# first-year students as the participant category; staff records fall outside it.
ORGANISER_CODES = {"100", "200"}

# Sessions recorded under a participant record that was later re-used by
# somebody else.
#
# On 12.10 a student ran the sequence on the organiser's reference phone, but
# instead of "hand the phone to another person" — which mints a fresh
# participant — the existing profile was edited: the link code became 500 and
# the ownership flag flipped to "borrowed". The record therefore carries the
# organiser's twelve test sessions from 16.09 together with the student's six
# from 12.10, under one identity.
#
# The split is unambiguous because the dates do not overlap, so the earlier
# half is removed and the later half stays as the student. Listed explicitly
# rather than guessed by a rule: this is a single operator slip, not a pattern
# worth generalising.
PROFILE_REUSE_CUTOFFS = {
    "p_7aa0f9f49d83": "2026-10-01",   # keep sessions on or after this date
}


def assign_person_ids(participants: pd.DataFrame) -> pd.DataFrame:
    """
    Replace the classroom number with an opaque identifier.

    The number is what links one person across two phones, and it must survive;
    the number itself must not. While an attendance list exists anywhere, a
    published classroom number is a thread back to a name — an opaque label
    linking the same records is not.
    """
    if participants.empty:
        return participants

    df = participants.copy()
    codes = df.get("link_code", pd.Series("", index=df.index)).fillna("").astype(str).str.strip()

    # Numbering follows the sorted participant_id, not the order the archives
    # were read in. Otherwise the same corpus converted from a folder per day
    # and from one flat folder gives the same grouping under different labels,
    # and nobody can tell the two packages apart from the two person_id columns.
    groups: dict[str, list[str]] = {}
    for pid, code in zip(df["participant_id"].astype(str), codes):
        key = f"code:{code}" if code else f"solo:{pid}"
        groups.setdefault(key, []).append(pid)

    order = sorted(groups, key=lambda k: min(groups[k]))
    mapping = {}
    for n, key in enumerate(order, start=1):
        for pid in groups[key]:
            mapping[pid] = f"person_{n:04d}"

    df.insert(1, "person_id", df["participant_id"].astype(str).map(mapping))
    return df.drop(columns=["link_code"])


def drop_reused_profile_sessions(t: dict) -> dict:
    """Remove the earlier half of any participant record that was re-used."""
    s = t["sessions"]
    if s.empty or not PROFILE_REUSE_CUTOFFS:
        return t
    drop = set()
    for pid, cutoff in PROFILE_REUSE_CUTOFFS.items():
        rows = s[(s["participant_id"] == pid) &
                 (s["started_at_utc"].astype(str).str[:10] < cutoff)]
        drop |= set(rows["session_id"])
    if not drop:
        return t
    print(f"  re-used profile: {len(drop)} earlier session(s) dropped "
          f"from {len(PROFILE_REUSE_CUTOFFS)} record(s)")
    t["sessions"] = s.loc[~s["session_id"].isin(drop)].reset_index(drop=True)
    if not t["key_events"].empty:
        t["key_events"] = t["key_events"].loc[
            ~t["key_events"]["session_id"].isin(drop)].reset_index(drop=True)
    t["_sensors"] = {k: v for k, v in t["_sensors"].items() if k not in drop}
    return t


def drop_organiser(t: dict) -> dict:
    """
    Remove staff records, identified by the reserved numbers.

    Dropping by a reserved number rather than by hand is deliberate. An unnumbered
    record is ambiguous, since a participant may simply have left the field empty;
    a reserved number is not.
    """
    p = t["participants"]
    if p.empty or "link_code" not in p.columns:
        return t

    mask = p["link_code"].fillna("").astype(str).str.strip().isin(ORGANISER_CODES)
    if not mask.any():
        return t

    drop_ids = set(p.loc[mask, "participant_id"])
    sessions = t["sessions"]
    drop_sessions = set(sessions.loc[sessions["participant_id"].isin(drop_ids), "session_id"])

    print(f"  staff records dropped: {len(drop_ids)} participant(s), "
          f"{len(drop_sessions)} session(s)")

    t["participants"] = p.loc[~mask].reset_index(drop=True)
    t["sessions"] = sessions.loc[~sessions["session_id"].isin(drop_sessions)].reset_index(drop=True)
    if not t["key_events"].empty:
        t["key_events"] = t["key_events"].loc[
            ~t["key_events"]["session_id"].isin(drop_sessions)].reset_index(drop=True)
    t["_sensors"] = {k: v for k, v in t["_sensors"].items() if k not in drop_sessions}
    return t


def flag_quality(t: dict) -> dict:
    """
    Mark every session with what is wrong with it, if anything.

    The flag is written into the dataset rather than silently applied, because
    a published corpus must let the reader see what was excluded and why. The
    --strict switch then drops the flagged rows for an analysis-ready subset.

    Three defects have actually occurred in this collection:

    emulated_device  an Android emulator, not a phone: sensors pinned to 5 Hz,
                     a 7.7-inch screen at 240 dpi, zero contact area. Key
                     timings there come from a desktop keyboard or a mouse.
    no_typing        nothing was typed: either the field held the right text
                     while the keyboard recorded no characters, which means the
                     text arrived by paste or from another keyboard, or a
                     free-text session produced no characters at all.
    external_input   the app itself detected, during the session, that the field
                     no longer matched its own events (schema 9 and later).
    """
    s, k, d = t["sessions"], t["key_events"], t["devices"]
    if s.empty:
        return t

    # Characters the research keyboard actually produced, per session.
    if not k.empty and {"session_id", "key_class", "action"} <= set(k.columns):
        downs = k[k["action"] == "down"]
        typed = (downs[downs["key_class"].isin(["LETTER", "DIGIT", "PUNCT", "SPACE"])]
                 .groupby("session_id").size().rename("typed_chars"))
        s = s.merge(typed, left_on="session_id", right_index=True, how="left")
        s["typed_chars"] = s["typed_chars"].fillna(0).astype(int)
    else:
        s["typed_chars"] = pd.NA

    emulated = set(_emulated_devices(s, k, d))

    def classify(row) -> str:
        if row.get("device_id") in emulated:
            return "emulated_device"
        # Sessions collected before schema 9 have no such field at all, and a
        # missing value is NaN — which is truthy. Checked explicitly, because
        # the naive test marked every older session as tampered with.
        ext = row.get("external_input")
        if pd.notna(ext) and bool(ext):
            return "external_input"
        typed = row.get("typed_chars")
        stim = row.get("stimulus") or ""
        if row.get("privacy_mode") == "KEY_ID" and stim:
            if pd.notna(typed) and int(typed) < len(str(stim)):
                return "no_typing"
        # Free text has no stimulus to compare with, so the rule above does not
        # reach it, and one session arrived with 80 backspaces in an empty field
        # and nothing else: the minimum-presses gate counts every press, and
        # pressing backspace in an empty field satisfied it. A free-text session
        # that produced no characters recorded no typing by any definition.
        elif pd.notna(typed) and int(typed) == 0:
            return "no_typing"
        return "ok"

    s["quality_flag"] = s.apply(classify, axis=1)
    t["sessions"] = s
    return t


def _emulated_devices(s, k, d) -> list[str]:
    """Devices failing at least two of the three physical-device checks."""
    suspect: dict[str, list[str]] = {}
    if "best_sensor_delay_us" in d.columns:
        slow = d[pd.to_numeric(d["best_sensor_delay_us"], errors="coerce").fillna(0) >= 100_000]
        for did in slow["device_id"]:
            suspect.setdefault(did, []).append("sensors capped at 10 Hz or slower")
    if "screen_diag_in" in d.columns:
        big = d[pd.to_numeric(d["screen_diag_in"], errors="coerce").fillna(0) >= 7.3]
        for did in big["device_id"]:
            suspect.setdefault(did, []).append("screen too large for a phone")
    if not k.empty and {"touch_major", "touch_minor", "touch_size"} <= set(k.columns):
        flat = (k.groupby("session_id")[["touch_major", "touch_minor", "touch_size"]]
                .max().fillna(0).max(axis=1) == 0)
        dead = set(flat[flat].index)
        if dead and {"session_id", "device_id"} <= set(s.columns):
            for did, _ in s[s["session_id"].isin(dead)].groupby("device_id"):
                suspect.setdefault(did, []).append("contact area always zero")
    # Zero contact area alone is NOT evidence: seven real Xiaomi phones in this
    # corpus report it. Two independent signals are required.
    return [did for did, why in suspect.items() if len(why) >= 2]


def drop_flagged(t: dict) -> dict:
    """Remove every session whose quality_flag is not "ok"."""
    s = t["sessions"]
    if s.empty or "quality_flag" not in s.columns:
        return t
    bad = s["quality_flag"] != "ok"
    if not bad.any():
        print("  strict: nothing to drop")
        return t
    drop_sessions = set(s.loc[bad, "session_id"])
    by_reason = s.loc[bad, "quality_flag"].value_counts().to_dict()
    print(f"  strict: {len(drop_sessions)} session(s) dropped {by_reason}")

    t["sessions"] = s.loc[~bad].reset_index(drop=True)
    if not t["key_events"].empty:
        t["key_events"] = t["key_events"].loc[
            ~t["key_events"]["session_id"].isin(drop_sessions)].reset_index(drop=True)
    t["_sensors"] = {k: v for k, v in t["_sensors"].items() if k not in drop_sessions}

    # A participant left with no sessions is no longer part of the corpus.
    alive = set(t["sessions"]["participant_id"])
    pp = t["participants"]
    gone = int((~pp["participant_id"].isin(alive)).sum())
    if gone:
        print(f"  strict: {gone} participant(s) left with no sessions, removed")
        t["participants"] = pp.loc[pp["participant_id"].isin(alive)].reset_index(drop=True)

    # A device whose every session was dropped must leave too, otherwise the
    # emulator stays in devices.csv and is counted in every device statistic.
    live_dev = set(t["sessions"]["device_id"])
    dd = t["devices"]
    gone_dev = int((~dd["device_id"].isin(live_dev)).sum())
    if gone_dev:
        print(f"  strict: {gone_dev} device(s) left with no sessions, removed")
        t["devices"] = dd.loc[dd["device_id"].isin(live_dev)].reset_index(drop=True)
    return t


# ---------------------------------------------------------------- checks

def report(t: dict) -> None:
    s, k, p, d = t["sessions"], t["key_events"], t["participants"], t["devices"]
    print()
    print(f"  people        {p['person_id'].nunique() if 'person_id' in p else '?'}")
    print(f"  participants  {len(p)}   (person × device)")
    print(f"  devices       {len(d)}")
    print(f"  sessions      {len(s)}")
    print(f"  key events    {len(k)}")
    print(f"  sensor rows   {sum(v if isinstance(v, int) else len(v) for v in t['_sensors'].values())}")

    problems = []

    if not p.empty and "person_id" in p:
        per_person = p.groupby("person_id")["device_id"].nunique()
        per_device = p.groupby("device_id")["person_id"].nunique()
        cross = int((per_person > 1).sum())
        shared = int((per_device > 1).sum())
        print(f"  people on 2+ devices   {cross} of {len(per_person)}")
        print(f"  devices with 2+ people {shared} of {len(per_device)}")
        if cross == 0:
            problems.append(
                "no person appears on more than one device: the person/device "
                "confound is total, and no cross-device claim can be supported")
        if shared == 0:
            problems.append(
                "no device carries more than one person: every impostor pair is "
                "also a cross-device pair, so the error rate mixes person and "
                "hardware and cannot be interpreted")

    if "stimulus" in s.columns:
        missing = int((s["stimulus"].fillna("") == "").sum())
        if missing:
            problems.append(
                f"{missing} session(s) carry no stimulus text (collected before "
                f"schema 4) — identify the stimulus from app_version")
        if "stimulus_sha1" in s.columns:
            for task, g in s.groupby("task_code"):
                h = g["stimulus_sha1"].replace("", pd.NA).dropna().unique()
                if len(h) > 1:
                    problems.append(
                        f"task '{task}' appears with {len(h)} different stimuli — "
                        f"these sessions are NOT comparable and must be separated")

    # Counterbalancing. The three transcription conditions rotate between
    # participants, so position and condition are only separable if all three
    # orders are actually present and roughly equally frequent.
    if "guided_order" in s.columns:
        g = s[s.get("guided", False) == True] if "guided" in s.columns else s
        orders = (g[["participant_id", "guided_order"]]
                  .replace("", pd.NA).dropna().drop_duplicates())
        if not orders.empty:
            counts = orders["guided_order"].value_counts().to_dict()
            print("  guided orders          " +
                  ", ".join(f"{k}:{v}" for k, v in sorted(counts.items())))
            if len(counts) < 3:
                problems.append(
                    f"only {len(counts)} of 3 step orders occur: step position "
                    f"and typing condition are confounded, and a difference "
                    f"between conditions cannot be told from practice effect")
            else:
                lo, hi = min(counts.values()), max(counts.values())
                if hi > 2 * lo:
                    problems.append(
                        f"step orders are unbalanced ({counts}) — include "
                        f"guided_step as a covariate rather than assuming "
                        f"position averages out")

    # Did the "phone flat on the table" instruction actually happen? Unsupervised,
    # it mostly does not: in the first collection one participant in eight complied,
    # while hold_style claimed on_surface for all eight.
    if "motion_active_fraction" in s.columns and "hold_style" in s.columns:
        flat = s[s["hold_style"] == "on_surface"]
        measured = flat["motion_active_fraction"].dropna()
        if len(measured):
            still = int((measured < 0.10).sum())
            print(f"  on-surface sessions still   {still} of {len(measured)} measured"
                  f"   (median moving fraction {measured.median():.0%})")
            if still < len(measured):
                problems.append(
                    f"{len(measured) - still} session(s) labelled on_surface were "
                    f"recorded with the device in motion — treat hold_style as the "
                    f"instruction given, not the condition observed, and filter on "
                    f"motion_active_fraction instead")
        blind = int(flat["motion_active_fraction"].isna().sum())
        if blind:
            print(f"  on-surface sessions unverifiable  {blind}  (device has no gyroscope)")

    if "kb_view_w_px" in s.columns:
        bad = int((pd.to_numeric(s["kb_view_w_px"], errors="coerce").fillna(-1) <= 0).sum())
        if bad:
            problems.append(
                f"{bad} session(s) lack keyboard window size — touch geometry "
                f"cannot be converted to millimetres for these")

    if not k.empty and "action" in k:
        cancels = int((k["action"] == "cancel").sum())
        if cancels:
            print(f"  cancelled presses      {cancels}  (drop these in analysis)")

    # Emulated devices.
    #
    # One participant completed the whole sequence inside an Android emulator:
    # a "Galaxy S21 Ultra" on Android 9 with a 1600x900 screen at 240 dpi,
    # every sensor pinned to 5 Hz, and touch_major / touch_minor / touch_size
    # exactly zero on every event. Keystroke timings from such a run come from
    # a mouse or a desktop keyboard, and the motion channel is synthetic.
    # Three independent signals, so one odd device characteristic is not enough
    # to condemn a real phone.
    if "quality_flag" in s.columns:
        flags = s["quality_flag"].value_counts().to_dict()
        if set(flags) - {"ok"}:
            print(f"  session quality          {flags}")
            problems.append(
                f"{len(s) - flags.get('ok', 0)} session(s) carry a quality_flag "
                f"other than 'ok' — run with --strict, or filter them yourself")

    # Sessions whose text did not come from the research keyboard.
    if "external_input" in s.columns:
        ext = int(s["external_input"].fillna(False).astype(bool).sum())
        if ext:
            problems.append(
                f"{ext} session(s) are flagged external_input: the text in the "
                f"field did not match the recorded key events — drop them")
    if "dropped_key_events" in s.columns:
        drop = int(pd.to_numeric(s["dropped_key_events"], errors="coerce").fillna(0).sum())
        if drop:
            print(f"  key presses lost to the package filter  {drop}")

    if not k.empty and "pressure" in k:
        const = k.groupby("session_id")["pressure"].nunique(dropna=True)
        flat = int((const <= 1).sum())
        if flat:
            print(f"  sessions with constant pressure  {flat} of {len(const)}")

    # Integrity: the counters come from the database, the rows from the export.
    if {"key_event_count", "session_id"} <= set(s.columns) and not k.empty:
        actual = k.groupby("session_id").size()
        expected = s.set_index("session_id")["key_event_count"]
        both = expected.dropna().astype("Int64").align(actual, join="inner")
        mism = int((both[0] != both[1]).sum())
        if mism:
            problems.append(
                f"{mism} session(s) hold fewer key events than the counter says — "
                f"the export was truncated")

    if problems:
        print("\n  warnings:")
        for w in problems:
            print(f"    ! {w}")
    print()


# ---------------------------------------------------------------- writing

def write(t: dict, out: Path, parquet: bool, fingerprints: dict | None = None) -> None:
    fingerprints = fingerprints if fingerprints is not None else {}
    data = out / "data"
    (data / "sensors").mkdir(parents=True, exist_ok=True)

    # lineterminator is given explicitly: pandas defaults to os.linesep, so the
    # same table written on Windows and on Linux differs in every line and the
    # two checksum files cannot be compared. GZIP_PARAMS does the same for the
    # timestamp gzip would otherwise stamp into its header.
    for name in ("participants", "devices", "sessions", "key_events"):
        t[name] = canonical_order(t[name], name)

    t["participants"].to_csv(data / "participants.csv", index=False, **CSV_PARAMS)
    t["devices"].to_csv(data / "devices.csv", index=False, **CSV_PARAMS)
    t["sessions"].to_csv(data / "sessions.csv", index=False, **CSV_PARAMS)
    t["key_events"].to_csv(data / "key_events.csv.gz", index=False,
                           compression=GZIP_PARAMS, **CSV_PARAMS)

    kept = set(t["_sensors"])
    for sid, df in t["_sensors"].items():
        if isinstance(df, int):
            continue   # already written while reading; see build_tables
        if parquet:
            df.to_parquet(data / "sensors" / f"{sid}.parquet", index=False,
                          compression="gzip")
        else:
            df.to_csv(data / "sensors" / f"{sid}.csv.gz", index=False,
                      compression=GZIP_PARAMS, **CSV_PARAMS)
        fingerprints[sid] = _frame_digest(df)

    # Sessions dropped after their sensor file was already streamed out.
    removed = 0
    for f in (data / "sensors").iterdir():
        if f.name.split(".")[0] not in kept:
            f.unlink(); removed += 1
    if removed:
        print(f"  {removed} sensor file(s) of dropped sessions removed")
    for sid in list(fingerprints):
        if sid not in kept:
            del fingerprints[sid]

    _checksums(data, out / "checksums.sha256")
    total = fingerprint(data, fingerprints, out / "fingerprint.sha256")
    print(f"  content fingerprint {total[:16]}")


def _checksums(data: Path, target: Path) -> None:
    lines = []
    stray = []
    for path in sorted(data.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(target.parent)
        # Forward slashes even on Windows: the manifest is read by whoever
        # downloads the package, not only by the machine that built it.
        name = rel.as_posix()
        if path.suffix not in {".csv", ".gz", ".parquet", ".json"}:
            stray.append(name)
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        lines.append(f"{h.hexdigest()}  {name}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if stray:
        print("  ! data/ holds file(s) that are not part of the dataset and "
              "have been checksummed with it:")
        for name in stray[:10]:
            print(f"      {name}")
        print("    move them out of data/ and run again before publishing")


def _toolchain() -> str:
    """Which libraries wrote the package. Worth recording: the Parquet files
    carry the pyarrow version in their footers, so the file checksums of two
    correct runs differ, and this line is what explains the difference."""
    import platform
    parts = [f"python {platform.python_version()}", f"pandas {pd.__version__}"]
    try:
        import pyarrow
        parts.append(f"pyarrow {pyarrow.__version__}")
    except ModuleNotFoundError:
        parts.append("pyarrow absent (CSV output)")
    parts.append(f"{platform.system()} {platform.machine()}")
    return ", ".join(parts)


def canonical_order(df, name: str):
    """Fixed column order (the documented ones first, any later addition after
    them alphabetically) and fixed row order, so that the written table depends
    on the data alone and not on the order the archives were read in."""
    if df.empty or name not in TABLE_ORDER:
        return df
    lead, keys = TABLE_ORDER[name]
    cols = ([c for c in lead if c in df.columns]
            + sorted(c for c in df.columns if c not in lead))
    out = df[cols]
    keys = [c for c in keys if c in out.columns]
    if keys:
        out = out.sort_values(keys, kind="mergesort")
    return out.reset_index(drop=True)


def _frame_digest(df) -> str:
    """
    Content hash of one sensor frame: column names, dtypes and the raw bytes of
    the values. Independent of the operating system, the file format and the
    pyarrow version, unlike the hash of the written file — Parquet stamps the
    writer's version into every footer, so two correct runs on different
    machines never produce the same bytes.
    """
    h = hashlib.sha256()
    for col in df.columns:
        a = df[col].to_numpy()
        h.update(str(col).encode("utf-8"))
        if a.dtype.kind in "biufc":
            # Numeric: the raw little-endian bytes, which is both the cheapest
            # and the exact choice. a.dtype.str ('<i8', '<f8') is used rather
            # than str(dtype), because pandas renames its dtypes between
            # versions while the numpy code does not change.
            h.update(a.dtype.str.encode("utf-8"))
            h.update(a.tobytes())
        else:
            # Text and anything else: tobytes() on an object array hashes the
            # addresses of the Python objects, which differ on every run, so
            # the values have to be spelled out.
            h.update(b"txt")
            h.update("\x00".join("" if v is None else str(v)
                                 for v in a).encode("utf-8"))
    return h.hexdigest()


def fingerprint(data: Path, sensors: dict, target: Path) -> str:
    """
    Write the content fingerprint of the package and return its overall value.

    Two people converting the same archives on different machines get the same
    value here while their checksums.sha256 differ, and - the point of the file -
    anyone holding only the published package can recompute it, which is what
    code/verify.py does.

    The tables are hashed as the bytes of the written files, which are
    deterministic: the line terminator is explicit and gzip stores no
    timestamp. The sensor files are not, because pyarrow stamps its own version
    into every Parquet footer, so those are hashed as frame content instead:
    column names, dtypes and the raw bytes of the values.
    """
    parts = []
    for name, fn in (("participants", "participants.csv"),
                     ("devices", "devices.csv"),
                     ("sessions", "sessions.csv"),
                     ("key_events", "key_events.csv.gz")):
        h = hashlib.sha256()
        with (data / fn).open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        parts.append((name, h.hexdigest()))

    sens = hashlib.sha256()
    for sid in sorted(sensors):
        sens.update(f"{sid} {sensors[sid]}\n".encode("utf-8"))
    parts.append(("sensors", sens.hexdigest()))

    overall = hashlib.sha256()
    for name, digest in parts:
        overall.update(f"{name} {digest}\n".encode("utf-8"))
    total = overall.hexdigest()

    body = ["# Content fingerprint of the published package.",
            "# Tables: sha256 of the written file, which is byte-identical on any",
            "# platform. Sensors: a hash of the frame contents, because Parquet",
            "# footers carry the writer's version and its bytes are not.",
            "# Recompute with code/verify.py; checksums.sha256 covers every file",
            "# as bytes and cannot be reproduced on another machine.",
            f"# produced by {_toolchain()}",
            ""]
    body += [f"{digest}  {name}" for name, digest in parts]
    body += ["", f"{total}  overall", ""]
    target.write_text("\n".join(body), encoding="utf-8")
    return total


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, required=True, help="folder of .zip archives")
    ap.add_argument("--output", type=Path, required=True, help="destination folder")
    ap.add_argument("--no-parquet", action="store_true",
                    help="gzipped CSV instead of Parquet for sensor data")
    ap.add_argument("--strict", action="store_true",
                    help="drop sessions whose quality_flag is not 'ok' "
                         "(emulated devices, pasted text, external input)")
    ap.add_argument("--keep-organiser", action="store_true",
                    help=f"keep sessions of the reserved staff codes "
                         f"{sorted(ORGANISER_CODES)} instead of dropping them")
    args = ap.parse_args()

    if not args.no_parquet:
        # Checked here, before the archives are read: pyarrow is imported by
        # pandas only at the first to_parquet call, which would otherwise be
        # after twenty minutes of work.
        try:
            import pyarrow  # noqa: F401
        except ModuleNotFoundError:
            raise SystemExit(
                "Parquet output needs pyarrow:\n"
                "    python -m pip install pyarrow\n"
                "or run with --no-parquet to write gzipped CSV instead."
            )

    if not args.input.exists():
        raise SystemExit(
            f"--input does not exist: {args.input}\n"
            "A path containing spaces must be quoted."
        )
    if not args.input.is_dir():
        raise SystemExit(f"--input is not a folder: {args.input}")

    print(f"reading {args.input}")
    selected = scan_archives(args.input)
    if not selected:
        # Say what was actually looked at. The previous one-line message sent
        # the reader hunting for a corrupt archive when the real cause was a
        # path that pointed somewhere else.
        zips = len(list(args.input.rglob("*.zip")))
        raise SystemExit(
            f"no usable archives found under {args.input.resolve()}\n"
            f"  .zip files seen (including subfolders): {zips}\n"
            "Expected the collector's keystroke_corpus_*.zip exports."
        )
    print(f"  {len(selected)} device archive(s)")

    sensors_dir = args.output / "data" / "sensors"
    sensors_dir.mkdir(parents=True, exist_ok=True)
    parquet = not args.no_parquet
    fingerprints: dict[str, str] = {}

    def _stream(sid: str, df) -> None:
        if parquet:
            # gzip, not the pyarrow default of snappy. Snappy optimises for read
            # speed, which nobody needs for a file downloaded once: measured on a
            # 28 407-row session it gives 765 KB against 577 KB for gzip, and
            # even loses to plain gzipped CSV at 626 KB. Over five hundred
            # sessions that is a quarter of the download for nothing.
            df.to_parquet(sensors_dir / f"{sid}.parquet", index=False,
                          compression="gzip")
        else:
            df.to_csv(sensors_dir / f"{sid}.csv.gz", index=False,
                      compression=GZIP_PARAMS, **CSV_PARAMS)
        fingerprints[sid] = _frame_digest(df)

    tables = build_tables(iter_bundles(selected), sensor_writer=_stream)
    tables = drop_reused_profile_sessions(tables)
    if not args.keep_organiser:
        tables = drop_organiser(tables)
    tables = flag_quality(tables)
    if args.strict:
        tables = drop_flagged(tables)
    tables["participants"] = assign_person_ids(tables["participants"])
    report(tables)
    write(tables, args.output, parquet=not args.no_parquet,
          fingerprints=fingerprints)
    print(f"written to {args.output}")


if __name__ == "__main__":
    main()
