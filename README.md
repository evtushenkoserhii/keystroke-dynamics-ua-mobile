# KDUA-Mobile: Ukrainian mobile keystroke dynamics with sensors

[Українська версія](README.uk.md)

498 typing sessions from 71 people on 56 Android phones, recorded with a
keyboard written for the study: every key press and release, the touch that
caused it, and the motion of the phone at 200 Hz while it was being typed on.
Ukrainian text on the ЙЦУКЕН layout.

Version 1.0, collected 16 September to 26 October 2026.
DOI: [10.5281/zenodo.23691798](https://doi.org/10.5281/zenodo.23691798)

---

## Why another keystroke corpus

Most keystroke datasets record one person per device, which makes person and
hardware inseparable: a classifier that tells two records apart may be telling
two handsets apart, and nothing in the data can show which. This corpus breaks
that confounding from both sides, deliberately:

- **14 devices carry two or more people**, giving 63 pairs of different people on identical hardware;
- **11 people appear on two devices**, so a template can be tested where it was not enrolled.

Two further things it has that comparable corpora usually lack:

- **The condition was measured, not assumed.** Each participant typed the same sentence sitting, standing, and with the phone flat on a surface. The phone's own gyroscope recorded whether it really was flat: of 90 sessions instructed that way, 74 are measurable and only 38 actually were. The instruction and the observation are separate columns.
- **Order was counterbalanced.** The three conditions are permuted by a 3×3 Latin square assigned deterministically from the participant identifier, so position and condition are not confounded.

What it is not: a corpus for population claims. 71 students of one Ukrainian
university, 75 of 82 records under 20 years old, one language, one layout.

---

## Contents

| | |
|---|---|
| sessions | 498 |
| participant records (person × device) | 82, which is 71 people |
| devices / distinct models | 56 / 46 |
| key events | 97 974, that is 48 987 press and release pairs |
| sensor samples | 16 608 404 |
| tasks | a 16-character fixed phrase, an 89-character Ukrainian pangram, free text |
| sensors | accelerometer, gyroscope, magnetometer, rotation vector, requested at 200 Hz |
| Android versions | 9 to 16 |
| total size | 389 MB |

```
data/
  participants.csv        one row per (person, device): coarse demographics
  devices.csv             one row per phone: model, screen, sensor chips
  sessions.csv            one row per session: task, condition, quality fields
  key_events.csv.gz       97 974 rows: press and release, touch geometry
  sensors/<session>.parquet   one file per session, four sensor streams
  features/
    keystrokes.csv.gz     one row per press: hold time
    digraphs.csv.gz       one row per pair: DD, UD, UU, DU
docs/                     see the index below
code/                     conversion, features, protocol, baseline, verification
splits/verification_protocol.json   the fixed experiment
sample/                   three sessions, to look at without downloading 389 MB
checksums.sha256          bytes of the published files
fingerprint.sha256        content hash, comparable across machines
```

## Where each part lives

| | |
|---|---|
| Zenodo, under the DOI | the complete package as one archive, sensors included, 411 MB, and a 1.5 MB sample |
| this repository | the code, the documentation, the sample, the verification protocol, and the three small tables plus `key_events.csv.gz` |

`data/sensors/` is not in the repository: 389 MB in 495 files is more than Git
should carry, and Git LFS does not help, because one clone would spend a third
of the free monthly bandwidth quota. `data/features/` is not there either, since
`code/features.py` reproduces it exactly. `checksums.sha256` describes the
complete package, so verifying a clone needs `--quick`:

```
python code/verify.py --dataset . --quick
```

## Quick start

```python
import pandas as pd

s = pd.read_csv("data/sessions.csv")
k = pd.read_csv("data/key_events.csv.gz", dtype_backend="numpy_nullable")
g = pd.read_parquet(f"data/sensors/{s.session_id[0]}.parquet")
```

`code/load.py` and `code/load.R` do the same with the traps handled. Before
using the data for anything, read `docs/quality.md` §1 and §4: there are four
filters that every analysis of this corpus needs, and one of them is the
difference between the instruction given and the condition observed.

## Documentation

| File | What it answers |
|---|---|
| `docs/data_dictionary.md` | every column: type, unit, range, and the traps |
| `docs/quality.md` | the quality fields, which filters to apply, achieved sensor rates |
| `docs/known_issues.md` | everything known to be wrong, with session identifiers |
| `docs/keyboard_layout.md` | the two layouts key by key, geometry, shift semantics |
| `docs/stimuli.md` | the three task texts with hashes |
| `docs/collection_protocol.md` | how the sessions were produced |
| `docs/consent.md` | the consent text participants agreed to, translated |
| `docs/privacy.md` | what was hidden, what remains recoverable, measured |
| `docs/baseline.md` | the fixed protocol and a baseline result to beat |

## Baseline

A deliberately simple baseline is published with the data: log median digraph
and hold times, a scaled Manhattan distance, no training and no parameters. On
the fixed protocol in `splits/verification_protocol.json` it reaches an equal
error rate of **22.2 %**, and the gap between impostors on the same phone
(23.6 %) and impostors on another phone (22.2 %) is 1.4 points.

That gap is the number to watch. A method that scores far better against
impostors on other phones than against impostors on the same phone is reading
the hardware, not the person. Reproduce with:

```
python code/features.py      --dataset .
python code/make_protocol.py  --dataset .
python code/baseline_eer.py   --dataset .
```

## Reproducing the package from the raw exports

```
python -m pip install -r code/requirements.txt
python code/convert.py --input <folder of archives> --output . --strict
```

The conversion is deterministic: the same archives give the same tables on any
operating system, in any folder layout. The byte checksums in
`checksums.sha256` cannot be reproduced on another machine, because pyarrow
writes its version into every Parquet footer. `fingerprint.sha256` is the hash
that can, and it is computed so that anyone holding only the published package
can recompute it:

```
python code/verify.py --dataset .
```

The reference value for version 1.0 is

```
00330347a3e47af885486916fd89306f73a7c5baf5124d672075726785babcf8  overall
```

The full release order, for anyone rebuilding the package from scratch, is
`convert.py`, `features.py`, `make_protocol.py`, `make_sample.py`, then
`verify.py --write`, which rewrites both hash files over everything that then
exists.

## Licence and attribution

- **Data** (`data/`, `sample/`, `splits/`): Creative Commons Attribution 4.0 International. See `LICENSE-DATA`.
- **Code** (`code/`): MIT. See `LICENSE-CODE`.

Attribution is the condition of use, not a courtesy: cite the dataset by its
DOI. `CITATION.cff` holds the machine-readable form.

```
Yevtushenko, S. (2026). KDUA-Mobile: Ukrainian mobile keystroke dynamics with
motion sensors (version 1.0) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.23691798
```

```bibtex
@dataset{yevtushenko2026kdua,
  author    = {Yevtushenko, Serhii},
  title     = {KDUA-Mobile: Ukrainian mobile keystroke dynamics with motion sensors},
  year      = {2026},
  version   = {1.0},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.23691798},
  url       = {https://doi.org/10.5281/zenodo.23691798}
}
```

## Limits you should know before you start

- The on-surface condition was met in 38 of 74 measurable sessions. Filter on `motion_active_fraction`, never on `hold_style`.
- `pressure` is constant in 470 of 498 sessions: most Android digitisers do not sense pressure. It is not a feature.
- 100 sessions have no motion verification: 54 predate the counters, 46 are on phones with no gyroscope.
- 31 of 82 records are on a borrowed phone, and some of those people also have a record of their own that cannot be linked to it. For impostor analysis use the 51 records with `own_device = own`.
- Free-text sessions publish the class of each key but not its identity. The word-length skeleton of the text remains recoverable, which is measured in `docs/privacy.md` §3.
- Splits must be made by `person_id`. Splitting by session or by participant record leaks, because 11 people hold two records.

Everything in this list is detailed in `docs/known_issues.md`. Nothing in it was
found by a reviewer; all of it was found by us and is published on purpose.
