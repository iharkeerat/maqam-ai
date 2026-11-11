"""Exact degeneracy audit for the V7/V8 *untargeted* formal score preview.

The preview's candidate uses no lexical evidence, no ideal syllable durations,
no locked events and no score-derived lyric constraints. Each full segmentation
of N positive note events into K nonempty syllable spans of length <= M has
identical native DP cost N-K. This module counts those paths independently of
native composed_dp and reports all potentially ambiguous syllable starts.

These are formal alternatives, not probabilities or musical correctness scores.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AmbiguityReport:
    feasible: bool
    exact_equal_cost_paths: int
    formal_min_cost: int | None
    nonunique_start_count: int
    start_event_ranges: tuple[tuple[int, int], ...]


def count_compositions(n: int, k: int, max_span: int) -> int:
    """Exact number of ordered K-part compositions of N with parts in [1,M].

    O(N*K) via a sliding-window sum recurrence. No enumerating paths and no
    floating-point probabilities. A modest 350-event public API is supported.
    """
    if any(type(v) is not int for v in (n, k, max_span)):
        raise TypeError('N, K, M must be integers (not bool)')
    if not 1 <= n <= 350 or not 1 <= k <= 350 or not 1 <= max_span <= 32:
        raise ValueError('formal ambiguity audit limited to 1..350 events/syllables and span 1..32')
    if k > n or n > k * max_span:
        return 0
    prev = [0] * (n + 1)
    prev[0] = 1
    for _ in range(k):
        new = [0] * (n + 1)
        window = 0
        for total in range(1, n + 1):
            window += prev[total - 1]
            if total - max_span - 1 >= 0:
                window -= prev[total - max_span - 1]
            new[total] = window
        prev = new
    return prev[n]


def analyze_untargeted_score(n: int, k: int, max_span: int) -> AmbiguityReport:
    paths = count_compositions(n, k, max_span)
    if paths == 0:
        return AmbiguityReport(False, 0, None, 0, ())
    ranges = []
    for j in range(k):
        # j previous nonempty spans and k-j remaining nonempty spans.
        minimum = max(j, n - (k-j) * max_span)
        maximum = min(j * max_span, n - (k-j))
        if not (0 <= minimum <= maximum < n):
            raise AssertionError('inconsistent bounded-composition start interval')
        ranges.append((minimum, maximum))
    return AmbiguityReport(True, paths, n-k, sum(a != b for a,b in ranges), tuple(ranges))


def summarize_for_public_api(n: int, k: int, max_span: int, normalized_groups: list[list[int]]) -> dict:
    """Safe solver-facing summary; never reads or consumes annotated lyric gold."""
    if len(normalized_groups) != n:
        raise ValueError('group count mismatch')
    r = analyze_untargeted_score(n, k, max_span)
    starts = [g[0] for g in normalized_groups]
    if any(not g or g[0] < 0 for g in normalized_groups):
        raise ValueError('invalid original chord mapping')
    return {
        'model': 'UNIFORM_UNTARGETED_FORMAL_SEGMENTATION',
        'number_of_equal_cost_optimal_paths': str(r.exact_equal_cost_paths),
        'unique_formal_path': r.feasible and r.exact_equal_cost_paths == 1,
        'number_of_syllable_starts_with_multiple_possible_positions': r.nonunique_start_count,
        'first_ten_possible_original_chord_index_ranges': [
            [starts[a],starts[b]] for a,b in r.start_event_ranges[:10]
        ],
        'all_feasible_paths_have_same_cost': r.feasible,
        'formal_minimum_cost': r.formal_min_cost,
        'evidence_limitation': 'Counts alternative exact-cost formal partitions only; not confidence, probability, human lyric alignment, or sung timing',
    }


def formal_spans_crossing_rests(ends: tuple[int, ...], rest_gap_before: list[int]) -> list[int]:
    """Indexes of syllables whose formal note spans cross observed silence.

    A rest directly before event j falls *inside* the syllable span only if
    start < j < end.  If j == start, it precedes the syllable and is not a
    crossing.  This is a diagnostic, not a new musical constraint.
    """
    if any(type(e) is not int for e in ends) or any(a >= b for a,b in zip(ends,ends[1:])):
        raise ValueError('invalid solution end sequence')
    rest=set(rest_gap_before)
    crossed=[]
    start=0
    for i,end in enumerate(ends):
        if any(start < j < end for j in rest):
            crossed.append(i)
        start=end
    return crossed
