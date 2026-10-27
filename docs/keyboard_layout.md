# Keyboard layout and geometry – KDUA-Mobile

The data were collected with a keyboard written for the study, registered with
Android as an input method. This is not a stylistic choice: an ordinary
application sees only the text that arrives, while an `InputMethodService` sees
each key going down and coming up, and the touch that caused it. Everything in
`key_events.csv.gz` exists because the keyboard itself recorded it.

The keyboard has no autocorrection, no prediction, no swipe input and no haptic
feedback. Nothing between the finger and the record changes the timing.

---

## 1. Two layouts

Sessions carry a `layout` column, `ua` or `en`, and a key is identified by
`key_row` and `key_col` within that layout. Rows are numbered from the top,
columns from the left, both from zero.

### Ukrainian, ЙЦУКЕН (`layout = ua`), 4 rows

| Row | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | й | ц | у | к | е | н | г | ш | щ | з | х | ї |
| 1 | ф | і | в | а | п | р | о | л | д | ж | є | |
| 2 | SHIFT | я | ч | с | м | и | т | ь | б | ю | BACKSPACE | |
| 3 | LAYOUT | , | SPACE | . | ENTER | | | | | | | |

Shifted output is the capital of the letter; for the punctuation keys of row 3
it is `;` on the comma key and `?` on the full stop key.

### Latin, QWERTY with a digit row (`layout = en`), 5 rows

| Row | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 0 |
| 1 | q | w | e | r | t | y | u | i | o | p |
| 2 | a | s | d | f | g | h | j | k | l | |
| 3 | SHIFT | z | x | c | v | b | n | m | BACKSPACE | |
| 4 | LAYOUT | , | SPACE | . | ENTER | | | | | |

Shifted output of the digit row is `! @ # $ % ^ & * ( )`.

This layout is reached only through the fixed phrase task, whose stimulus is
ASCII; the Ukrainian layout carries the transcription and the free text. Both
layouts are reproduced here in full, including keys this corpus never records,
so that the table can be read as the keyboard the participants saw.

**The mapping above was re-derived from the published events** – every
`(layout, key_row, key_col, key_code)` combination that occurs in the data – and
it agrees with the keyboard source cell for cell. Only the keys that the three
tasks require are actually present in the corpus.

---

## 2. Special keys

| Key | `key_class` | `key_code` in the data |
|---|---|---|
| Shift | `SHIFT` | -2 |
| Enter | `ENTER` | -3 |
| Layout switch | `LAYOUT` | -4 |
| Backspace | `BACKSPACE` | **empty** |
| Space | `SPACE` | 32 |
| Letters, digits, punctuation | `LETTER`, `DIGIT`, `PUNCT` | the Unicode code point of the unshifted character |

The empty `key_code` on backspace is a known collision and not a loss: the
collector writes -1 both for the backspace key and for a field it deliberately
leaves blank, and the conversion turns every -1 into a null. **Select backspace
by `key_class`, never by code.** Backspace is at row 2, column 10 in the
Ukrainian layout and row 3, column 8 in the Latin one, which is a second way to
find it. 15 344 of the 97 974 events in this corpus are backspaces.

`key_code` is the unshifted code point, so letter case does not come from it.
Case comes from the shift state, which has to be tracked while walking the
events.

---

## 3. Shift behaves differently in different app versions

Up to app version 3.3 shift was a toggle: it stayed on until pressed again. From
3.4 it is single-shot, resetting after any committed character except backspace.

In practice every session in this corpus reconstructs under the single-shot
rule, which was verified by rebuilding the text of all 417 stimulus sessions
from the events (see `quality.md` §7). Two presses of shift still cancel each
other, and a session whose shift event was lost cannot recover the case of the
following letter; one such session exists and is named in `known_issues.md`.

**Reconstruction must walk the release (`up`) events, not the presses.** The
keyboard commits a character when the key is released, so in fast two-thumb
typing the order of presses is not the order of the text. Walking presses on the
fixed phrase `kb.research.2026` yields `kb.research.2206`.

---

## 4. Geometry

The keyboard occupies the full width of the screen and 250 dp of height, capped
at 55 % of the screen height so that a landscape session is not all keyboard.
Keys are laid out row by row with a 3 dp gap on every side.

Within a row, width is distributed by weight:

| Key | Weight |
|---|---|
| space | 5 |
| shift, backspace, enter, layout switch | 1.5 |
| everything else | 1 |

so a key's width is `(row width – gaps) × weight / total weight of the row`, and
every row is the same height, `(keyboard height – gaps) / number of rows`.

Each event publishes the geometry it was recorded against:

| Column | Meaning |
|---|---|
| `key_w`, `key_h` | the size of that key, in view **pixels**, on that device, in that session |
| `touch_x`, `touch_y` | the touch point as a **fraction** of the keyboard view, 0…1. Multiply by `kb_view_w_px` and `kb_view_h_px` for pixels |
| `offset_x`, `offset_y` | the touch point relative to the centre of the key, divided by the key's width and height, so roughly −0.5…+0.5 |

Note the asymmetry on one row of the same table: the touch point is a fraction
of the view while the key size is in pixels. It is a trap worth stating twice.

`offset_x` and `offset_y` are the comparable form: ±0.5 is the edge of the key
whatever the screen, so they can be pooled across devices. Raw pixels cannot,
and `density_dpi` in `devices.csv` is needed for any conversion to millimetres.
`kb_view_w_px` and `kb_view_h_px` in `sessions.csv` give the size of the whole
keyboard view for that session.

### Touches that land between keys

A touch inside a gap is attributed to the nearest key, but only within three
quarters of a key's width and height; beyond that it is not a key press at all.
Without the fallback, edge touches would vanish and the record would show
missing presses; without the limit, a palm resting on the view would be recorded
as a press.

---

## 5. What the privacy mode removes

Free-text sessions are recorded in `CLASS_ONLY` mode. The difference is exact:

| Column | `KEY_ID` (417 sessions) | `CLASS_ONLY` (81 sessions) |
|---|---|---|
| `key_class` | present | present |
| `key_row`, `key_col`, `key_code` | present | empty |
| `touch_x`, `touch_y`, `key_w`, `key_h` | present | empty |
| `offset_x`, `offset_y` | present | **present** |
| `pressure`, `touch_major`, `touch_minor`, `touch_size` | present | present |
| timings (`t_nanos`, `t_rel_ns`, down/up pairing) | present | present |

So a free-text session still carries how hard and how precisely the person hit
the key, and how long they held it, but not which key it was. The text cannot be
reconstructed from it; what remains is a skeleton of word lengths, which is
quantified in `privacy.md`.
