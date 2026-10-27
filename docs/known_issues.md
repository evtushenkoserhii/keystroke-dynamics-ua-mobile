# Known issues – KDUA-Mobile

Everything we know to be wrong, incomplete or easy to misread in this dataset,
with the session and participant identifiers needed to act on it. Nothing here
is hidden behind a flag only: each item says what to do.

A defect we name costs us a caveat. A defect a reviewer finds costs us the
paper. That is the reason for this file.

---

## 1. Excluded from the published package

The published package is the `--strict` build of `code/convert.py`. 35 sessions
were removed before publication:

| Reason | Sessions | Detail |
|---|---|---|
| staff recordings | 13 | the organiser's own test sessions, participant number 100 |
| re-used participant record | 12 | on 12.10.2026 an operator edited an existing participant's questionnaire instead of creating a new one, so a second person's sessions were written under `p_7aa0f9f49d83`. Separation is unambiguous by date; the converter drops that record's sessions earlier than 2026-10-01 (`PROFILE_REUSE_CUTOFFS`) |
| Android emulator | 6 | one participant completed the whole sequence in an emulator: sensors pinned at 5 Hz, 7.3-inch diagonal, zero contact area. Detection requires two independent signals of three, because seven real phones in this corpus also report zero contact area |
| no real typing | 4 | in three of them the text reached the field without the research keyboard; in the fourth, a free-text session, the participant pressed backspace 80 times in an empty field, which satisfied the minimum-presses gate while producing no characters at all (`s_c38496b8015c447a`, `typed_chars = 0`). All four belong to two participants |

The flags survive in the converter, so a non-strict build reproduces these rows
with `quality_flag` set. They are not in the published files.

---

## 2. Kept, with caveats

### 2.1 One session where letter case cannot be reconstructed

`s_94f2cf9e63bd4f55` (participant `p_e58a230a3b08`, step 4, 24.09.2026, app
3.3). One SHIFT event is missing from the record, so the capital of the first
letter does not come back from the events: reconstruction yields `щедрий` where
the stimulus has `Щедрий`. Timing features are unaffected and the session is
otherwise exact. The cause – SHIFT not being reset after a committed symbol –
was fixed in app version 3.4.

### 2.2 Three sessions with no sensor data

`s_0787a9e258fc4133`, `s_ee6dea44485b4c1d`, `s_216923a59fc14dfc` (participant
`p_68f5ea052b40`, device `d_7e22d6c58961`, 02.10.2026). The sensor stream never
started although the keyboard counters are intact; from the fourth session of
the same participant it worked normally. Usable for keystroke features, unusable
for sensor features. Select on `sensor_sample_count > 0`.

### 2.3 Seven sessions with a trailing space

In seven sessions the reconstructed text is the stimulus plus one space that the
participant typed after the last word. Not a defect of the record: the key event
is real. It matters only if you compare the reconstruction with the stimulus for
equality, in which case compare stripped strings.

### 2.4 One session outside the guided sequence

`s_636b4a403dc74707` has `guided = false` and `guided_step = 0`: it was started
from the application's own screen, not from the guided sequence, so it has no
position in the Latin square. Filter `guided_step` between 1 and 6 to exclude
it, as in `quality.md` §4.

### 2.5 Two participant records mislabel a researcher's phone as their own

`p_707de53d8a64` and `p_8dee36d8b314` carry `own_device = own` on device
`d_f3bbcafe5e0a`, which is one of the two reference phones the researcher
brought. **Treat every session on `d_f3bbcafe5e0a` and `d_f41461b5266d` as a
borrowed device**, whatever the field says. 93 of the 498 sessions were recorded
on those two phones.

### 2.6 Hidden duplicates among borrowed phones

31 of the 82 participant records are marked `borrowed`. Some of those people are
Android owners whose own record is also in the corpus, under a different random
participant number, because the number is generated per installation and no
participant wrote theirs down. Those two records cannot be linked.

Consequence for impostor analysis: a pair drawn across two records may
accidentally be the same person, which inflates the false-accept rate in an
unknown direction. The conservative subset is the 51 records with
`own_device = own`; in it the same person appearing twice is impossible by
construction. State which subset a reported error rate came from.

### 2.7 100 sessions have no motion verification

54 sessions were recorded before the gyroscope counters existed (app 3.1,
`schema_version = 7`) and 46 on devices with no gyroscope at all – 15 of the 56
devices have none. `motion_active_fraction` is empty for all 100.
`gyro_samples = 0` must never be read as a still device. See `quality.md` §1 and
§3.

