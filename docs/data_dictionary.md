# Data dictionary – KDUA-Mobile

Every column of the published dataset: type, unit, range, and the traps.
Column set follows export schema version 9, the newest of the three present in
the corpus. Which columns can be empty in the older ones is in `quality.md` §3.

Missing values are empty (`null` in Parquet), never `-1`. The collector writes
`-1` as a sentinel; the conversion replaces it. If you see `-1` in a numeric
column of this dataset, report it as a bug.

---

## `participants.csv`

One row per (person, device) pair. A person who typed on two phones has two rows.

| Column | Type | Unit / values | Notes |
|---|---|---|---|
| `participant_id` | string | `p_` + 12 hex | Random, generated on the device. Unique per device, **not** per person |
| `person_id` | string | `person_0001` | Same person across devices. Derived at packaging from the participant number; the number itself is not published |
| `age_group` | string | `<20`, `20-24`, `25-29`, `30-39`, `40+` | Self-reported |
| `gender` | string | `female`, `male`, `other`, `undisclosed` | Self-reported |
| `handedness` | string | `right`, `left`, `ambidextrous` | Self-reported |
| `typing_experience` | string | `<2`, `2-5`, `6-10`, `10+` | Years of smartphone typing, self-reported |
| `own_device` | string | `own`, `borrowed` | Whether this device belongs to this person. Typing on an unfamiliar phone differs systematically – treat as a covariate, not noise |
| `consent_version` | string | `1.1` | Version of the consent text agreed to |

---

## `devices.csv`

| Column | Type | Unit | Notes |
|---|---|---|---|
| `device_id` | string | `d_` + 12 hex | Random, stable across participants on the same phone |
| `manufacturer`, `model` | string | – | `android.os.Build` values, verbatim |
| `android_release` | string | e.g. `11`, `16` | |
| `api_level` | int | e.g. 30, 36 | |
| `screen_w_px`, `screen_h_px` | int | pixels | Full display, not the keyboard |
| `density_dpi` | int | dots per inch | **Needed for every conversion to millimetres** |
| `sensor_hardware` | json | – | Per sensor: type, name, vendor, nominal rate, resolution, max range |

---

## `sessions.csv`

| Column | Type | Unit | Notes |
|---|---|---|---|
| `session_id` | string | `s_` + 16 hex | |
| `participant_id`, `device_id` | string | – | Foreign keys |
| `task_code` | string | `transcribe_ua`, `transcribe_en`, `digits`, `fixed_phrase`, `free_ua` | |
| `stimulus` | string | – | **The exact target text.** Present from schema 4 on; empty for earlier sessions |
| `stimulus_sha1` | string | hex | Detects a changed stimulus under an unchanged task code. Earlier releases of the collector used a different `transcribe_ua` sentence – this is how you tell them apart |
| `privacy_mode` | string | `KEY_ID`, `CLASS_ONLY` | In `CLASS_ONLY`, key identity and touch geometry are blank by design |
| `layout` | string | `ua`, `en` | See `docs/keyboard_layout.md` |
| `posture` | string | `sitting`, `standing`, `walking` | Instructed, not measured |
| `hold_style` | string | `one_hand_thumb`, `two_hands_thumbs`, `held_index`, `on_surface` | **The strongest nuisance variable in this dataset.** Changing hold shifts median dwell by ~30 %, against ~9 % between sessions at fixed hold |
| `guided` | bool | – | Whether the session was run inside the app's guided sequence. Guided sessions were self-administered without an operator: task, posture and hold were set by the app, not chosen on the spot. Manual sessions were run with an operator present. The degree of control differs, so do not pool them without checking |
| `guided_step` | int | 1…6, 0 if manual | Position of the session in the sequence. **Needed because typing speeds up within a run:** in one control run the median inter-key interval fell from 436 to 381 ms between the first and third transcription |
| `guided_order` | string | `ABC`, `BCA`, `CAB`, empty if manual | Which rotation of the three transcription conditions this participant received. A = sitting, hand-held; B = standing, hand-held; C = sitting, phone flat on a surface. The rotation is a 3×3 Latin square assigned deterministically from the participant identifier, so each condition occupies each position equally often. Without it, position and condition would be perfectly confounded and no difference between conditions could be told from practice |
| `gyro_samples`, `gyro_active_samples` | int | count | Gyroscope samples in the session, and how many of them exceeded 0.02 rad/s. Blank/zero on devices with no gyroscope – one of the first nine phones (Galaxy A15) has none |
| `motion_active_fraction` | float | 0…1 | Derived by `convert.py` as `gyro_active_samples / gyro_samples`, `NaN` where there is no gyroscope. **Use this, not `hold_style`, to select sessions where the phone really lay on a surface.** Measured values separate cleanly: 0.004 for a phone on a table, 0.85–0.99 for a phone in the hand, 0.14–0.53 for one put down and picked up again. In the first collection, seven of eight sessions labelled `on_surface` were recorded with the phone in motion – the label records the instruction given, this column records what happened |
| `kb_view_w_px`, `kb_view_h_px` | int | pixels | Measured keyboard window. With `density_dpi`, converts normalised touch coordinates to millimetres |
| `started_at_utc` | string | date, `YYYY-MM-DD` | The day of the session, deliberately not the time of day. The clock time adds nothing to an analysis – order within a sitting is `guided_step`, timing within a session is `t_rel_ns`, and the same-day pairing of two devices survives a date – while for anyone who was in the room it would be one more key to join a record to a person. See `privacy.md` §1 |
| `started_nanos`, `ended_nanos` | int | ns, `elapsedRealtimeNanos` | |
| `uptime_to_realtime_offset_nanos` | int | ns | See "Two clocks" below |
| `requested_sensor_period_us` | int | µs | Requested, not achieved. Use `quality` for what actually happened |
| `key_down_count`, `key_event_count`, `sensor_sample_count` | int | – | |
| `quality` | json | – | Per sensor: sample count, achieved Hz, largest gap in ms, nominal Hz |
| `power_save` | bool | – | Power-save mode was on. Suspect any session where sensor rate collapsed |
| `thermal_start`, `thermal_end` | string | `none`…`shutdown` | API 29+; `unknown` below that |
| `battery_start_pct`, `battery_end_pct` | int | % | |
| `charging` | bool | – | |
| `app_version` | string | e.g. `2.3` | Provenance |

