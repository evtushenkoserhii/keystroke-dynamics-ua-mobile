# Changelog

This dataset follows the rule that a published version is never edited in
place. A correction becomes a new version with its own DOI, and the version it
corrects stays downloadable, so that a paper citing it can still be checked.

## 1.0 – 2026-10-26

First public release. Collection ran from 16 September to 26 October 2026 and is
closed; the corpus is frozen.

- 498 sessions, 82 participant records (71 people), 56 devices, 46 distinct models
- 97 974 key events, 16 608 404 sensor samples
- content fingerprint `00330347a3e47af885486916fd89306f73a7c5baf5124d672075726785babcf8`

Published as the `--strict` build of `code/convert.py`: 35 sessions were
excluded before release and the reasons are itemised in `docs/known_issues.md`
§1. Three exporter versions are present, 7, 8 and 9, because the collector was
still being corrected during collection; which fields can be empty in which
version is in `docs/quality.md` §3.

Decisions worth recording, because they are visible in the files:

- session times are published to the day, not to the second, which removes a join key that was of no analytical use (`docs/privacy.md` §1);
- `person_id` is numbered from the sorted participant identifier, so the labels do not depend on the order the archives were read in;
- the free-text sessions are published with their residual leak measured and disclosed rather than withheld (`docs/privacy.md` §3 and §4).

### Not in this release

`docs/ethics.md`, the documentation of the ethical review, which will be added
in a later version. The lawful basis of this release is the clause of the
consent text on publication of anonymised data, quoted in `docs/consent.md`.
