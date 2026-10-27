# Baseline result – KDUA-Mobile

A published dataset without a number on it invites every reader to invent their
own experiment, and the numbers that come back are then incomparable. This file
fixes one experiment and one result. It is deliberately the simplest method that
can be written down completely, and it exists to be beaten.

Everything here is reproduced by three commands:

```
python code/features.py       --dataset .
python code/make_protocol.py  --dataset .
python code/baseline_eer.py   --dataset .
```

---

## 1. The protocol

`splits/verification_protocol.json`, built by `code/make_protocol.py`. Only the
transcription task is used: all participants typed the same 89 characters, so
two sessions are comparable without aligning different texts.

| | |
|---|---|
| unit of enrolment | a (person, device) record, not a person |
| records | 81 of 82; one record has no transcription session left after cleaning |
| people | 70, of whom 11 appear on two devices |
| enrolment | the first two transcription sessions in recorded order |
| probe | the third, which is always a condition the template has not seen |
| pairs | exhaustive over records, no sampling, no random seed |

| Pair kind | Count | What it measures |
|---|---|---|
| `genuine_same_device` | 81 | the same person on the same phone |
| `genuine_cross_device` | 22 | the same person on another of their phones |
| `impostor_same_device` | 126 | a different person on the **same** phone: hardware held constant, so the error is about the person |
| `impostor_cross_device` | 6 332 | a different person on a different phone, the usual benchmark pair, and the one that can be won on the device alone |

The probe being an unseen condition is the hard version of the task. A template
built from all three conditions and tested on one of them would flatter any
method applied to it, including this one.

The file also carries a person-level partition into `dev` and `eval` halves for
anyone fitting a model. A person is in one half only, with both their records.
Splitting by session or by record leaks: 11 people would appear on both sides.

---

## 2. The features

`code/features.py` writes two tables from the published events:

| File | Rows | Content |
|---|---|---|
| `data/features/keystrokes.csv.gz` | 48 987 | one per key press: hold time, and the touch geometry that produced it |
| `data/features/digraphs.csv.gz` | 48 489 | one per adjacent pair of presses: DD, UD, UU, DU |

Definitions, for keys 1 and 2 of a pair: `hold = up1 - down1`,
`DD = down2 - down1`, `UD = down2 - up1`, `UU = up2 - up1`,
`DU = up2 - down1`, all in milliseconds from `t_rel_ns`.

Measured over the corpus, pauses longer than 2 s excluded:

| | median | 5th pct | 95th pct |
|---|---|---|---|
| hold | 73.0 ms | 40.0 | 108.0 |
| DD | 279.8 ms | 125.0 | 1099.7 |
| UD | 203.6 ms | 51.0 | 1015.5 |
| UU | 276.6 ms | 124.8 | 1093.1 |
| DU | 352.5 ms | 191.0 | 1179.0 |

Two notes that matter for anyone recomputing these:

- A press is paired with its release by key position within the session, counting occurrences, never by proximity in time. Pairing by nearest timestamp breaks exactly where the data are most interesting, when two keys are held at once. All 48 987 presses pair cleanly, and the script refuses to continue if any hold time comes out negative.
- UD is negative in 132 of 47 709 pairs, 0.3 %: the next key went down before the previous came up. That is real two-thumb overlap, not an error. 780 pairs exceed the 2 s pause threshold and are marked rather than removed.

---

## 3. The method

Feature vector of a session: the natural logarithm of the median DD of every
digraph that occurs in it, and of the median hold of every key. 528 dimensions
exist across the corpus; a template holds a median of 125 of them.

Template of a record: the mean of its two enrolment vectors, dimension by
dimension.

Score of a pair: the mean over the dimensions both sides have of
`|probe − template| / MAD(dimension)`, where the median absolute deviation is
taken over all sessions. Low is similar. Pairs sharing fewer than 20 dimensions
are not scored; in this protocol there are none.

Equal error rate: the threshold at which the share of genuine pairs rejected
equals the share of impostor pairs accepted, found by scanning every observed
score. No training, no hyperparameters, no seed.

---

## 4. The result

| Comparison | EER |
|---|---|
| genuine same device vs **all** impostor pairs | **22.2 %** |
| genuine same device vs impostors on the same phone | 23.6 % |
| genuine same device vs impostors on another phone | 22.2 % |
| genuine **cross-device** vs all impostor pairs | 23.2 % |
| own-device records only (48 records) | 20.8 % |

Median scores: 1.240 for genuine same-device pairs, 1.129 for genuine
cross-device, 1.652 for impostors on the same phone, 1.644 for impostors on
another phone.

### What these numbers say

**22 % is a floor, not a result.** Each session is 89 characters, the template
is two sessions, and the probe is a condition the template never saw. Published
figures in the 5 to 15 % range come from far more data per person, richer
features and, often, from protocols that test on a condition the template has
already seen.

**The gap between same-phone and other-phone impostors is 1.4 points**, which is
the most informative number here. In a corpus where each person appears on one
phone only, an impostor pair is also a hardware pair, and a method can score
well by telling handsets apart rather than people. This baseline gains almost
nothing from hardware, as the two rows show. A method that shows a much larger
gap on this protocol is reading the device, and the `impostor_same_device`
subset is in the dataset precisely to make that visible.

**Cross-device genuine pairs cost 1 point** here, 23.2 % against 22.2 %, which
is suspiciously little and should not be read as "templates transfer across
phones". With 22 such pairs the estimate is noisy, and this baseline is too weak
for the question. It is the open question the dataset was built around, not an
answer it provides.

**Own-device records score better** (20.8 %), as expected: typing on an
unfamiliar phone is less consistent. That subset is also the conservative one
for impostor analysis, because it cannot contain two records of the same person
unlinked; see `known_issues.md` §2.6.

### Variants, so that the floor is honest

The same method, changing one thing at a time, on the same protocol:

| Variant | EER |
|---|---|
| log timings, template dimensions from either enrolment session (**the baseline**) | 22.2 % |
| log timings, dimensions present in both enrolment sessions | 23.5 % |
| raw milliseconds, dimensions from either session | 28.6 % |
| raw milliseconds, dimensions from both | 30.7 % |
| log timings, digraph latencies only | 25.9 % |
| log timings, hold times only | 33.3 % |
| the repeated 16-character phrase instead of the sentence, same posture both times | 33.7 % |

The log transform is worth six points, which is why the baseline uses it:
keystroke latencies are log-normally distributed and a scaled Manhattan distance
on raw milliseconds is dominated by the slowest digraphs. Pass `--raw` to
`baseline_eer.py` to reproduce the untransformed figures.

The last row is worth keeping in mind by anyone planning a collection: the short
phrase was typed twice under identical conditions, which should be the easy
case, and it still loses to one sentence typed under a condition change. 16
characters are not enough.
