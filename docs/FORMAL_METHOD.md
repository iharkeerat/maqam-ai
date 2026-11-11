# Formal alignment method — what the math actually establishes

This is a **bounded symbolic-score research experiment**. It does not transcribe sung audio, independently infer pronunciation, or establish the correct alignment of real lyrics.

## Problem definition

- The input is an ordered set of N **normalized note events** (after valid tie-chain continuations are combined), with positive finite durations and optional hard constraints.
- K **formal syllable tokens** are supplied independently by the caller. The algorithm does not count or retrieve the original score's lyric labels as inference features.
- A feasible assignment partitions the ordered note events into K nonempty consecutive spans (subject to constraints such as maximum notes per syllable).
- The DP finds an exact minimum-cost feasible assignment. An independent verifier checks the returned witness; a separate counter can expose how many equally optimal formal partitions exist.

## A crucial limitation: the untargeted objective is constant

In the untargeted default objective, a span of L notes costs `L - 1`. Over K syllables covering N note events, total cost is:

```text
sum(span_length - 1) = N - K
```

**Every feasible partition has the same objective cost.** Therefore a specific DP output is determined by structural feasibility and tie-breaking, not by independent evidence that the selected lyric placement is musically correct. Exact search still matters for software correctness, but it cannot manufacture missing musical information.

For instance, five ordinary notes and three formal syllables with no extra constraints allow six contiguous partitions. Under the untargeted cost they all score 2; it would be misleading to call the chosen path a high-confidence interpretation.

## What can be read from notation?

The [MSCX adapter](../research/score_ingestion/notation_adapter.py) extracts a limited, conservative single-voice written-time representation. A note-level backward tie is accepted only when paired with a compatible forward tie and the same pitch. A slur is **not** equivalent to a tied sustain or an automatic syllable-continuation rule. Rests are not modeled as note events by the formal solver, although gap information is reported separately.

Unsupported mixed voices, overlapping timelines and uncertain timing are rejected instead of being silently guessed. See [Score ingestion README](../research/score_ingestion/README.md).

## Interpretation of the output

| Field | Meaning | What it is not |
|---|---|---|
| `predicted_original_chord_indices` | A source-index mapping for **one** formally optimal partition | Human-audited lyric timestamps |
| `formal_cost` | Objective score for that formal partition | Probability of musical correctness |
| `number_of_equal_cost_optimal_paths` | Exact number of formally optimal paths under assumptions | A confidence interval or posterior |
| `unique_formal_path` | Only one path meets the declared formal constraints | Proof that it is the real sung phrasing |
| `cost_is_not_singing_accuracy` | Explicit limitation flag | A benchmark measurement |

Read the [identifiability explainer](../research/score_ingestion/IDENTIFIABILITY_V8.md) for concrete ambiguity examples.

## What would be needed for scientific validation?

A well-defined independently supplied lyric transcript, syllable structure and/or lexical stress; a validated notation parser across multiple composers; a prospectively selected source corpus with untouched gold; comparisons against meaningful existing aligners and heuristics; and human or otherwise independent annotations. The public code **does not yet supply this evaluation**.

## Originality and attribution boundary

Exact dynamic programming, exhaustive baselines, tie handling and ambiguity counting build on established general techniques. The repository does not claim these primitives were invented here. For project citations, use [Research evidence and limitations](RESULTS_AND_LIMITATIONS.md) and the checked-in [literature audit](../research/literature/SEARCH_LOG.md).
