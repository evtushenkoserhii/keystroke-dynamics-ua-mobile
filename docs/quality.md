# Quality control – KDUA-Mobile

What this dataset records beyond keystrokes: a measurement of how far each
session actually met the condition it was collected under. Every field named
here is a column of `sessions.csv`; nothing has to be recomputed from the raw
events to use them.

The figures below describe the published package: 498 sessions, 82 participant
records (71 people), 56 devices, 97 974 key events, 16 608 404 sensor samples.

---

## 1. Read this first: the instruction is not the observation

`hold_style` says **what the participant was asked to do**. It does not say what
happened. The collector therefore measures the device's own movement with the
gyroscope and publishes the result as `motion_active_fraction`, the share of
gyroscope samples in which the device was moving.

| `hold_style = on_surface` | sessions |
|---|---|
| instructed | 90 |
| measurable (device has a gyroscope and the counters existed) | 74 |
| actually still, `motion_active_fraction < 0.10` | 38 |
| borderline, 0.10 ≤ fraction < 0.20 | 15 |
| moving, fraction ≥ 0.20 | 21 |
| not measurable | 16 |

Median `motion_active_fraction` is 0.096 for sessions instructed `on_surface`
and 0.976 for every other posture, so the measure separates the two conditions
almost binarily. It is the separation that makes the field usable as a filter
and `hold_style` unusable as one.

**Consequence for any analysis of the on-surface condition: select on
`motion_active_fraction`, report the resulting n, and treat `hold_style` as the
protocol's intention.** Compliance was far from uniform: in unsupervised online
sessions roughly a third of participants put the phone down, in supervised
individual sessions over eighty per cent.

---

## 2. The quality fields

| Field | What it says | How to use it |
|---|---|---|
| `quality_flag` | `ok`, `emulated_device`, `no_typing`, `external_input` | The published package is the `--strict` build, so every row is `ok`. The flags exist in the converter and in the unfiltered build |
| `motion_active_fraction` | share of gyroscope samples showing movement; empty where it cannot be computed | the only honest test of the on-surface condition |
| `gyro_samples`, `gyro_active_samples` | the counts the fraction is derived from | `gyro_samples = 0` means **no gyroscope**, not a still device. Never read it as stillness |
| `external_input` | the text in the field disagreed with the recorded key events, i.e. it was pasted or typed with another keyboard | always exclude. Zero such sessions remain in this package |
| `dropped_key_events` | presses that reached the field but not the record | any non-zero value puts the session's timing in doubt. Zero in this package |
| `sensor_sample_count` | rows in the session's sensor file | `0` means the sensor stream never started: the session is usable for keystroke features and unusable for sensor features |
| `caret_moves` | attempts to move the caret inside the field | non-zero means the typed string is not simply the concatenation of the key events; check digraphs in those 56 sessions separately |
| `guided`, `guided_step`, `guided_order` | whether the session came from the guided sequence, its position 1…6, and which Latin-square order | `guided_step` is a covariate: position and condition are counterbalanced, not independent within a participant |
| `quality` | JSON, per sensor: `sample_count`, `actual_hz`, `nominal_hz`, `max_gap_ms` | the achieved rate of this session, not the requested one |
| `schema_version`, `app_version` | the exporter that wrote the session | tells you which fields can be empty; see §3 |
| `typed_chars`, `key_down_count`, `key_event_count` | counters taken from the device database | compare against the rows you load: a mismatch means a truncated export, and the converter refuses to ignore it |

---

## 3. Field coverage by schema version

Collection ran while the collector was still being corrected, so three exporter
versions are present. Empty cells are empty by age, not by failure.

| `schema_version` | `app_version` | sessions | missing fields |
|---|---|---|---|
| 7 | 3.1-guided | 54 | `gyro_samples`, `gyro_active_samples`, `motion_active_fraction`, `external_input`, `dropped_key_events` |
| 8 | 3.3-guided | 86 | `external_input`, `dropped_key_events` |
| 9 | 3.4-guided | 358 | – |

Two consequences worth stating plainly:

- 100 sessions have no motion verification: 54 because the counters did not yet
  exist, 46 because the device has no gyroscope. 15 of the 56 devices have no
  gyroscope at all.
- `external_input` is empty for 140 sessions. Empty means "not checked on the
  device", not "checked and clean". For those sessions the check was done
  afterwards on the published data, by reconstructing the text from the key
  events and comparing it with the stimulus; see §7.

---

## 4. Recommended filters