---

## `key_events.csv.gz`

One row per key action. A keypress produces two rows: `down` then `up`.

| Column | Type | Unit | Notes |
|---|---|---|---|
| `session_id` | string | – | |
| `seq` | int | – | Order within the session |
| `action` | string | `down`, `up`, `cancel` | **`cancel` has no matching `up`** – the system took over the gesture. Drop these presses; without the marker they would be indistinguishable from real data loss |
| `key_class` | string | `LETTER`, `DIGIT`, `PUNCT`, `SPACE`, `BACKSPACE`, `SHIFT`, `ENTER`, `LAYOUT` | Always present, both privacy modes |
| `key_row`, `key_col` | int | – | Position on the layout. Blank in `CLASS_ONLY` |
| `key_code` | int | Unicode code point | **Unshifted.** The code point of the key, not of the character produced: a capital letter appears as its lowercase code point preceded by a `SHIFT` press. Reconstructing the typed text means tracking shift state across events. Negative values are special keys: −2 shift, −3 enter, −4 layout. **Backspace has no code in the published data**: the collector writes −1 both for the backspace key and for a deliberately blank field, and the conversion turns every −1 into a null, so all 15 344 backspace events have an empty `key_code`. Select backspace by `key_class`. Blank in `CLASS_ONLY` |
| `caret_moves` | int | count | Session-level, in `sessions.csv`. Attempts to move the caret or select text. The caret is pinned to the end of the field, so these attempts change nothing and the value is normally 0. A non-zero value is not a defect; it flags a session worth inspecting before its digraphs are used |
| `t_nanos` | int | ns | Sensor clock (see below) |
| `t_rel_ns` | int | ns | **Since session start. Use this unless you have a reason not to** |
| `touch_x`, `touch_y` | float | fraction of keyboard window, 0…1 | **Not pixels.** Multiply by `kb_view_w_px` / `kb_view_h_px` for pixels, then by 25.4 / `density_dpi` for millimetres. Blank in `CLASS_ONLY` |
| `offset_x`, `offset_y` | float | key widths, roughly −0.5…+0.5 | Displacement from key centre, normalised by key size. Dimensionless and device-independent by construction. A systematic bias to one side reflects which finger and which hand struck the key. **Present in `CLASS_ONLY` too**: where the key is hidden, how precisely it was struck is not |
| `key_w`, `key_h` | float | **pixels** | Note the asymmetry: these are view pixels while `touch_x`/`touch_y` on the same row are fractions. Millimetres are `key_w × 25.4 / density_dpi` directly, with no `kb_view_*` factor. Blank in `CLASS_ONLY` |
| `touch_major`, `touch_minor` | float | device units ≈ pixels | Contact ellipse axes. Manufacturer-dependent; several devices return a constant |
| `touch_size` | float | 0…1, device-dependent | Normalised contact area. Not comparable across manufacturers |
| `pressure` | float | dimensionless | **Read this before using it.** Available as a real measurement only on HTC One and Nexus 9 (both 2017) in our device survey; constant on Galaxy S4 (2014), Redmi Note 8 (2019), realme (2021) and Redmi Note 13 Pro (2023). This is a touchscreen driver property, not an era. Check for variance per device before including it |
| `pointer_id` | int | – | Distinguishes fingers in multi-touch. Overlapping presses are normal in fast typing |

---

## `sensor_samples/*.parquet`

One file per session.

