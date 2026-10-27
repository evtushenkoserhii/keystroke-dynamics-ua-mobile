# Privacy – KDUA-Mobile

What was hidden, what was kept, and what can still be recovered from this
dataset. The residual leak described in §3 is measured on the published corpus,
not estimated.

The approach and the first measurement were published as S. V. Yevtushenko,
"Quantitative assessment of residual information leakage in anonymised
collection of keystroke dynamics data" (МЦНД conference proceedings, 2026). The
figures below repeat that analysis on the full frozen corpus, which is 36 times
larger than the three sessions reported there.

---

## 1. What the dataset holds about a person

| | |
|---|---|
| Published | key press and release timings; touch geometry relative to the key; contact size and reported pressure; motion sensor streams; age group, gender, dominant hand, typing experience, whether the phone was their own; device manufacturer, model, screen and sensor chips |
| Not published | name, group, contacts, institution per record, e-mail, any free-text content, the participant number read out in class, any device identifier (no IMEI, no Android ID, no serial number, no advertising ID) |

`participant_id` and `device_id` are random values generated on the device at
installation. `person_id` is derived at packaging from the participant number and
the number itself is then discarded, so the number cannot be recovered from the
published files.

Demographics are coarse by design: age in five bands rather than years, gender
in four categories, experience in four bands. The questionnaire never asked for
anything finer.

Session times are coarse by decision rather than by design. The collector
records the start of a session to the second; `sessions.csv` publishes the date
only. The clock time is of no analytical use – the order of steps within a
sitting is `guided_step`, timing within a session is `t_rel_ns` on a monotonic
clock, and the same-day pairing of a person's two devices survives a date – but
for anyone who was in the room it would be one more key with which to join a
record to a person. `started_nanos` is nanoseconds since the device booted, not
wall clock, and carries no time of day.

---

## 2. The two privacy modes, verified

Stimulus tasks are recorded in `KEY_ID` mode, free text always in `CLASS_ONLY`.
The difference is field by field:

| Field of a key event | `KEY_ID` | `CLASS_ONLY` |
|---|---|---|
| key class (letter, digit, punctuation, space, special) | kept | kept |
| code of the character entered | kept | **hidden** |
| row and column of the key in the layout | kept | **hidden** |
| absolute coordinates of the touch | kept | **hidden** |
| key size | kept | **hidden** |
| press and release timestamps | kept | kept |
| touch offset from the key centre, normalised by key size | kept | kept |
| contact area and reported pressure | kept | kept |

Hiding the character code alone would be pointless. The geometry of an on-screen
keyboard is deterministic, so an absolute touch coordinate recovers the
character almost uniquely; every field from which the character can be rebuilt
has to go with it.

**Verification on the published corpus.** All 81 free-text sessions, 22 902 key
events: every field marked hidden is empty in every single record. The checks
are `key_code`, `key_row`, `key_col`, `touch_x`, `touch_y`, `key_w`, `key_h`,
and the count of non-empty values is zero for each.

What survives is biometrically informative without being legible: the normalised
touch offset takes between 81 and 824 distinct values within a single free-text
session, median 136, so nearly every press carries its own signature. A
systematic bias to one side follows from which finger of which hand struck the
key.

---

## 3. The residual leak, measured

The sequence of key classes is published, and from it the structure of the typed
text can be rebuilt: the number of words, the length of each, and the positions
of punctuation. The letters cannot.

Measured over all 81 free-text sessions of this corpus:

| | |
|---|---|
| words per session | median 13, from 5 to 61 |
| characters typed | median 101, from 59 to 388 |
| skeletons that are unique within the corpus | **81 of 81** |

A skeleton looks like this one, taken from a session of this dataset:

```
[4, 11, 5, 5, 5, 1, 4, 8, 1, 3, 14, 3, 8, 4, 7, 6, 1, 15, 7, 1, 7]
punctuation after the 8th word
```

What this does and does not allow:

