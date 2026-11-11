"""V9 experimental compact pointer-cached lock-edit DP over the frozen A2 graph.

This reconstructs a well-known dynamic-programming *representation* from the V8
A2 formal DAG.  It does not import the separate 26-Oct pointer-cache release,
which was not available in this runtime.  It is NOT a new algorithm and never
claims Hindi/Punjabi/singing alignment validity.

Instead of retaining O(K)-length optimal endpoint suffix tuples at each state,
cache only (suffix_cost, next_endpoint) and reconstruct the chosen witness by
following cached pointers. The static graph, weights, legality and tie-breaking
come directly from FixedAlignmentDAG, not from score-annotation gold.
"""
from __future__ import annotations

from dataclasses import dataclass
from heapq import heappush, heappop
from typing import Optional

from .core import AlignmentCase, Solution, SolveResult, verify_solution
from .incremental_a2 import FixedAlignmentDAG, State

# Terminal goal is represented by (0, -1); nonterminal by (cost, next end).
CompactValue = Optional[tuple[int, int]]


@dataclass(frozen=True)
class PointerEditStats:
    edited_event_indexes: tuple[int, ...]
    seeded_states: int
    recomputed_states: int
    changed_state_values: int
    edges_scanned: int
    static_states: int
    static_edges: int
    status: str


class PointerCachedLockDP:
    """Pointer-valued incremental shortest-path DP for lock-only changes.

    `update` validates requests prior to any mutation, respects all frozen
    hard constraints, and reproduces the canonical (cost, key, ends) optimum.
    Its cached *source case* is immutable except for lock assignments.
    """

    def __init__(self, case: AlignmentCase):
        self.graph = FixedAlignmentDAG(case)
        self.locks = case.rhythm.locked_events
        locked = dict(self.locks)
        self.values: dict[State, CompactValue] = {}
        for state in self.graph.order:
            self.values[state], _ = self._calculate(state, locked)

    def _calculate(self, state: State, locks: dict[int, str]) -> tuple[CompactValue, int]:
        ci, i, p = state
        cand = self.graph.case.candidates[ci]
        if i == len(cand.syllables):
            return ((0, -1) if p == self.graph.n else None), 0
        best = None
        examined = 0
        for dest, weight, end in self.graph.edges[state]:
            examined += 1
            if any(event in locks and locks[event] != cand.syllables[i]
                   for event in range(p, end)):
                continue
            suffix = self.values.get(dest)
            if suffix is None:
                continue
            option = (weight + suffix[0], end)
            # Among equal costs, the first cut is enough to compare suffix
            # endpoint tuples because at one (ci,i,p), each 'end' is unique.
            if best is None or option < best:
                best = option
        return best, examined

    def _witness(self, ci: int) -> Optional[tuple[int, tuple[int, ...]]]:
        case = self.graph.case
        n = self.graph.n
        cand = case.candidates[ci]
        root = (ci, 0, 0)
        value = self.values.get(root)
        if value is None:
            return None
        ends = []
        pos = 0
        for i in range(len(cand.syllables)):
            state = (ci, i, pos)
            v = self.values.get(state)
            if v is None or v[1] <= pos or v[1] > n:
                raise AssertionError(f'broken pointer at {state}')
            pos = v[1]
            ends.append(pos)
        if pos != n:
            raise AssertionError('pointer path does not reach goal')
        return value[0], tuple(ends)

    def result(self) -> SolveResult:
        winners = []
        for ci, cand in enumerate(self.graph.case.candidates):
            witness = self._witness(ci)
            if witness is not None:
                cost, ends = witness
                winners.append((cost + cand.prior, cand.key, ends))
        if not winners:
            return SolveResult('INFEASIBLE', None, 0)
        cost, key, ends = min(winners)
        sol = Solution(key, ends, cost)
        if not verify_solution(self.graph._with_locks(self.locks), sol):
            raise AssertionError('pointer-cached witness failed independent verification')
        return SolveResult('FEASIBLE', sol, 0)

    def update(self, locks: tuple[tuple[int, str], ...]) -> tuple[SolveResult, PointerEditStats]:
        # Fail closed before modifying state, even for duplicate/invalid locks.
        self.graph._with_locks(locks)
        before, after = dict(self.locks), dict(locks)
        edited = tuple(sorted(index for index in before.keys() | after.keys()
                              if before.get(index) != after.get(index)))
        roots: set[State] = set()
        for event in edited:
            roots.update(self.graph.affected.get(event, ()))
        pending: list[tuple[int, int, int]] = []
        scheduled: set[State] = set()

        def push(state: State):
            if state not in scheduled:
                scheduled.add(state)
                ci, i, pos = state
                heappush(pending, (-i, ci, pos))

        for state in roots:
            push(state)
        recomputed = changed = edges = 0
        while pending:
            minus_i, ci, pos = heappop(pending)
            state = (ci, -minus_i, pos)
            scheduled.remove(state)
            candidate, scanned = self._calculate(state, after)
            recomputed += 1
            edges += scanned
            if candidate != self.values[state]:
                self.values[state] = candidate
                changed += 1
                for parent in self.graph.parents.get(state, ()):
                    push(parent)
        self.locks = locks
        result = self.result()
        return result, PointerEditStats(
            edited, len(roots), recomputed, changed, edges,
            self.graph.static_states, self.graph.static_edges, result.status)

    def full_recompute(self, locks: tuple[tuple[int, str], ...]) -> SolveResult:
        """Independent pointer-state rebuild on the shared frozen graph."""
        self.graph._with_locks(locks)
        old = self.values
        try:
            values: dict[State, CompactValue] = {}
            self.values = values
            lockdict = dict(locks)
            scanned = 0
            for state in self.graph.order:
                values[state], n = self._calculate(state, lockdict)
                scanned += n
            original_locks = self.locks
            self.locks = locks
            try:
                r = self.result()
                return SolveResult(r.status, r.solution, scanned)
            finally:
                self.locks = original_locks
        finally:
            self.values = old
