#!/usr/bin/env python3
"""
Load the KDUA-Mobile dataset in Python, with the traps already handled.

    from load import load
    d = load("path/to/dataset")

    d.sessions        one row per session, the analysis subset by default
    d.participants    one row per (person, device) record
    d.devices         one row per phone
    d.key_events      one row per press or release
    d.sensors(sid)    the sensor frame of one session, read on demand

What "traps already handled" means, each of which has caught someone:

* Columns with blanks are read with a nullable integer type. Read naively,
  key_code 1092 arrives as 1092.0 and every join on it fails in silence.
* The analysis subset excludes step 1, the familiarisation session, and the one
  session recorded outside the guided sequence. Pass analysis_only=False for
  all 498 sessions.
* on_surface(), in_hand() and own_device_records() select on what was measured,
  not on what the participant was told to do.
* Sensor frames are not loaded until asked for: all of them together are 389 MB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import pandas as pd
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(f"Missing dependency: {exc.name}") from exc

STILL = 0.10        # motion_active_fraction below this is "on a surface"
MOVING = 0.20       # and at or above this is "in the hand"


@dataclass
class Dataset:
    root: Path
    sessions: pd.DataFrame
    participants: pd.DataFrame
    devices: pd.DataFrame
    key_events: pd.DataFrame
    _cache: dict = field(default_factory=dict, repr=False)

    def sensors(self, session_id: str) -> pd.DataFrame:
        """The sensor frame of one session. Three sessions have no file."""
        if session_id in self._cache:
            return self._cache[session_id]
        pq = self.root / "data" / "sensors" / f"{session_id}.parquet"
        gz = self.root / "data" / "sensors" / f"{session_id}.csv.gz"
        if pq.exists():
            df = pd.read_parquet(pq)
        elif gz.exists():
            df = pd.read_csv(gz)
        else:
            raise FileNotFoundError(
                f"no sensor file for {session_id}; the stream never started "
                "in three sessions, select on sensor_sample_count > 0")
        self._cache[session_id] = df
        return df

    # ---- selections that encode a decision, so it is made once and in writing

    def on_surface(self) -> pd.DataFrame:
        """Sessions where the phone was measurably still, whatever was asked."""
        return self.sessions[self.sessions["motion_active_fraction"] < STILL]

    def in_hand(self) -> pd.DataFrame:
        return self.sessions[self.sessions["motion_active_fraction"] >= MOVING]

    def with_sensors(self) -> pd.DataFrame:
        return self.sessions[self.sessions["sensor_sample_count"] > 0]

    def key_identity(self) -> pd.DataFrame:
        """Sessions where which key was pressed is published."""
        return self.sessions[self.sessions["privacy_mode"] == "KEY_ID"]

    def own_device_records(self) -> pd.DataFrame:
        """The conservative subset for impostor analysis: no hidden duplicates."""
        return self.participants[self.participants["own_device"] == "own"]

    def join(self) -> pd.DataFrame:
        """Sessions with the participant and device columns attached."""
        return (self.sessions
                .merge(self.participants, on=["participant_id", "device_id"],
                       how="left")
                .merge(self.devices, on="device_id", how="left"))


def load(root: str | Path, analysis_only: bool = True) -> Dataset:
    root = Path(root)
    data = root / "data"

    sessions = pd.read_csv(data / "sessions.csv",
                           dtype_backend="numpy_nullable")
    participants = pd.read_csv(data / "participants.csv",
                               dtype_backend="numpy_nullable")
    devices = pd.read_csv(data / "devices.csv", dtype_backend="numpy_nullable")
    key_events = pd.read_csv(data / "key_events.csv.gz",
                             dtype_backend="numpy_nullable")

    if analysis_only:
        keep = sessions["guided_step"].between(2, 6)
        sessions = sessions[keep].reset_index(drop=True)
        key_events = key_events[
            key_events["session_id"].isin(set(sessions["session_id"]))
        ].reset_index(drop=True)

    return Dataset(root=root, sessions=sessions, participants=participants,
                   devices=devices, key_events=key_events)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="print a summary of the dataset")
    ap.add_argument("--dataset", type=Path, required=True)
    args = ap.parse_args()

    d = load(args.dataset)
    print(f"  sessions in the analysis subset  {len(d.sessions)}")
    print(f"  participant records              {len(d.participants)}"
          f"   people {d.participants['person_id'].nunique()}")
    print(f"  devices                          {len(d.devices)}")
    print(f"  key events                       {len(d.key_events)}")
    print(f"  measurably on a surface          {len(d.on_surface())}")
    print(f"  measurably in the hand           {len(d.in_hand())}")
    print(f"  with key identity                {len(d.key_identity())}")
    print(f"  own-device records               {len(d.own_device_records())}")
    sid = d.sessions.loc[d.sessions['sensor_sample_count'] > 0, 'session_id'].iloc[0]
    g = d.sensors(sid)
    print(f"  one sensor frame ({sid})  {len(g)} rows, "
          f"{g['sensor_name'].nunique()} streams")
