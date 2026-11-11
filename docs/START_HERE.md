# Start here: MAQAM AI documentation

Welcome! MAQAM is a **computational music research prototype**, not a finished song-generation system. The repository separates a browser-based music workbench from a formal symbolic-score alignment experiment. Both are exploratory.

## Pick a route

| Visitor | Best path | Time needed |
|---|---|---|
| **Professor / internship evaluator** | [Reviewer guide](REVIEWER_GUIDE.md) → [Formal method](FORMAL_METHOD.md) → [Results & limits](RESULTS_AND_LIMITATIONS.md) | About 2–5 minutes to understand the claims |
| **Student** | [Getting started](GETTING_STARTED.md) → [Main README](../README.md) → [Screenshot guidance](SCREENSHOTS.md) | Around 10–20 minutes to set up, depending on dependencies |
| **Developer** | [Repository map](REPO_MAP.md) → [Architecture](ARCHITECTURE.md) → [Verification](VERIFICATION.md) | Quick orientation, then inspect code |
| **Research reproducer** | [Verification](VERIFICATION.md) → [Score-ingestion protocol](../research/score_ingestion/README.md) → [Formal solver](../research/pronunciation_rhythm/README.md) | Depends on the experiment |

## What the public repository contains

- A Next.js user interface for exploring Raag/Taal descriptions and constructed formal-alignment examples.
- A Python FastAPI service for synthesis, internal ranking baselines and symbolic-score diagnostics.
- A conservative MuseScore XML parser; a tie-chain normalization process; an exact formal DP and a formal ambiguity counter.
- Fixture-based test suites, runnable CI checks, historical research code, model artifacts and provenance notes.

## What it does **not** establish

- Accurate lyric alignment on unseen singing performances, independently adjudicated syllables or authentic pronunciation.
- A newly invented DP algorithm or state-of-the-art model superiority.
- Independently verified Raag/Taal recommendations or expert consensus.
- A public hosted demo or complete compatibility with all MuseScore polyphony.

The public source is intended to be inspectable and reproducible within the declared assumptions. See [Results & limitations](RESULTS_AND_LIMITATIONS.md) before quoting accuracy numbers.

## Important ownership and privacy note

The included [MIT license](../LICENSE) and existing attribution must be reviewed by the repository owner; do not infer sole authorship or originality from the fact that code is publicly hosted. See [Credits and rights](PROJECT_CREDITS_AND_RIGHTS.md). Keep academic records, personal addresses, application essays, API keys and private data out of public issues and commits.
