# Informed consent – KDUA-Mobile

The text below is what every participant read on the first screen of the
application, before anything was recorded. It was shown in Ukrainian; this is a
faithful translation. The participant had to tick "I have read this and agree to
take part" before the questionnaire appeared, and the application recorded the
version of the text agreed to and the moment of agreement.

Every participant record in this corpus carries `consent_version = 1.2`, the
version translated here.

---

## Informed consent (version 1.2)

The study examines individual characteristics of typing on a smartphone.
Participation is voluntary and can be stopped at any moment without giving a
reason.

### What is collected

- the moments at which keys are pressed and released;
- the coordinates, contact area and pressure of each touch;
- readings from the accelerometer, gyroscope and magnetometer;
- the device model and the system version;
- age group, gender, dominant hand, typing experience;
- a mark of whether the phone is your own or borrowed;
- the number read out by the lecturer, used only to join together the recordings you make on different phones. It is a number unconnected to your name or your group, and filling it in is not required.

### What is NOT collected

- your name, your group or your contact details: the application does not ask for them;
- the content of text you compose yourself: for those tasks only the class of the key is stored (letter, digit, space), so what was written cannot be reconstructed;
- anything from other applications: recording happens only in this application's own input field.

### How the data reach the researcher

Recordings stay on your device until you press the "Send to the researcher"
button yourself. The application transmits nothing in the background and does
not contact the network at any other moment. Sending is anonymous: it requires
no login to any account.

### Data and your rights

Recordings are stored under a random identifier unconnected to your person.
**Anonymised data may be published as a scientific dataset in open access.**

Until you have pressed "Send to the researcher", the recordings remain on this
device only, and the "Withdraw consent" button deletes them completely. After
sending, deleting them is no longer possible – for the same reason that makes
participation safe: there is nothing in what was sent by which one particular
person's recordings could be found.

---

## Notes on this translation

- The emphasis on the publication sentence is added here, not present in the application. That sentence is the basis on which this dataset is published: participants were told, before taking part, that anonymised data might be released in open access.
- "The number read out by the lecturer" is the participant number described in `collection_protocol.md` §5. It is not published. `person_id` in `participants.csv` is derived from it and the number itself is discarded at packaging.
- The questionnaire that follows the consent screen asks for age group, gender, dominant hand, typing experience, whether the phone belongs to the participant, and the participant's habitual grip. Its answers are the columns of `participants.csv`.
- Residual re-identification risk, including what remains in a free-text session, is analysed in `privacy.md`.
- Documentation of the ethical review is not part of this release and will be added as `docs/ethics.md` when available.
