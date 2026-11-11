"""Independent LPA*-style incremental shortest-path baseline for the fixed alignment DAG.

Derived from the established g/rhs consistency mechanism (Koenig et al., 2004).
This is a full-consistency, zero-heuristic, reverse-search specialization, NOT
an implementation of a published authors' exact source code and NOT a new method.

The existing A2 approach propagates changes in complete (cost, path) values;
this separate baseline propagates scalar g/rhs labels with a priority queue.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import itertools
from math import inf, isinf
from .core import AlignmentCase, SolveResult, Solution, verify_solution
from .incremental_a2 import FixedAlignmentDAG, State

@dataclass(frozen=True)
class DynamicSSSPStats:
    edited_events: int
    affected_seeds: int
    rhs_evaluations: int
    scanned_edges: int
    queue_pops: int
    settled_vertices: int
    peak_heap: int
    peak_pending: int
    cache_vertices: int
    status: str

class DynamicSSSPBaseline:
    """Maintain shortest suffix distances under edge validity toggles.

    g = committed cost and rhs = one-step lookahead. At convergence g=rhs
    for every state. Query is a complete exact shortest path, no hidden pruning.
    """
    def __init__(self, case: AlignmentCase):
        self.graph=FixedAlignmentDAG(case)
        self.locks=case.rhythm.locked_events
        self._lockmap=dict(self.locks)
        self.g:dict[State,float]={}
        self.rhs:dict[State,float]={}
        self._heap=[]
        self._pending={}
        self._serial=itertools.count()
        self._peak_heap=0
        self._peak_pending=0
        for u in self.graph.order:
            v,_=self._one_step(u)
            self.g[u]=v
            self.rhs[u]=v

    def _allowed(self,u,stop):
        ci,i,p=u
        label=self.graph.case.candidates[ci].syllables[i]
        return all(self._lockmap.get(evt,label)==label for evt in range(p,stop))

    def _one_step(self,u):
        ci,i,p=u
        if i==len(self.graph.case.candidates[ci].syllables):
            return (0 if p==self.graph.n else inf),0
        best=inf
        examined=0
        for dest,w,q in self.graph.edges[u]:
            examined+=1
            if self._allowed(u,q):
                value=w+self.g.get(dest,inf)
                if value<best:best=value
        return best,examined

    def _enqueue_if_inconsistent(self,u):
        if self.g[u]==self.rhs[u]:
            self._pending.pop(u,None)
        else:
            seq=next(self._serial)
            self._pending[u]=seq
            k=min(self.g[u],self.rhs[u])
            heapq.heappush(self._heap,(k,max(self.g[u],self.rhs[u]),seq,u))
            self._peak_heap=max(self._peak_heap,len(self._heap))
            self._peak_pending=max(self._peak_pending,len(self._pending))

    def _update_vertex(self,u):
        rhs,scanned=self._one_step(u)
        self.rhs[u]=rhs
        self._enqueue_if_inconsistent(u)
        return scanned

    def _result(self,expansions=0):
        # Reconstruct a canonical lexicographic optimum without borrowing A2 path cache.
        options=[]
        for ci,cand in enumerate(self.graph.case.candidates):
            root=(ci,0,0)
            if root not in self.g or isinf(self.g[root]):continue
            u=root
            ends=[]
            while u[1]<len(cand.syllables):
                possible=[(q,dest) for dest,w,q in self.graph.edges[u]
                          if self._allowed(u,q) and not isinf(self.g[dest])
                          and w+self.g[dest]==self.g[u]]
                if not possible:raise AssertionError('Dynamic-SSSP value has no valid witness')
                q,u=min(possible)
                ends.append(q)
            solution=Solution(cand.key,tuple(ends),int(self.g[root]+cand.prior))
            options.append(solution)
        if not options:
            return SolveResult('INFEASIBLE',None,expansions)
        best=min(options,key=lambda s:(s.cost,s.candidate_key,s.ends))
        if not verify_solution(self.graph._with_locks(self.locks),best):
            raise AssertionError('Dynamic-SSSP solution rejected by independent witness checker')
        return SolveResult('FEASIBLE',best,expansions)

    def result(self):return self._result()

    def update(self,new_locks:tuple[tuple[int,str],...]):
        self.graph._with_locks(new_locks) # validation before state mutation
        old=self._lockmap
        fresh=dict(new_locks)
        changed=sorted(i for i in old.keys()|fresh.keys() if old.get(i)!=fresh.get(i))
        self._lockmap=fresh
        scans=0; evaluations=0; queue_pops=0; settled=0
        seeds=set()
        for event in changed:seeds.update(self.graph.affected.get(event,()))
        for u in sorted(seeds):
            scans+=self._update_vertex(u);evaluations+=1
        while self._heap:
            _,_,seq,u=heapq.heappop(self._heap)
            if self._pending.get(u)!=seq:continue
            self._pending.pop(u)
            queue_pops+=1
            if self.g[u]>self.rhs[u]:
                self.g[u]=self.rhs[u]
            else:
                self.g[u]=inf
                scans+=self._update_vertex(u);evaluations+=1
            settled+=1
            for parent in self.graph.parents.get(u,()):
                scans+=self._update_vertex(parent);evaluations+=1
        self.locks=new_locks
        if self._pending:raise AssertionError('Nonempty pending queue after settlement')
        result=self._result(scans)
        return result,DynamicSSSPStats(len(changed),len(seeds),evaluations,scans,
                                     queue_pops,settled,self._peak_heap,self._peak_pending,
                                     len(self.g),result.status)