| Column | Type | Unit | Notes |
|---|---|---|---|
| `session_id` | string | – | |
| `sensor_type` | int | Android constant | 1, 2, 4, 11 |
| `sensor_name` | string | `accelerometer`, `magnetometer`, `gyroscope`, `rotation_vector` | **Use this, not the integer** |
| `t_nanos` | int | ns | Sensor hardware timestamp |
| `t_rel_ns` | int | ns | Since session start |
| `t_recv_nanos` | int | ns | When the app received the sample. The difference from `t_nanos` is batching latency |
| `x`, `y`, `z` | float | see below | |
| `w` | float | see below | Only meaningful for `rotation_vector` |
| `accuracy` | int | 0…3 | 0 = unreliable. Magnetometer drops here near metal and electronics |

### Reconstructing the typed text

The key sequence reproduces the text exactly, because the caret is pinned to the
end of the input field: backspace always removes the last character, and nothing
can be inserted in the middle. Verified against a real session in which the
participant deliberately tried to move the caret five times and pressed backspace
ten times; the reconstruction matched the target string character for character.

Three things the loop must handle:

```python
buf, shift = [], False
for e in up_events_in_order:          # action == "up", NOT "down"
    if e.key_class == "SHIFT":     shift = not shift; continue   # toggle, not one-shot
    if e.key_class == "LAYOUT":    continue
    if e.key_class == "BACKSPACE": buf and buf.pop(); continue
    ch = chr(e.key_code)
    buf.append(ch.upper() if shift else ch); shift = False
```

**Iterate over releases, not presses.** The keyboard commits a character when the
key is released, so release order is the order the characters enter the field.
Press order is not: a fast two-thumb typist starts the next key before letting go
of the previous one, and the two orders then differ. One session in the corpus
reconstructs as `kb.research.2206` from presses and `kb.research.2026` from
releases, against a target of `kb.research.2026`; the participant typed it
correctly and the app accepted it. Dwell and flight features are of course still
computed from the press/release pairs – this rule is only about the order in which
characters are appended.

**Shift toggles.** Two `SHIFT` presses in a row turn it on and back off, which is
what a participant does after hitting shift by mistake. Treat every `SHIFT` press
as "next letter is upper case" and such a session reconstructs as `Kb.research.2026`
against a target of `kb.research.2026` – a mismatch that exists only in the
reconstruction. This occurred once in the first 54 collected sessions.

Ignore shift and every capital letter comes out lowercase; ignore `caret_moves`
and you will not notice a session where the assumption failed.

### Worked example: touch geometry in millimetres

Verified against a Redmi Note 13 Pro, 1080 px wide, 440 dpi, keyboard window
1080 × 687 px:

```python
mm_per_px = 25.4 / density_dpi          # 0.0577 mm
x_mm      = touch_x * kb_view_w_px * mm_per_px   # touch_x is a fraction
key_w_mm  = key_w * mm_per_px                    # key_w is already pixels
```

Sanity check: the window is 62.3 mm wide, the top row holds 12 keys, and the
median `key_w` of 89.2 px converts to 5.1 mm. Those agree, which is the quickest
way to confirm you have the units right before building features.

**Units by sensor** – the single most common source of error:

| Sensor | x, y, z | w |
|---|---|---|
| `accelerometer` | m/s², **including gravity** | unused |
| `gyroscope` | rad/s | unused |
| `magnetometer` | µT | unused |
| `rotation_vector` | quaternion components, dimensionless | quaternion scalar part |

Device axes: x to the right of the screen, y up, z out of the screen, with the
phone held upright in portrait.

---

## Two clocks – the thing to understand before touching timestamps

Android has two monotonic clocks and they disagree.

`MotionEvent` timestamps run on `SystemClock.uptimeMillis()`, which **stops
during deep sleep**. `SensorEvent.timestamp` runs on `elapsedRealtimeNanos()`,
which **keeps counting**. The gap equals total accumulated sleep since boot. We
measured 0.9 ms on a freshly rebooted phone and **9.24 days** on one that had
been up for 9.99 days, 93 % of it asleep.

In this dataset key events are **already converted** to the sensor clock, so
`t_nanos` is directly comparable between the two tables. The measured offset is
kept in `uptime_to_realtime_offset_nanos` so the conversion can be checked or
undone.

If you only need timing within a session, use `t_rel_ns` and ignore all of this.

---

## Reading the files

`key_row`, `key_col`, `key_code`, `touch_x`, `touch_y`, `key_w` and `key_h` are
blank in every `CLASS_ONLY` session; `offset_x`, `offset_y`, `pressure`, the
contact-size columns and all timings are present there. `key_code` is blank in
`KEY_ID` sessions too wherever the key was backspace. The exact table is in
`keyboard_layout.md` §5.

Pandas reads a column with blanks as float by default, so key code 1092 arrives
as `1092.0` and every join on it fails silently. Read with a nullable backend:

```python
pd.read_csv("data/key_events.csv.gz", dtype_backend="numpy_nullable")
```

The Parquet sensor files carry their types, so this does not apply to them.

---

## Conventions

- All timestamps in nanoseconds; all wall-clock times UTC.
- Boolean columns are `true` / `false`.
- Text is UTF-8. Ukrainian stimuli contain і, ї, є, ґ – check your locale before
  blaming the data.
- Files are UTF-8 with `\n` endings and a header row.
- `checksums.sha256` covers every data file; `code/verify.py` checks them.
