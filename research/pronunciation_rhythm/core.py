"""Exact finite reference solvers for a formally specified toy alignment task.

All symbols and pronunciations are constructed formal examples. The rhythmic
constraints are simplified cyclic-tick conditions, not validated Taal theory.
Algorithmic novelty is NOT claimed: enumerating cuts and dynamic programming are
well-established techniques.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from typing import Optional


@dataclass(frozen=True)
class Candidate:
    key: str
    syllables: tuple[str, ...]
    prior: int = 0
    ideal_ticks: tuple[int, ...] = ()
    evidence: str = "constructed_formal_only"

    def __post_init__(self) -> None:
        if not self.key or not self.syllables or any(not s for s in self.syllables):
            raise ValueError("Candidate requires a key and nonempty syllables")
        if self.prior < 0 or (self.ideal_ticks and (len(self.ideal_ticks) != len(self.syllables)
                             or any(d < 1 for d in self.ideal_ticks))):
            raise ValueError("Invalid prior or target syllable durations")
        if self.evidence != "constructed_formal_only":
            raise ValueError("This formal pilot may not assert linguistic verification")


@dataclass(frozen=True)
class RhythmSpec:
    events: tuple[int, ...]
    cycle_ticks: int
    min_syllable_ticks: int = 1
    max_syllable_ticks: int = 16
    max_events_per_syllable: int = 3
    # Tick positions where a syllable must end (formal phrase/section boundaries).
    boundaries: tuple[int, ...] = ()
    # (event index, exact formal syllable token) pairs the user has locked.
    locked_events: tuple[tuple[int, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.events or any(x < 1 for x in self.events):
            raise ValueError("Positive event durations required")
        if self.cycle_ticks <= 0 or sum(self.events) % self.cycle_ticks:
            raise ValueError("Total event duration must span complete formal cycles")
        if self.min_syllable_ticks <= 0 or self.max_syllable_ticks < self.min_syllable_ticks:
            raise ValueError("Invalid syllable duration bounds")
        if self.max_events_per_syllable < 1:
            raise ValueError("Invalid max events per syllable")
        tick_positions = {0}
        t = 0
        for v in self.events:
            t += v
            tick_positions.add(t)
        if len(self.boundaries) != len(set(self.boundaries)) or any(
            b <= 0 or b >= t or b not in tick_positions for b in self.boundaries
        ):
            raise ValueError("Boundaries must be distinct internal event boundaries")
        event_indexes = [i for i, _ in self.locked_events]
        if len(event_indexes) != len(set(event_indexes)) or any(
            i < 0 or i >= len(self.events) or not s for i, s in self.locked_events
        ):
            raise ValueError("Invalid or duplicate locked events")


@dataclass(frozen=True)
class AlignmentCase:
    key: str
    candidates: tuple[Candidate, ...]
    rhythm: RhythmSpec
    provenance: str = "constructed_formal_only"

    def __post_init__(self) -> None:
        if not self.key or not self.candidates or len({c.key for c in self.candidates}) != len(self.candidates):
            raise ValueError("Need case key and uniquely keyed candidate paths")
        if self.provenance != "constructed_formal_only":
            raise ValueError("No real-world pronunciation evidence is provided")


@dataclass(frozen=True)
class Solution:
    candidate_key: str
    # End-exclusive event index of every syllable; strictly increasing; last == n.
    ends: tuple[int, ...]
    cost: int


@dataclass(frozen=True)
class SolveResult:
    status: str
    solution: Optional[Solution]
    expansions: int


def _validate_mapping(case: AlignmentCase, candidate: Candidate, ends: tuple[int, ...]) -> Optional[int]:
    spec = case.rhythm
    n = len(spec.events)
    if len(ends) != len(candidate.syllables) or not ends or ends[-1] != n:
        return None
    if any(end < 1 or end > n for end in ends) or any(a >= b for a, b in zip((0,) + ends[:-1], ends)):
        return None
    costs = candidate.prior
    start = 0
    boundary_set = set(spec.boundaries)
    prefix = [0]
    for d in spec.events:
        prefix.append(prefix[-1] + d)
    locked = dict(spec.locked_events)
    for index, end in enumerate(ends):
        ticks = prefix[end] - prefix[start]
        if end - start > spec.max_events_per_syllable:
            return None
        if not spec.min_syllable_ticks <= ticks <= spec.max_syllable_ticks:
            return None
        if any(prefix[start] < b < prefix[end] for b in boundary_set):
            return None
        if any(candidate.syllables[index] != locked[event]
               for event in range(start, end) if event in locked):
            return None
        costs += (end - start - 1)  # transparently disclosed melisma cost
        if candidate.ideal_ticks:
            costs += abs(ticks - candidate.ideal_ticks[index])
        start = end
    return costs


def verify_solution(case: AlignmentCase, proposed: Solution) -> bool:
    """Independent witness checker with separate constraint/objective implementation.

    Deliberately does NOT call the oracle's `_validate_mapping` routine or a
    search algorithm, to reduce common-mode mistakes between solver and checker.
    """
    match = next((c for c in case.candidates if c.key == proposed.candidate_key), None)
    if match is None or len(proposed.ends) != len(match.syllables):
        return False
    spec = case.rhythm
    total_events = len(spec.events)
    starts = (0,) + proposed.ends[:-1]
    if proposed.ends[-1] != total_events:
        return False
    total_cost = match.prior
    elapsed = 0
    for i, (start, end) in enumerate(zip(starts, proposed.ends)):
        if not 0 <= start < end <= total_events:
            return False
        count = end - start
        if count > spec.max_events_per_syllable:
            return False
        duration = sum(spec.events[start:end])
        if duration < spec.min_syllable_ticks or duration > spec.max_syllable_ticks:
            return False
        tick_start = sum(spec.events[:start])
        tick_end = tick_start + duration
        for boundary in spec.boundaries:
            if tick_start < boundary < tick_end:
                return False
        for event_index, required in spec.locked_events:
            if start <= event_index < end and match.syllables[i] != required:
                return False
        total_cost += count - 1
        if match.ideal_ticks:
            total_cost += abs(duration - match.ideal_ticks[i])
        elapsed = end
    return elapsed == total_events and total_cost == proposed.cost


def _best(solutions: list[Solution]) -> Optional[Solution]:
    return min(solutions, key=lambda s: (s.cost, s.candidate_key, s.ends)) if solutions else None


def exact_oracle(case: AlignmentCase, keys: Optional[set[str]] = None) -> SolveResult:
    """Independent brute-force reference enumerating EVERY possible cut assignment.

    Complexity exponential in event count; appropriate only to bounded tests.
    """
    n = len(case.rhythm.events)
    sols = []
    expanded = 0
    for cand in case.candidates:
        if keys is not None and cand.key not in keys:
            continue
        k = len(cand.syllables)
        if k > n:
            continue
        for cuts in combinations(range(1, n), k - 1):
            ends = tuple(cuts) + (n,)
            expanded += 1
            score = _validate_mapping(case, cand, ends)
            if score is not None:
                sols.append(Solution(cand.key, ends, score))
    win = _best(sols)
    return SolveResult("FEASIBLE" if win else "INFEASIBLE", win, expanded)


def top_k(case: AlignmentCase, k: int = 1) -> SolveResult:
    if k < 1:
        raise ValueError("k must be positive")
    ordered = sorted(case.candidates, key=lambda c: (c.prior, c.key))
    return exact_oracle(case, {c.key for c in ordered[:k]})


def exhaustive_two_stage(case: AlignmentCase) -> SolveResult:
    # Each pronunciation is solved independently and EXACTLY; no top-k loss.
    results = [exact_oracle(case, {candidate.key}) for candidate in case.candidates]
    win = _best([result.solution for result in results if result.solution is not None])
    return SolveResult("FEASIBLE" if win else "INFEASIBLE", win,
                       sum(result.expansions for result in results))


def composed_dp(case: AlignmentCase) -> SolveResult:
    """Exact dynamic-programming/composition baseline (NOT a new algorithm).

    DP caches suffix states (syllable index, event index) within each candidate.
    Both DP and exhaustive solvers use the identical hard constraints/objective.
    """
    spec = case.rhythm
    events = spec.events
    n = len(events)
    prefix = [0]
    for d in events:
        prefix.append(prefix[-1] + d)
    borders = set(spec.boundaries)
    locked = dict(spec.locked_events)
    all_solutions: list[Solution] = []
    expanded = 0
    for cand in case.candidates:
        syllables = cand.syllables

        @lru_cache(None)
        def suffix(index: int, start: int) -> Optional[tuple[int, tuple[int, ...]]]:
            nonlocal expanded
            if index == len(syllables):
                return (0, ()) if start == n else None
            best_value = None
            for end in range(start + 1, min(n, start + spec.max_events_per_syllable) + 1):
                expanded += 1
                ticks = prefix[end] - prefix[start]
                if ticks < spec.min_syllable_ticks or ticks > spec.max_syllable_ticks:
                    continue
                if any(prefix[start] < b < prefix[end] for b in borders):
                    continue
                if any(locked[e] != syllables[index] for e in range(start, end) if e in locked):
                    continue
                tail = suffix(index + 1, end)
                if tail is None:
                    continue
                local = end - start - 1
                if cand.ideal_ticks:
                    local += abs(ticks - cand.ideal_ticks[index])
                value = (local + tail[0], (end,) + tail[1])
                if best_value is None or value < best_value:
                    best_value = value
            return best_value

        result = suffix(0, 0)
        if result is not None:
            solution = Solution(cand.key, result[1], result[0] + cand.prior)
            if not verify_solution(case, solution):
                raise AssertionError("DP returned invalid witness")
            all_solutions.append(solution)
    win = _best(all_solutions)
    return SolveResult("FEASIBLE" if win else "INFEASIBLE", win, expanded)
