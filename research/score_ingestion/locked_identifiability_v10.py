"""V10 exact lock-conditioned formal ambiguity counts for V9 lock trace.

For the score preview's *untargeted*, single-candidate, positive-event model,
any feasible K-span segmentation of N events has objective cost N-K. Thus the
number of legal segmentations equals the number of equal-cost optimal paths.

The code below uses only N, K, max_span and *caller-provided formal locks*.
It never accesses, requests or infers score lyric annotation positions. It
is not a confidence measure, posterior probability or singing predictor.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LockedFormalIdentifiability:
    exact_equal_cost_paths: int
    feasible_start_ranges: tuple[tuple[int, int], ...]
    ambiguous_syllable_starts: int
    forced_syllable_starts: int


def analyze_locked_formal_paths(
    n: int,
    k: int,
    max_span: int,
    locks: tuple[tuple[int, int], ...] = (),
) -> LockedFormalIdentifiability:
    """Count legal monotone K-part event partitions with event-to-token locks.

    Each lock (event_i, syllable_j) requires that entire event to be assigned
    to the indexed syllable. All parts must have lengths in [1, max_span].
    The first part begins at event 0 and the last ends at event N.

    Prefix and suffix path counts independently certify each possible onset
    position: syllable j can begin at p iff forward[j,p] and backward[j,p]
    are both positive. This is exact arbitrary-precision integer arithmetic.
    """
    if any(type(q) is not int for q in (n, k, max_span)):
        raise TypeError('N, K and max_span must be integers')
    if not 1 <= n <= 120 or not 1 <= k <= 120 or not 1 <= max_span <= 8:
        raise ValueError('V10 exact lock audit limited to 1..120 events/syllables and span 1..8')
    locks = tuple(locks)
    by_event: dict[int, int] = {}
    for lock in locks:
        if not isinstance(lock, tuple) or len(lock) != 2 or any(type(t) is not int for t in lock):
            raise TypeError('each formal lock must be an (int event, int syllable) tuple')
        event, syllable = lock
        if not (0 <= event < n and 0 <= syllable < k):
            raise ValueError('formal lock outside event or syllable range')
        if event in by_event:
            raise ValueError('duplicate formal lock event')
        by_event[event] = syllable
    if k > n or n > k * max_span:
        return LockedFormalIdentifiability(0, (), 0, 0)

    # conflict[j][p] = # of assignments incompatible with syllable j in [0,p).
    conflicts = [[0]*(n+1) for _ in range(k)]
    for j in range(k):
        for event in range(n):
            required = by_event.get(event)
            conflicts[j][event+1] = conflicts[j][event] + (required is not None and required != j)

    def legal(j: int, p: int, end: int) -> bool:
        return conflicts[j][end] == conflicts[j][p]

    forward = [[0]*(n+1) for _ in range(k+1)]
    forward[0][0] = 1
    for j in range(k):
        for start, ways in enumerate(forward[j]):
            if not ways:
                continue
            for end in range(start+1, min(n,start+max_span)+1):
                if legal(j, start, end):
                    forward[j+1][end] += ways

    total = forward[k][n]
    if not total:
        return LockedFormalIdentifiability(0, (), 0, 0)

    backward = [[0]*(n+1) for _ in range(k+1)]
    backward[k][n] = 1
    for j in range(k-1, -1, -1):
        for start in range(n-1, -1, -1):
            for end in range(start+1, min(n,start+max_span)+1):
                if legal(j, start, end):
                    backward[j][start] += backward[j+1][end]

    if backward[0][0] != total:
        raise AssertionError('independent forward/backward formal path counts disagree')

    ranges = []
    for j in range(k):
        possible = [pos for pos in range(n) if forward[j][pos] and backward[j][pos]]
        if not possible:
            raise AssertionError('nonzero path count has no feasible onset for syllable')
        ranges.append((possible[0],possible[-1]))
    ambiguous = sum(a != b for a,b in ranges)
    return LockedFormalIdentifiability(total, tuple(ranges), ambiguous, k-ambiguous)


def summarize_lock_trace_ambiguity(
    n: int, k: int, max_span: int,
    locks: tuple[tuple[int,int],...],
    normalized_groups: list[list[int]],
) -> dict[str, object]:
    if len(normalized_groups) != n or any(not g for g in normalized_groups):
        raise ValueError('normalized group mapping does not match event count')
    report = analyze_locked_formal_paths(n, k, max_span, locks)
    original_indices = [g[0] for g in normalized_groups]
    return {
        'model':'LOCK_CONDITIONED_UNTARGETED_FORMAL_PARTITIONS',
        'number_of_equal_cost_optimal_paths':str(report.exact_equal_cost_paths),
        'unique_formal_path':report.exact_equal_cost_paths==1,
        'number_of_syllable_starts_with_multiple_possible_positions':report.ambiguous_syllable_starts,
        'number_of_syllable_starts_forced_to_one_position':report.forced_syllable_starts,
        'first_ten_possible_original_chord_index_ranges':[
            [original_indices[a],original_indices[b]] for a,b in report.feasible_start_ranges[:10]
        ],
        'user_supplied_lock_count':len(locks),
        'all_feasible_paths_have_same_cost':report.exact_equal_cost_paths>0,
        'formal_minimum_cost':n-k if report.exact_equal_cost_paths else None,
        'evidence_limitation':'Counts formal equal-cost paths consistent with user locks; not probabilities, confidence, score lyric gold or singing accuracy',
    }
