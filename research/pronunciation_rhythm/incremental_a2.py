"""Track A2: exploratory lock-only incremental dynamic programming on a fixed DAG.

Well-established incremental DP principle, NOT a new algorithm. Formally
constructed syllable strings; not authentic Hindi/Punjabi data. Comparisons
against an optimized full-recomputation baseline on the SAME prebuilt graph.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from heapq import heappush, heappop
from typing import Optional

from .core import AlignmentCase, RhythmSpec, SolveResult, Solution, verify_solution

State = tuple[int, int, int]  # candidate index, syllable index, start event
Value = Optional[tuple[int, tuple[int, ...]]]  # minimum suffix cost, endpoint tuple


@dataclass(frozen=True)
class EditStats:
    edited_event_indexes: tuple[int, ...]
    seed_states: int
    recomputed_states: int
    changed_state_values: int
    edges_scanned: int
    static_states: int
    static_edges: int
    status: str


class FixedAlignmentDAG:
    """Precompute lock-independent legal spans; lock edits change edge validity.

    The edge geometry and cost remain frozen. Only locked_events may change.
    Supports arbitrary insert/delete/replace of locks in a single update.
    """

    def __init__(self, case: AlignmentCase):
        self.case = case
        self.base_rhythm = case.rhythm
        self.events = case.rhythm.events
        self.n = len(self.events)
        self.nodes: list[State] = []
        self.edges: dict[State, tuple[tuple[State, int, int], ...]] = {}
        self.parents: dict[State, set[State]] = defaultdict(set)
        self.affected: dict[int, set[State]] = defaultdict(set)
        pref = [0]
        for d in self.events:
            pref.append(pref[-1] + d)
        boundaries = case.rhythm.boundaries
        for ci, cand in enumerate(case.candidates):
            k = len(cand.syllables)
            for i in range(k + 1):
                for p in range(self.n + 1):
                    node = (ci, i, p)
                    self.nodes.append(node)
                    arcs = []
                    if i < k:
                        for q in range(p + 1, min(self.n, p + case.rhythm.max_events_per_syllable) + 1):
                            ticks = pref[q] - pref[p]
                            if not case.rhythm.min_syllable_ticks <= ticks <= case.rhythm.max_syllable_ticks:
                                continue
                            if any(pref[p] < b < pref[q] for b in boundaries):
                                continue
                            dest = (ci, i + 1, q)
                            weight = q - p - 1
                            if cand.ideal_ticks:
                                weight += abs(ticks - cand.ideal_ticks[i])
                            arcs.append((dest, weight, q))
                            self.parents[dest].add(node)
                            for evt in range(p, q):
                                self.affected[evt].add(node)
                    self.edges[node] = tuple(arcs)
        # Structural pruning is shared by incremental and full baselines:
        # retain only nodes on a root-to-goal path when ignoring locks. This
        # prevents artificially inflating the full-recomputation baseline.
        filtered: set[State] = set()
        for ci, cand in enumerate(case.candidates):
            root = (ci, 0, 0)
            forward = {root}
            todo = [root]
            while todo:
                u = todo.pop()
                for v, _, _ in self.edges[u]:
                    if v not in forward:
                        forward.add(v); todo.append(v)
            goal = (ci, len(cand.syllables), self.n)
            backward = {goal}
            todo = [goal]
            while todo:
                v = todo.pop()
                for u in self.parents.get(v, ()):
                    if u not in backward:
                        backward.add(u); todo.append(u)
            filtered.update((forward & backward) | {root})
        self.nodes = sorted(filtered)
        self.edges = {u: tuple(edge for edge in self.edges[u] if edge[0] in filtered)
                      for u in self.nodes}
        self.parents = defaultdict(set)
        self.affected = defaultdict(set)
        for u, arcs in self.edges.items():
            for v, _, end in arcs:
                self.parents[v].add(u)
                for evt in range(u[2], end):
                    self.affected[evt].add(u)
        self.static_edges = sum(len(x) for x in self.edges.values())
        self.static_states = len(self.nodes)
        self.order = tuple(sorted(self.nodes, key=lambda s: (-s[1], s[0], s[2])))

    def _with_locks(self, locks: tuple[tuple[int, str], ...]) -> AlignmentCase:
        old = self.base_rhythm
        rhythm = RhythmSpec(old.events, old.cycle_ticks, old.min_syllable_ticks,
                            old.max_syllable_ticks, old.max_events_per_syllable,
                            old.boundaries, locks)
        return AlignmentCase(self.case.key, self.case.candidates, rhythm)

    def _calculate(self, node: State, values: dict[State, Value],
                   locks: dict[int, str]) -> tuple[Value, int]:
        ci, i, p = node
        cand = self.case.candidates[ci]
        if i == len(cand.syllables):
            return ((0, ()) if p == self.n else None), 0
        best: Value = None
        examined = 0
        for dest, weight, end in self.edges[node]:
            examined += 1
            if any(evt in locks and locks[evt] != cand.syllables[i]
                   for evt in range(p, end)):
                continue
            suffix = values.get(dest)
            if suffix is None:
                continue
            proposal = (weight + suffix[0], (end,) + suffix[1])
            if best is None or proposal < best:
                best = proposal
        return best, examined

    def _get_result(self, values: dict[State, Value],
                    locks: tuple[tuple[int, str], ...], edges_count: int) -> SolveResult:
        winners = []
        for ci, candidate in enumerate(self.case.candidates):
            suffix = values[(ci, 0, 0)]
            if suffix is not None:
                winners.append((suffix[0] + candidate.prior, candidate.key, suffix[1]))
        if not winners:
            return SolveResult("INFEASIBLE", None, edges_count)
        cost, key, ends = min(winners)
        sol = Solution(key, ends, cost)
        check_case = self._with_locks(locks)
        if not verify_solution(check_case, sol):
            raise AssertionError("Incremental/full graph algorithm returned invalid witness")
        return SolveResult("FEASIBLE", sol, edges_count)

    def full_recompute(self, locks: tuple[tuple[int, str], ...]) -> tuple[SolveResult, int]:
        """Optimized full-DAG DP baseline reusing the same static graph index."""
        self._with_locks(locks)  # fail early on invalid user requests
        values: dict[State, Value] = {}
        checked = 0
        lockdict = dict(locks)
        for state in self.order:
            values[state], examined = self._calculate(state, values, lockdict)
            checked += examined
        return self._get_result(values, locks, checked), self.static_states


class IncrementalLockDP:
    """Basic dependency-propagating incremental update, using established ideas."""

    def __init__(self, case: AlignmentCase):
        self.graph = FixedAlignmentDAG(case)
        self.locks = case.rhythm.locked_events
        self.values: dict[State, Value] = {}
        for state in self.graph.order:
            self.values[state], _ = self.graph._calculate(state, self.values, dict(self.locks))

    def result(self) -> SolveResult:
        return self.graph._get_result(self.values, self.locks, 0)

    def update(self, new_locks: tuple[tuple[int, str], ...]) -> tuple[SolveResult, EditStats]:
        self.graph._with_locks(new_locks)
        before, after = dict(self.locks), dict(new_locks)
        changed = tuple(sorted(idx for idx in before.keys() | after.keys()
                               if before.get(idx) != after.get(idx)))
        roots: set[State] = set()
        for idx in changed:
            roots.update(self.graph.affected.get(idx, ()))
        queue: list[tuple[int, int, int]] = []
        scheduled: set[State] = set()

        def push(state: State):
            if state not in scheduled:
                scheduled.add(state)
                ci, i, pos = state
                heappush(queue, (-i, ci, pos))
        for node in roots:
            push(node)
        recomputed = affected_values = arcs = 0
        while queue:
            minus_i, ci, pos = heappop(queue)
            state = (ci, -minus_i, pos)
            scheduled.remove(state)
            proposed, count = self.graph._calculate(state, self.values, after)
            recomputed += 1
            arcs += count
            if proposed != self.values[state]:
                self.values[state] = proposed
                affected_values += 1
                for parent in self.graph.parents.get(state, ()):
                    push(parent)
        self.locks = new_locks
        result = self.result()
        return result, EditStats(changed, len(roots), recomputed, affected_values,
                                 arcs, self.graph.static_states, self.graph.static_edges,
                                 result.status)
