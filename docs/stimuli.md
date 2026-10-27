# Stimuli – KDUA-Mobile

Three tasks produced the 498 sessions. Every session stores the exact text it
was given in `stimulus` and its SHA-1 in `stimulus_sha1`, so a session can be
tied to its stimulus without trusting this file.

| Task code | Layout | Privacy | Stimulus length | Sessions | Guided steps | Minimum key presses | Exact match required |
|---|---|---|---|---|---|---|---|
| `fixed_phrase` | `en` | `KEY_ID` | 16 chars | 164 | 1 and 5 | 16 | yes |
| `transcribe_ua` | `ua` | `KEY_ID` | 89 chars | 253 | 2, 4, 6 | 89 | yes |
| `free_ua` | `ua` | `CLASS_ONLY` | prompt, 135 chars | 81 | 3 | 80 | no |

"Exact match required" means the session's Finish button stayed disabled until
the text in the field equalled the stimulus character for character. Counting
key presses alone had proved insufficient: in a pilot a participant stopped at
the 60th press of a 68-character sentence, the moment the button unlocked, and
the record looked usable from the outside while being incomplete.

---

## 1. `transcribe_ua` – the transcription sentence

```
Щедрий гай шепоче, юна фея їде в сад, де зріє хміль, а бджоли кружляють над тихим озерцем
```

- 89 characters, `stimulus_sha1 = 442aa9c64624a4d02d8f3c6514e63f14801e490b`
- English gloss: "A generous grove whispers, a young fairy rides into the garden where the hops ripen, and bees circle above the quiet pond." It is a pangram, not a meaningful statement; it was written to cover the alphabet.
- It uses all 32 letters available on the ЙЦУКЕН layout. The sentence it replaced covered only 22, so for ten letters – б, в, г, ж, ф, ц, щ, я, є, ї among them – no features were being collected at all.
- This is the sentence typed three times by every participant, once in each of the three conditions (sitting, standing, phone on the surface), in a counterbalanced order. It is therefore the task on which any comparison between conditions rests.

## 2. `fixed_phrase` – the short line

```
kb.research.2026
```

- 16 characters, `stimulus_sha1 = 969773be1c31056c4fb5ab5dc5ed38d1cb7710fa`
- Deliberately ASCII, on the Latin layout, mixing letters, full stops and digits.
- Typed twice by every participant: at step 1 as familiarisation, which is **not part of the analysis**, and again at step 5 under the participant's own habitual posture and grip.
- The two recordings of the same 16 characters, separated by three other tasks, are the within-session stability measure of the corpus: the same person, the same text, the same device, a few minutes apart.

## 3. `free_ua` – free text

The `stimulus` field of a free-text session holds the prompt, not what was
typed:

```
Опишіть у 2–3 реченнях будь-який фільм або книгу, які вам сподобались. Не пишіть відомостей про себе: імені, місця навчання, контактів.
```

- 135 characters, `stimulus_sha1 = 9b076636f3e2c4cff271f6b56876d40293aa5a83`
- English gloss: "Describe in 2 to 3 sentences any film or book you liked. Do not write anything about yourself: no name, no place of study, no contacts."
- What the participant composed is **not published**. These sessions are recorded in `CLASS_ONLY` mode, where key identity is not stored at all; see `keyboard_layout.md` §5. `typed_chars` gives the length of what was written, nothing else about it.
- At least 80 key presses were required to finish the task. The gate counts presses, including backspaces, which one participant exploited; that session is excluded and named in `known_issues.md` §1.

---

## 4. Notes for anyone computing features

- Compare reconstructions with `stimulus` **stripped**: in seven sessions the participant typed a trailing space after the last word, which is a real key event and not an error.
- `transcribe_ua` and `fixed_phrase` are the only tasks where a target text exists. Error rates, correction behaviour and per-character alignment are defined only there.
- Backspaces are frequent and are part of the signal, not noise: 15 344 of 97 974 events. The stimulus was never shortened to discourage them.
- The application also defines two tasks that were never used in this collection, `transcribe_en` and `digits`. No session in this corpus carries those codes.
- All SHA-1 values in this file were recomputed from the published `stimulus` column and match it.
