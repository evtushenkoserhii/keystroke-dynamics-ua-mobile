# sample/

Three sessions of one participant, in the same layout as `data/`, so that the
shape of this dataset can be seen without downloading 389 MB.

| | |
|---|---|
| participant record | `p_7fc74a3a3c5f`, `person_0035`, her own phone |
| device | samsung SM-A556E, Android 16, 1080 × 2116 px at 450 dpi, gyroscope present |
| sessions | steps 1, 2 and 3 of the guided sequence |
| exporter | schema version 9, the newest of the three in the corpus |

| Step | Task | Layout | Privacy mode | What it shows |
|---|---|---|---|---|
| 1 | `fixed_phrase` | `en` | `KEY_ID` | the 16-character line, with key identity |
| 2 | `transcribe_ua` | `ua` | `KEY_ID` | the 89-character pangram, condition A, sitting |
| 3 | `free_ua` | `ua` | `CLASS_ONLY` | free text: key classes published, identity not |

```
sample/
  participants.csv     one row
  devices.csv          one row
  sessions.csv         three rows, all 40 columns
  key_events.csv.gz    394 rows
  sensors/*.parquet    three files, 50 720 rows, 1.45 MB
```

Step 1 is the familiarisation session and is **not** part of the analysis
subset; it is here because it is the only session with the Latin layout, and the
sample would otherwise show one layout out of two. The analysis subset is
`guided_step` between 2 and 6, as in `docs/quality.md` §4.

Nothing in this sample is a special case: no quality flag, no missing sensor
stream, no older exporter version. For the sessions that are special cases, see
`docs/known_issues.md`.

Read it exactly as the full package, pointing the loader at this folder:

```python
import pandas as pd
s = pd.read_csv("sample/sessions.csv")
k = pd.read_csv("sample/key_events.csv.gz", dtype_backend="numpy_nullable")
g = pd.read_parquet(f"sample/sensors/{s.session_id[0]}.parquet")
```

Rebuilt from the full package with `python code/make_sample.py --dataset .`.
