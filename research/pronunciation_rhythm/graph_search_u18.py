"""Upgrade 18: independent finite-state-style weighted DAG shortest-path baseline.

Research-only formal symbols. NOT a phonological WFST, not an OpenFst binding,
not an algorithmic novelty claim. States are (candidate, syllable, event-position).
Edges consume a contiguous nonempty span of formal rhythm events and carry
nonnegative additive costs. Exact uniform-cost search has the same optimum as
brute enumeration and the existing DP. A search-budget cutoff returns
INCOMPLETE, never a false infeasibility conclusion.
"""
from __future__ import annotations

from dataclasses import dataclass
from heapq import heappush, heappop
from typing import Optional

from .core import AlignmentCase, Solution, SolveResult, verify_solution


@dataclass(frozen=True)
class GraphReport:
    status: str  # FEASIBLE | INFEASIBLE | INCOMPLETE
    solution: Optional[Solution]
    popped_states: int
    eligible_edges: int
    checked_edges: int
    search_budget: Optional[int]
    witness_verified: bool
    reason: str


def _graph_edges(case: AlignmentCase, candidate_index: int, syllable: int, start: int):
    """Independently implement span eligibility and additive path weights."""
    spec = case.rhythm
    candidate = case.candidates[candidate_index]
    events = spec.events
    n = len(events)
    if syllable >= len(candidate.syllables) or start >= n:
        return
    locked = spec.locked_events
    for end in range(start + 1, min(n, start + spec.max_events_per_syllable) + 1):
        ticks = sum(events[start:end])
        if not spec.min_syllable_ticks <= ticks <= spec.max_syllable_ticks:
            continue
        left_tick, right_tick = sum(events[:start]), sum(events[:end])
        if any(left_tick < b < right_tick for b in spec.boundaries):
            continue
        if any(start <= event < end and candidate.syllables[syllable] != required
               for event, required in locked):
            continue
        weight = end - start - 1
        if candidate.ideal_ticks:
            weight += abs(ticks - candidate.ideal_ticks[syllable])
        yield (end, weight)


def shortest_path(case: AlignmentCase, max_pops: Optional[int] = None) -> GraphReport:
    """Uniform-cost search over implicit pronunciation x rhythm graph.

    Tie-break canonical (total_cost, candidate_key, alignment_ends).
    Prior cost is paid at the source. Any imposed budget stops with INCOMPLETE
    if no optimal goal has been popped, even if no feasible path found yet.
    """
    if max_pops is not None and max_pops < 1:
        raise ValueError("max_pops must be positive if provided")
    # Heap tuple: cost, candidate key, ends, candidate index, syllable index, event pos.
    heap = []
    best = {}
    for ci, candidate in enumerate(case.candidates):
        node = (ci, 0, 0)
        tag = (candidate.prior, candidate.key, ())
        best[node] = tag
        heappush(heap, (*tag, *node))
    popped, checked, eligible = 0, 0, 0
    n = len(case.rhythm.events)
    while heap:
        if max_pops is not None and popped >= max_pops:
            return GraphReport("INCOMPLETE", None, popped, eligible, checked, max_pops,
                               False, "Budget exhausted; infeasibility NOT established")
        cost, key, ends, ci, idx, pos = heappop(heap)
        state = (ci, idx, pos)
        if best.get(state) != (cost, key, ends):
            continue
        popped += 1
        if idx == len(case.candidates[ci].syllables) and pos == n:
            sol = Solution(key, ends, cost)
            if not verify_solution(case, sol):
                raise AssertionError("Graph search returned an invalid formal witness")
            return GraphReport("FEASIBLE", sol, popped, eligible, checked, max_pops,
                               True, "Optimal feasible path found under supplied formal constraints")
        if idx == len(case.candidates[ci].syllables):
            continue
        start_end = min(n, pos + case.rhythm.max_events_per_syllable)
        checked += max(0, start_end - pos)
        for end, weight in _graph_edges(case, ci, idx, pos):
            eligible += 1
            successor = (ci, idx + 1, end)
            tag = (cost + weight, key, ends + (end,))
            if successor not in best or tag < best[successor]:
                best[successor] = tag
                heappush(heap, (*tag, *successor))
    return GraphReport("INFEASIBLE", None, popped, eligible, checked, max_pops,
                       False, "Exhausted complete finite graph: no formal path exists")


def as_solve_result(report: GraphReport) -> SolveResult:
    if report.status == "INCOMPLETE":
        raise ValueError("Cannot coerce incomplete search to FEASIBLE/INFEASIBLE")
    return SolveResult(report.status, report.solution, report.eligible_edges)