### 2.8 The on-surface condition was often not met

Of the 90 sessions instructed `on_surface`, 74 are measurable and only 38 were
actually still. `hold_style` is the instruction given, not the condition
observed. Compliance by collection date, as measured:

| Date | Setting | On surface as measured |
|---|---|---|
| 16.09 | online, unsupervised | 9 instructed, none measurable; a check of the raw sensor streams found one |
| 23.09 | in room, 1 participant | 1 of 1 |
| 24.09 | online and in room | 6 of 11 measured |
| 29.09 | online, unsupervised | 1 of 6, 2 borderline |
| 02.10 | in room, 4 groups | 12 of 33, 11 borderline |
| 12.10 | in room, cross-device | 1 of 2 |
| 22.10 | in room, individual | 10 of 13, 2 borderline |
| 26.10 | in room, individual | 7 of 8 |

Unsupervised collection gives roughly a third; an operator next to the
participant gives over eighty per cent. Anyone reporting results per posture
must report the n that the measured filter leaves.

---

## 3. Structure of the dataset that limits what can be claimed

### 3.1 Impostor pairs are concentrated on two phones

14 devices carry two or more people, giving 63 pairs of different people on the
same hardware. 49 of those pairs are on the researcher's two reference phones
(8 people on one, 7 on the other) and only 14 on devices belonging to
participants themselves.

The two groups are not equivalent: the reference phones were handed around in a
controlled sequence, the participants' phones were shared occasionally. **Report
the two groups separately.** A single pooled number makes the corpus look built
around two handsets.

### 3.2 Cross-device coverage is thin and mostly against a reference phone

11 people of 71 appear on two devices. In 9 of the 11 the second device is a
reference phone; only 2 people (`person_0036`, `person_0057`) typed on two
phones that both belong to participants, by swapping with each other – the most
informative configuration in the corpus and the rarest.

10 of the 11 recorded both devices on the same day. One (`person_0024`) returned
after 32 days, so exactly one person in the corpus provides a within-person
comparison across a month. Session-level or record-level splits will leak;
**split by `person_id`.**

### 3.3 Pressure and touch size are not usable features

470 of 498 sessions report a single distinct `pressure` value. Most Android
digitisers do not sense pressure and return a constant, so a model that improves
when pressure is added is reading a device identifier, not a behaviour.
`touch_major`, `touch_minor` and `touch_size` are reported as zero by several
manufacturers; use them within a device only.

### 3.4 Free text carries no key identity

The 81 free-text sessions are recorded in `CLASS_ONLY` privacy mode: key class,
geometry and timing are published, the key identity is not. Key-level analysis
therefore uses the 417 stimulus sessions. The residual information in a
`CLASS_ONLY` session is a word-length skeleton, which is documented in
`privacy.md`.

### 3.5 Demography is narrow

75 of the 82 records are under 20, 6 are 20–24 and 1 is over 40; 60 male, 22
female. All participants are students of one Ukrainian university, typing
Ukrainian on a ЙЦУКЕН layout. Nothing in this corpus supports a claim about
older typists, other languages or other layouts.

### 3.6 Three exporter versions

Sessions were recorded with app versions 3.1, 3.3 and 3.4 (schema 7, 8 and 9)
while the collector was still being corrected. Which fields can be empty in
which version is in `quality.md` §3. No session was re-recorded to a newer
version: the data are as collected.

---

## 4. Reproducibility caveat

The byte checksums in `checksums.sha256` describe the published files. They
cannot be reproduced on another machine, because pyarrow writes its own version
into the footer of every Parquet file. Converting the same archives again gives
the same data and different bytes. `fingerprint.sha256` is the check that does
hold across machines; its reference value for version 1.0 is

```
00330347a3e47af885486916fd89306f73a7c5baf5124d672075726785babcf8  overall
```

Three earlier defects of the converter itself are worth recording, because any
package built with a version before this one differs from the published files
without differing in content: CSV was written with the platform line ending,
the column order of `sessions.csv` and the row order of every table followed
whichever archive was read first, and `person_id` labels were numbered in order
of encounter. All three are fixed; the grouping of records into people was never
affected.

---

## 5. What is not in this file

Consent, anonymisation and residual re-identification risk are the subject of
`privacy.md`, not of this file. Documentation of the ethical review is not part
of this release and will be added as `docs/ethics.md` when it is available; the
lawful basis for publication is the clause of the consent text that covers
publication of anonymised data, which is quoted in `privacy.md`.
