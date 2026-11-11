# MAQAM AI — Pronunciation/Rhythm Formal Reference Pilot (research step 14)

**Status: exploratory, mathematical/software verification only.** This directory
is an isolated research module; it does not change MAQAM's existing Raag,
Taal, text-processing, rendering, or frontend behavior. The earlier v11.9.0
benchmark artifacts are intentionally preserved.

## Exact research question

Given a finite set of **constructed formal** syllable paths, a cyclic event
schedule, and documented hard constraints, when does selecting a single path
before alignment cause a false report of infeasibility? Does exact exhaustive
pronunciation-first search agree with an exact composed dynamic program?

**It must agree** for the same candidate set, hard constraints, and objective:

`minimum over paths p [ minimum over alignments a for p cost(p,a) ]`

is algebraically the same optimization as `minimum over feasible pairs (p,a)`.
The numerical experiment is a correctness check, not an algorithmic discovery.

## Formal task / exclusions

- Positive-integer event durations, grouped into integer-length formal cycles.
- Every formal syllable consumes one or more *whole* consecutive events.
- Monotonic one-to-many syllable-to-event alignments; no syllable sharing of an event.
- Hard restrictions on syllable tick duration, maximum events per syllable,
  explicit phrase-boundary crossings, and locked formal syllable tokens.
- Cost = integer prior + number of extra events per syllable + absolute
  deviations from optional ideal durations. Consistent tie-break by cost,
  candidate key, then end indexes.
- Constructed syllable tokens like `a`, `b`, `c` are **not actual Hindi,
  Punjabi or Urdu pronunciations**. Neither source authenticity nor linguistic
  plausibility nor expressive musical quality is tested.
- Cyclic ticks here are an **abstract formal grid**, not a comprehensive
  definition of Teentaal or any authentic tradition-specific Taal.
- A complete brute-force oracle is exponential in event count; this pilot
  deliberately bounds event counts and does not promise runtime scalability.

## Reproduce

Run from the repository root:

```bash
python -m pytest -q tests/test_pronunciation_rhythm.py
python -m research.pronunciation_rhythm.pilot \
  --output reports/research/pronunciation_rhythm_pilot
```

Artifacts:

- `FORMAL_CASES.json`: all 150 deterministic, constructed evaluation cases.
- `PILOT_SUMMARY.json`: formal feasibility comparison and SHA-256 data digest.
- `PER_CASE_RESULTS.csv`: complete case-level baseline outcomes.
- `EXPERIMENT_PROTOCOL.json`: claim limits and exploratory registration status.

The pilot is **not confirmatory/preregistered**: researchers designed and
inspected cases and observed the results. Any future evaluation set must be
specified, frozen, and independently sourced *after* fixing the method.

## Five honest takeaways

1. A top-1 pronunciation pipeline can produce false infeasibility on this
   designed **formal task**. This is logically expected; it is not a discovery
   that 56.8% of real Hindi/Punjabi lyrics have that problem.
2. A top-2 pipeline is a stronger baseline, reducing many—but not all—failures.
3. Exhaustive two-stage and exact composed DP must give identical results
   under identical assumptions. The 150 case experiment tests that equality.
4. The DP and enumeration algorithms count different kinds of work. A lower
   number of one type of operation would not establish faster wall-clock time.
5. The next defensible step is independently justified pronunciation
   alternatives with reference provenance, then a **prospective** comparison
   against exhaustive, k-best and generic WFST/CSP baselines.

## Research decision

**GO** for a bounded software and formal-specification pilot. **NO CLAIM** of
novel solver, Hindi/Punjabi pronunciation correctness, Taal authenticity,
real-world false-infeasibility prevalence, or superiority over state of the art.
