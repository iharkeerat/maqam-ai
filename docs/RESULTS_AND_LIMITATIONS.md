# Research evidence and limitations

**Evidence snapshot: 11 November 2026**

## Independently repeatable software behaviour

- Built-in `portfolio_smoke_demo.py` operates on a **constructed** three-chord XML score. The tied first two chords become one normalized note event, with predicted original-chord starts `[0, 2]` for two externally supplied formal syllables.
- The API returns a formal result and does not return the score's lyric-reference text. It rejects a DTD-containing invalid XML submission (HTTP 422).
- The formal engine and exact composition counters are checked against constructed independent fixtures. An exact formal result is **not a likelihood or music-confidence estimate**.
- The source adapter supports direct and voice-wrapped MuseScore 3 measure events and selected simple tuplets; it **rejects** missing timing, mixed voices and conflicting time jumps rather than choosing an ungrounded timeline.

## What the research audit has and hasn't established

- Authenticated GitHub-side inspection of several original CC0 OpenScore Lieder score files has verified the **presence of note-linked lyric tags, ties, slurs and unsupported timing structures**.
- On small source-derived pilots, untuned MAQAM exact DP did not recover real annotation alignments well, and a slur hard-exclusion shortcut produced false rejections. Other cases were trivial because notation explicitly marked continuations. These are **scientific warnings, not performance results to market**.
- The original full score XML was not passed through the local Python adapter in this working environment. Previous audits distinguish verified source blobs, Python tests on constructed fixtures and unexplored independent-song performance.
- No independent human musical validation, audio-ground-truth study or top-journal novelty proof has been completed.

## How to interpret the code

| Layer | Meaningful claim | Claim not established |
| --- | --- | --- |
| Parser | Rejects unsupported timing, normalizes score events under an explicit contract | Parses arbitrary complex polyphonic notation |
| DP solver | Finds an exact optimum among supplied *formal* candidates and constraints | Finds the musically correct syllable mapping |
| Synthesis | Produces experimental synthesized notes | Produces human-authentic performances |
| Raag/Taal baseline | Reproducible synthetic-data ranking and rules | General expert agreement or cultural correctness |
| API | Allows inspectable, deterministic processing and errors | Independently verified alignment accuracy |

## Useful reference sources

- [OpenScore Lieder public repository](https://github.com/OpenScore/Lieder) for the symbolic score corpus, subject to its source-license terms.
- The standalone technical evidence brief in this `docs/` directory includes the API demonstration and its limitations.

*The strongest portfolio claim is auditable software engineering with scientifically explicit limitations.*