- The content **cannot** be reconstructed. The sequence carries no information about which letters were typed.
- It is specific enough to **confirm a hypothesis**. Anyone who already holds a guess at what a participant wrote can check it by matching word lengths, and since all 81 skeletons differ, a correct guess matches exactly one session.
- It therefore also **links**: a person who holds the text itself, from any other source, can find the session that typed it and read off that participant's device, demographics and typing behaviour.

The practical size of this leak is bounded by what the task asked for. The prompt
was "describe in 2 to 3 sentences any film or book you liked", with an explicit
instruction not to write anything about themselves, no name, no place of study,
no contacts. The leak is over a description of a film, not over a confession.
That bounds it; it does not remove it.

---

## 4. The consent text was less precise than this

The consent text that participants agreed to, version 1.2, says of free-text
tasks: "only the class of the key is stored (letter, digit, space), so what was
written cannot be reconstructed." Translated in full in `consent.md`.

The precise statement, which is the conclusion of the published analysis cited
above, is different: **the words cannot be reconstructed, but the number of
characters in each word and the positions of punctuation remain recoverable.**

The difference is not a formality, and we state it here rather than leave it to
a reader to find. In mitigation, and without claiming it undoes the imprecision:

- participants were told, in the same text, that anonymised data might be published in open access, and that is the basis of this release;
- the content of the task was constrained in advance to a film or book description, with an explicit instruction to write nothing about themselves;
- no free-text content is published, only its skeleton;
- the correct wording is already in print in the cited paper, and any further collection under this protocol uses it.

Anyone who considers this insufficient for their own use of the data should treat
the 81 free-text sessions as the part to leave out; the 417 stimulus sessions
carry no content risk at all, because their text was given to the participant.

---

## 5. Re-identification risk from the quasi-identifiers

Behavioural biometrics is what this dataset is for, so the behaviour itself
cannot be removed. The question is what else could single a record out.

Measured on the 82 participant records:

| Combination known to an attacker | Records that become unique |
|---|---|
| gender + age group | 1 of 82 |
| gender + age group + handedness | 1 of 82 |
| device model | 31 of 82 |
| device model + gender + handedness + age group | 48 of 82 |
| collection date + device model + every questionnaire answer | 70 of 82 |

The dates are in the table because the collection days are documented in
`collection_protocol.md` and cannot be hidden; what was removed is the time of
day, which would have narrowed a day to a single participant in a room.

Uniqueness inside the dataset is not the same as re-identification: an attacker
needs an outside list that ties a person to those attributes and to the fact
that they took part. But the honest reading is that for someone inside the
cohort – who knows who attended which session and what phone they carry – a
record is often singled out. The device model is the strongest of these
attributes, and it cannot be coarsened without destroying what the corpus exists
to study: the separation of person from device.

The corpus is small, which cuts both ways. 71 people is few enough that an
insider has few candidates, and few enough that nothing in it supports a claim
about a population.

---

## 6. Regulatory framing

Keystroke dynamics are behavioural biometric data and fall under the special
category of Article 9 of Regulation (EU) 2016/679, and under the Law of Ukraine
"On the protection of personal data" (No. 2297-VI). The release rests on
informed consent given before participation, recorded per participant as a
version string and a timestamp, with the clause on publication of anonymised
data quoted in `consent.md`.

Regulation (EU) 2024/1689 requires datasets used for high-risk systems,
biometric identification among them, to be documented. This file, together with
`data_dictionary.md`, `collection_protocol.md`, `quality.md` and
`known_issues.md`, is that documentation, and follows the practice of
Datasheets for Datasets (Gebru et al., Communications of the ACM 64(12), 2021).

Documentation of the ethical review is not part of this release and will be
added as `docs/ethics.md` when it is available.

---

## 7. For anyone reusing the data

- Do not attempt to re-identify participants, and do not combine this dataset with any list of the cohort. The licence permits reuse of the data, not that.
- If your work needs free text, read §3 and §4 first and decide whether to include those 81 sessions.
- Publish per-person results only in aggregate. A table with one row per `person_id` plus device model and demographics reproduces the quasi-identifier combination measured in §5.
