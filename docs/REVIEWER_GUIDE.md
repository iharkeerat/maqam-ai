# MAQAM AI — two-minute reviewer guide

**Type:** inspectable research software prototype in computational musicology. **Key boundary:** exact formal optimization is validated against constructed constraints; musical correctness on independent performances is not.

## 1. Research question

How can symbolic notation and explicit mathematical constraints support auditable syllable-to-note hypotheses while clearly exposing cases where multiple alignments are consistent with the available evidence?

A related exploratory thread studies Raag/Taal knowledge and text-based ranking. Neither thread is presented here as a validated artistic expert system.

## 2. Inspect actual code

| What to inspect | Where | Why |
|---|---|---|
| Run the demo | [`portfolio_smoke_demo.py`](../portfolio_smoke_demo.py) | Constructed XML, tie normalization, formal result, safe API responses |
| Exact optimizer and independent check | [`research/pronunciation_rhythm/core.py`](../research/pronunciation_rhythm/core.py) | Formal DP, exhaustive reference and witness validation |
| Score parsing | [`research/score_ingestion/notation_adapter.py`](../research/score_ingestion/notation_adapter.py) | Conservative MSCX extraction and explicit unsupported cases |
| Tie normalization and API integration | [`research/score_ingestion/integration.py`](../research/score_ingestion/integration.py) · [`backend/main.py`](../backend/main.py) | How source indices and API outputs are linked |
| Formal ambiguity | [`research/score_ingestion/identifiability.py`](../research/score_ingestion/identifiability.py) · [`locked_identifiability_v10.py`](../research/score_ingestion/locked_identifiability_v10.py) | Counts alternate feasible formal mappings |
| Automated evidence | [CI workflow](../.github/workflows/ci.yml) · [Verification](VERIFICATION.md) | Tests, typecheck, lint, frontend build |

## 3. Reproduce in two commands

At the repository root with Python 3.11+:

```bash
python -m pip install -r requirements.txt
python portfolio_smoke_demo.py
```

Look for `original_notated_chords: 3`, `normalized_events_after_tie_collapse: 2`, `formal_chord_start_indices: [0, 2]`, and `real_world_alignment_accuracy_evaluated: false`. These are checks on a **constructed** musical example.

To inspect the web app: `cd web && npm ci && npm run dev`, then open `http://localhost:3000/alignment-lab`. This local page is not a hosted demo.

## 4. What the algorithm can and cannot prove

The exact DP solves a **specified formal objective**. Without informative targets, its baseline cost is the same for every feasible partition: `N − K`, where N is the number of formal note events and K the externally given syllable count. Therefore a mathematically exact optimum need not recover real lyric placement. See [Formal method](FORMAL_METHOD.md).

Score parsing currently rejects some multi-voice, overlapping-time and other unsupported structures. Source-side investigations uncovered both useful tie signals and slur counterexamples. These are informative limitations, not performance gains. See [Results & limitations](RESULTS_AND_LIMITATIONS.md).

## 5. What would substantiate a scientific contribution next?

An independently specified research question, fuller notation support, external syllabification or stress evidence, annotation provenance, a genuinely untouched score test set, competitive baselines, and statistical uncertainty. Do not infer that these are already completed.

## 6. Attribution and research integrity

The code is presented as a portfolio source snapshot. Verify author/assistant/third-party contributions with the repository owner before attributing invention or authorship. The MIT copyright notice by itself is not independent proof of who designed every component. Refer to [Credits and rights](PROJECT_CREDITS_AND_RIGHTS.md).
