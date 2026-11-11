# MAQAM V7 — isolated symbolic score-to-formal solver bridge

## Scope

This is an **engineering integration into the locally available MAQAM v13.3 (Track A, stage A4) source snapshot**, not a replacement for later, separately packaged pointer-cache code. The exact `research.pronunciation_rhythm.core.composed_dp` and independent `verify_solution` are used unchanged. A score reader does not turn a constructed-formal solver into a validated musical lyric aligner.

Features:

- Parses both MuseScore 3 `<voice>`-wrapped and direct-measure event layouts, finite event durations and simple single-level tuplets.
- Rejects ambiguous multi-voice notation, timing operators, malformed notes and invalid note durations.
- Requires **single-pitch vocal note events** in the current tie-aware bridge; no silent polyphonic reduction.
- Collapses a tie continuation only when the preceding note has a matching **forward tie**, both pitches match, and there is no intervening rest. Merges chains and retains the full map back to source chord indices.
- Never treats a slur end as a compulsory syllable non-onset.
- Requires the syllable count to be **provided independently by the caller** (not inferred by the solver from score annotations).
- Private gold is an **independent file location**, not part of the inference input or API output. A gold label from the same score edition is *not* independent audio ground truth.

## CLI (from MAQAM project root)

```bash
python -m research.score_ingestion.cli /path/to/your_score.mscx \
  --syllables 18 \
  --public-dir /tmp/maqam_trial_solver_only \
  --private-dir /tmp/maqam_trial_reference_only
```

The named paths must be fresh and disjoint. The public output contains `SOLVER_INPUT.json`, `FORMAL_SETUP.json`, `FORMAL_OUTPUT.json`. The separate private folder contains reference lyric positions and a metadata audit. For an untrusted inference worker, **do not mount the private folder or original score**. Directory separation by itself is not a filesystem ACL.

The solver operates on a **note-event-only formal timeline** that omits rest time; its durations are exact integer scalings of original notation tick lengths. `original_written_onsets` are retained only for source mapping, not converted to real performance time. The rhythm is not verified Taal and the syllable strings are constructed formal placeholders.

## Optional FastAPI preview (only sanitized inference output)

```bash
uvicorn backend.main:app --reload
```

`POST /research/score/formal-preview` accepts JSON containing `mscx_xml` (original score XML string), `syllable_count` (external), and optional `max_events_per_syllable`. It returns the **formal** predicted original chord indices, feasibility, and disclaimers, never private lyric labels. API is capped at 350 normalized note events; further caller-supplied untrusted data should be handled with rate and resource limits if deploying publicly.

## Tests

```bash
python -m pytest -q tests/test_score_ingestion_v7.py tests/test_score_formal_preview_api_v7.py
python -m pytest -q
```

Inputs to these tests are all explicitly constructed synthetic MSCX. They verify software behavior, **not external alignment accuracy**.

## Original-source replay

`PINNED_OPENSCORE_V6.json` records the upstream commit `38c5db510224d9facdc4b08d741fc788cfb58ea8` and five source file Git blob hashes. Once actual OpenScore XML bytes are available in a pinned checkout, verify their blob identities and V6 parser results using `python scripts/replay_openscore_v7.py --score-root /path/to/Lieder`. Without those bytes, fail closed: do not claim local end-to-end source validation.

## Scientific decision

**GO** for software integration readiness. **NO-GO** for claiming learned lyric-note alignment quality, Hindi/Punjabi pronunciation, sangita/taal validity, or novel DP. Next scientific stage requires real scores on disk, broader notation support and an independent held-out comparison with fair baselines.