```python
import pandas as pd

s = pd.read_csv("data/sessions.csv")
p = pd.read_csv("data/participants.csv")

# The analysis set: the guided sequence without its familiarisation step.
# Step 1 is the first half-minute on an unfamiliar keyboard and is excluded by
# design, see collection_protocol.md §2. One session was started outside the
# sequence altogether and carries guided_step = 0.
guided = s[s["guided_step"].between(2, 6)]      # 415 of 498 sessions

# Sensor analysis: a session whose sensor stream never started is not a quiet one.
sensors_ok = guided[guided["sensor_sample_count"] > 0]

# The on-surface condition as observed, not as instructed.
on_surface = guided[guided["motion_active_fraction"] < 0.10]

# Hand-held, for the contrast.
in_hand = guided[guided["motion_active_fraction"] >= 0.20]

# Impostor pairs without the risk of a person matching themselves: see
# known_issues.md on hidden duplicates among borrowed phones.
own = p[p["own_device"] == "own"]          # 51 of 82 records

# Key identity is published only where the typed text was a given stimulus:
# 417 sessions of the whole corpus, 334 of the analysis set above.
by_key = guided[guided["privacy_mode"] == "KEY_ID"]
```

Splits must be made **by person, never by session or by participant record**:
one person can hold two participant records, and 11 people do.

---

## 5. Sampling rates actually achieved

Every session requested 5 000 µs (200 Hz) for all four sensors. What the devices
delivered:

| Sensor | sessions | median | 10th pct | 90th pct | median `max_gap_ms` | 95th pct |
|---|---|---|---|---|---|---|
| accelerometer | 498 | 204.1 Hz | 197.2 | 237.6 | 5.0 ms | 8.3 ms |
| gyroscope | 449 | 203.0 Hz | 161.1 | 235.2 | 4.9 ms | 8.3 ms |
| magnetometer | 461 | 100.0 Hz | 50.0 | 100.0 | 10.0 ms | 109.3 ms |
| rotation vector | 455 | 200.0 Hz | 101.0 | 210.0 | 5.0 ms | 10.4 ms |

Some devices cap the nominal rate at 125, 100 or 50 Hz, and the magnetometer is
capped on most. **Do not assume a uniform sampling interval.** Every sample
carries its own `t_nanos`; resample from the timestamps, or compute features
that do not require a fixed grid.

The two time bases do not coincide: key events are on `uptimeMillis`, sensor
samples on `elapsedRealtimeNanos`. Each session publishes
`uptime_to_realtime_offset_nanos` for the conversion, and `t_rel_ns` in both
tables is already relative to the session start on a single base.

---

## 6. Two fields that look like features and are not

- **Pressure.** 470 of 498 sessions report a single distinct value of
  `pressure`, almost always 1.0: most Android phones have no pressure-sensing
  digitiser and return a constant. Pressure cannot be a feature in this corpus,
  and a model that improves when it is added is reading a device identifier.
- **Touch size.** `touch_major`, `touch_minor` and `touch_size` are
  digitiser-dependent and are reported as zero by several manufacturers. Use
  them within a device, never across devices.

---

## 7. What was verified across the whole corpus

- Every press has a release: 48 987 `down` events and 48 987 `up` events, and no
  `cancel` events at all.
- Every session's key-event count matches the counter written by the device
  database at the time of recording, so no export is truncated.
- The typed text was reconstructed from the published key events and compared
  with the stimulus for all 417 sessions where both exist (`privacy_mode =
  KEY_ID`, stimulus tasks). 409 match character for character; 7 match except
  for a trailing space the participant typed after the last word; 1 differs only
  in the case of the first letter and is named in `known_issues.md`. Nothing
  else differs anywhere. Reconstruction must iterate the **release** events: the
  keyboard commits a character when the key is released, and fast two-thumb
  typing makes press order differ from commit order. SHIFT is a single-shot
  modifier from app version 3.4 and a toggle before it; the published events
  reconstruct under the single-shot rule in every session.
- No session contains text that entered the field from outside the research
  keyboard.
- Session durations range from 6.6 s to 371 s (median 44.9 s), and key presses
  per session from 16 to several hundred (median 96). The short sessions are the
  fixed phrase; the long ones are free text.

---

## 8. Reproducing the package

`code/convert.py` is deterministic: the same archives give the same tables,
irrespective of the operating system, of the folder layout the archives are read
from, and of whether sensors are written as Parquet or as gzipped CSV.

Two verification files ship with the data because they answer different
questions:

- `checksums.sha256` – the bytes of the published files, for whoever downloads
  them. These sums cannot be reproduced on another machine: pyarrow writes its
  own version into the footer of every Parquet file.
- `fingerprint.sha256` – a hash of the content itself, independent of operating
  system, file format and library versions. Tables are hashed as the bytes of
  their written files, which are byte-identical on any platform; sensor files
  are hashed as frame contents, which survives both the Parquet writer version
  and a conversion to CSV. Its header line records the toolchain that produced
  the package.

Both are checked by `python code/verify.py --dataset .`, which recomputes them
from the published files and needs neither the raw archives nor a network.

Reference value for version 1.0:

```
00330347a3e47af885486916fd89306f73a7c5baf5124d672075726785babcf8  overall
```
