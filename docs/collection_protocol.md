# Collection protocol – KDUA-Mobile

How the 498 sessions were produced. This is the English version of the protocol
the collection ran under; the instructions quoted below were shown to
participants in Ukrainian, and the translations are faithful rather than literal.

Participants were students of the National University "Odesa Law Academy"
(computer science and cybersecurity programmes), typing Ukrainian on their own
Android phones or on a phone handed to them. Collection ran from 16 September to
26 October 2026.

---

## 1. Instrument

A keyboard application written for the study and registered with Android as an
input method, so that key-down and key-up events and the touch behind each of
them could be recorded; see `keyboard_layout.md`. No autocorrection, no
prediction, no swipe typing, no haptic feedback.

Recording is confined to the application's own input field. The keyboard records
nothing in any other application, and the application sends nothing until the
participant presses the send button.

Four sensors were requested at 5 000 µs (200 Hz) in every session:
accelerometer, gyroscope, magnetometer and rotation vector. What the devices
actually delivered is in `quality.md` §5.

---

## 2. The guided sequence

Each participant completes six sessions in one sitting. The application leads
them one after another: the participant cannot pick tasks, and progress survives
closing the app.

| Step | Task | Posture | Grip | In analysis |
|---|---|---|---|---|
| 1 | `fixed_phrase` | sitting | own habit | **no**, familiarisation |
| 2 | `transcribe_ua` | condition 1 of the participant's order | | yes |
| 3 | `free_ua` | sitting | own habit | yes |
| 4 | `transcribe_ua` | condition 2 | | yes |
| 5 | `fixed_phrase` | sitting | own habit | yes |
| 6 | `transcribe_ua` | condition 3 | | yes |

Step 1 is excluded from analysis by design. The first half-minute on an
unfamiliar keyboard is unlike anything that follows, and it is cheaper to spend
it on a session nobody uses than to let it contaminate one that matters.

Odd positions are fixed; only the three transcription conditions move. Step 1 is
`guided_step = 1` in the data, and `guided = false` marks the single session in
this corpus that was started outside the sequence.

### The three conditions

**A, sitting.** "Sit comfortably, hold the phone as you always do. Type the
sentence exactly as shown. Take your time. Speed is not being measured: what
matters is how you type, not how fast."

**B, standing.** "Stand up – actually stand, not sit up straighter. Hold the
phone the same way you hold it sitting. Press Start once you are already
standing."

**C, phone on a surface.** Worded harder than the rest on purpose. In the first
collection one participant in eight complied, while the data marked the
condition as met for all eight.

> "This task is done differently from all the others, and it is the easiest one
> to spoil. Put the phone down on a hard flat surface: a desk, a windowsill, a
> stool. A lap, a pillow or your palm will not do. Type the sentence without
> lifting the phone and without steadying it with your hand, even lightly. Your
> hand touches the screen only. The Start button unlocks only when the sensors
> show that the phone really is lying still. If you pick it up in the middle of
> typing, the application will notice and warn you, and that recording has to be
> discarded."

---

## 3. Counterbalancing

The three conditions are permuted by a 3×3 Latin square: `ABC`, `BCA`, `CAB`.
Each condition stands in each position exactly once per three participants, so
across participants the effect of position on condition averages to zero.

The order is **computed from the participant identifier**, not drawn at random:
a stable hash of the random `participant_id` modulo three. The same person on
the same device therefore always gets the same order, including after
reinstalling the application, and the stored order can never disagree with the
one in use. The identifier is itself random, so the three orders come out
roughly even: 24, 26 and 32 participant records in this corpus.

The order is published per session as `guided_order`, and the position as
`guided_step`. Position and condition are counterbalanced, not independent:
`guided_step` belongs in the model as a covariate.

Why it is needed at all: in a control run the mean inter-key interval fell from
436 ms at the first transcription to 381 ms at the third. Without permutation,
"faster on the table" and "faster because warmed up" would produce the same
numbers and could not be told apart.

---

## 4. What the application refuses to accept

A session can only be finished when all of these hold:

- the minimum number of key presses for the task has been reached (see `stimuli.md`);
- for stimulus tasks, the field content equals the stimulus character for character;
- the text reconstructed from the recorded key events agrees with the field content. A disagreement means the text arrived from somewhere else – pasted, or typed with another keyboard – and the session is flagged `external_input`;
- for condition C, the device is still.

Stillness is measured before and during the session: a two-second window of
gyroscope samples with angular velocity under 0.02 rad/s, falling back to the
accelerometer under 0.08 m/s² on devices with no gyroscope, and passing
unverified where neither sensor exists. If the phone is picked up mid-session,
the application shows a warning and the participant is asked to repeat the step.

The application also warns when nothing appears in the field, which means the
research keyboard is not the active one, and asks the participant to repeat a
step rather than silently keeping a bad record.

---

## 5. Environment, session by session

| Date | Setting | Participant records |
|---|---|---|
| 16.09 | three first-year groups, online | 9 |
| 23.09 | one third-year participant, in a room | 1 |
| 24.09 | first-year group online, second and third year in a room | 14 |
| 29.09 | four first-year groups, online | 5 |
| 02.10 | four first-year groups in a room, with devices exchanged | 32 |
| 12.10 | cross-device block, in a room | 1 person, 2 records |
| 22.10 | cross-device block, third and fourth year, in a room | 12 |
| 26.10 | cross-device block, in a room | 7 |

Two things were done deliberately to break the confounding of person and device,
which no amount of data collected one-person-one-phone can fix:

- **Several people on one phone.** On 02.10 participants exchanged handsets inside the room; from 12.10 the researcher's two phones were handed from participant to participant. 14 devices carry two or more people.
- **One person on several phones.** In the cross-device blocks a participant completed the sequence on their own phone and then on a second one. 11 people have records on two devices.

The limits of that structure, and why the two groups of pairs must be reported
separately, are in `known_issues.md` §3.

Participant numbers were handed out on paper cards. The number is the only link
between two records of the same person; it is a number with no relation to a
name or a group, it was optional, and it is not published – `person_id` is
derived from it at packaging and the number itself is discarded.

In the unsupervised online sessions an operator read the instructions aloud over
the call and the participants worked alone on their own phones. In the room an
operator sat with each participant. The difference in compliance is large and
measurable: see the table in `known_issues.md` §2.8.

---

## 6. How a session reaches the researcher

Everything stays on the phone until the participant presses "Send to the
researcher". There is no background transfer and no network access at any other
moment; sending requires no account and carries no identifier beyond the random
`participant_id`.

The export is one archive per phone, containing one JSON document per session
plus a manifest with a SHA-256 of each document. It is cumulative: pressing send
twice produces two archives, the later one containing the earlier. 93 archives
were received, of which 36 are superseded copies; `code/convert.py` keeps the
newest archive per device and ignores the rest.

Consent is recorded as a version string (`1.2` for every record in this corpus)
and the moment of agreement. Until the participant presses send, a "withdraw
consent" button deletes the recordings from the device completely. After
sending, deletion is no longer possible, for the same reason that participation
is safe: nothing in what was sent identifies a person. The consent text says
exactly this, and is translated in `consent.md`.
