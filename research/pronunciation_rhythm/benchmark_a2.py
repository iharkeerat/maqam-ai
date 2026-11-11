"""Track A Stage A2 -- reproducible exploratory interactive lock-edit benchmark.

NOT a prospective independent external study. No real pronunciations, singing,
novel search algorithm, or generalizable runtime advantage is claimed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import statistics
import time
from dataclasses import asdict
from pathlib import Path

from .core import AlignmentCase, Candidate, RhythmSpec, composed_dp
from .benchmark_u18 import cases as archived_cases
from .incremental_a2 import IncrementalLockDP

SEED = 20261024 + 2202
PROTOCOL = 'MAQAM_TRACK_A2_LOCK_UPDATES_EXPLORATORY_V1'


def stable(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode()


def new_scale_cases() -> list[AlignmentCase]:
    r = random.Random(SEED)
    result = []
    for i in range(36):
        n = [14, 20, 26, 32][i % 4]
        events = tuple(r.choice((1, 1, 2, 2, 3)) for _ in range(n))
        count = [2, 4, 6][i % 3]
        prefix = []
        p = 0
        for d in events[:-1]:
            p += d
            prefix.append(p)
        # Mix permissive and tight geometry to avoid only favorable workloads.
        borders = () if i % 3 == 0 else tuple(sorted(r.sample(prefix, (i % 3))))
        candidates = []
        for ci in range(count):
            k = min(n, max(2, n // 2 + r.randint(-3, 3)))
            syl = tuple(r.choice('abcde') for _ in range(k))
            candidates.append(Candidate(f'A2_scale_{i:02d}_C{ci}', syl,
                                        prior=ci % 4,
                                        ideal_ticks=tuple(r.randint(1, 4) for _ in range(k))))
        spec = RhythmSpec(events, sum(events),
                          min_syllable_ticks=1,
                          max_syllable_ticks=6 if i % 2 else 9,
                          max_events_per_syllable=3 if i % 2 else 5,
                          boundaries=borders)
        result.append(AlignmentCase(f'A2_scale_{i:02d}', tuple(candidates), spec))
    return result


def prepare() -> dict:
    collection = archived_cases() + new_scale_cases()
    rng = random.Random(SEED + 1)
    traces = []
    for case in collection:
        current = dict(case.rhythm.locked_events)
        n = len(case.rhythm.events)
        for j in range(12):
            if j < 8:
                kind = 'single'
                # A controlled, local UI edit workload: alternate add, change,
                # remove. Limits accumulating infeasibility from random locks.
                if j % 3 == 2:
                    if current:
                        current.pop(rng.choice(sorted(current)))
                else:
                    index = (rng.choice(sorted(current)) if current and j % 3 == 1
                             else rng.randrange(n))
                    c = rng.choice(case.candidates)
                    current[index] = (rng.choice(c.syllables) if rng.random() < .7
                                      else rng.choice('abcde'))
            elif j < 10:
                kind = 'multi'
                indexes = rng.sample(range(n), min(4, n))
                for index in indexes:
                    if index in current and rng.random() < .35:
                        del current[index]
                    else:
                        current[index] = rng.choice('abcde')
            elif j == 10:
                kind = 'wide'
                current = {idx: rng.choice('abcde') for idx in range(n)}
            else:
                kind = 'clear'
                current.clear()
            traces.append({'case_id': case.key, 'edit': j, 'family': kind,
                           'locks': [[idx, label] for idx, label in sorted(current.items())]})
    obj = {'protocol': PROTOCOL, 'seed': SEED, 'origin': 'constructed_formal_only',
           'cases': [asdict(c) for c in collection], 'edit_trace': traces,
           'case_family_counts': {'previously_inspected_u18': len(archived_cases()),
                                  'new_constructed_scale': len(new_scale_cases())}}
    return obj


def run(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    data = prepare()
    fixture_bytes = stable(data)
    (directory / 'FROZEN_CASES_AND_EDITS.json').write_bytes(fixture_bytes)
    records = []
    by_case = {}
    for t in data['edit_trace']:
        by_case.setdefault(t['case_id'], []).append(t)
    originals = archived_cases() + new_scale_cases()
    for case in originals:
        init_start = time.perf_counter_ns()
        engine = IncrementalLockDP(case)
        init_ns = time.perf_counter_ns() - init_start
        init_result = engine.result()
        baseline_result, _ = engine.graph.full_recompute(case.rhythm.locked_events)
        assert (init_result.status, init_result.solution) == (baseline_result.status, baseline_result.solution)
        # Independent preexisting exact DP with separate implementation.
        reference = composed_dp(case)
        assert (init_result.status, init_result.solution) == (reference.status, reference.solution)
        for t in by_case[case.key]:
            locks = tuple((int(i), str(s)) for i, s in t['locks'])
            # Alternate timing order to reduce systematic first/second bias.
            if t['edit'] % 2:
                f0 = time.perf_counter_ns()
                fresh, states = engine.graph.full_recompute(locks)
                full_ns = time.perf_counter_ns() - f0
                i0 = time.perf_counter_ns()
                changed, stats = engine.update(locks)
                incremental_ns = time.perf_counter_ns() - i0
            else:
                i0 = time.perf_counter_ns()
                changed, stats = engine.update(locks)
                incremental_ns = time.perf_counter_ns() - i0
                f0 = time.perf_counter_ns()
                fresh, states = engine.graph.full_recompute(locks)
                full_ns = time.perf_counter_ns() - f0
            if (changed.status, changed.solution) != (fresh.status, fresh.solution):
                raise AssertionError('Baseline mismatch for ' + str((case.key, t['edit'])))
            # All cases are constructed, but the old exact DP is still an
            # independent correctness check for every update.
            reference = composed_dp(engine.graph._with_locks(locks))
            if (changed.status, changed.solution) != (reference.status, reference.solution):
                raise AssertionError('Independent exact-DP mismatch')
            records.append({
                'case_id': case.key,
                'case_family': 'reused_u18' if not case.key.startswith('A2_') else 'new_scale',
                'edit': t['edit'], 'edit_family': t['family'],
                'num_events': len(case.rhythm.events),
                'num_candidates': len(case.candidates),
                'status': changed.status,
                'best_cost': changed.solution.cost if changed.solution else '',
                'candidate': changed.solution.candidate_key if changed.solution else '',
                'changed_events': len(stats.edited_event_indexes),
                'seeds': stats.seed_states,
                'incremental_states': stats.recomputed_states,
                'full_states': states,
                'incremental_edges_scanned': stats.edges_scanned,
                'full_edges_scanned': fresh.expansions,
                'changed_state_values': stats.changed_state_values,
                'incremental_ns': incremental_ns, 'full_ns': full_ns,
                'static_nodes': stats.static_states, 'static_edges': stats.static_edges,
                'initial_build_ns': init_ns,
                'exact_equivalence': True,
            })
    with (directory / 'CASE_LEVEL_RESULTS.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(records[0]))
        w.writeheader(); w.writerows(records)
    # Deterministic science results separate from volatile machine timing.
    deterministic = [{k: v for k, v in row.items()
                      if k not in ('incremental_ns', 'full_ns', 'initial_build_ns')}
                     for row in records]
    (directory / 'DETERMINISTIC_RESULTS.json').write_bytes(stable(deterministic))
    categories = {}
    for category in ('single', 'multi', 'wide', 'clear'):
        sub = [r for r in records if r['edit_family'] == category]
        denom_states = sum(r['full_states'] for r in sub)
        denom_edges = sum(r['full_edges_scanned'] for r in sub)
        categories[category] = {
            'updates': len(sub),
            'incremental_states': sum(r['incremental_states'] for r in sub),
            'full_states': denom_states,
            'recomputed_state_ratio': round(sum(r['incremental_states'] for r in sub)/denom_states, 6) if denom_states else None,
            'incremental_edges': sum(r['incremental_edges_scanned'] for r in sub),
            'full_edges': denom_edges,
            'scanned_edge_ratio': round(sum(r['incremental_edges_scanned'] for r in sub)/denom_edges, 6) if denom_edges else None,
            'aggregate_full_seconds': round(sum(r['full_ns'] for r in sub)/1e9, 5),
            'aggregate_incremental_seconds': round(sum(r['incremental_ns'] for r in sub)/1e9, 5),
            'feasible_updates': sum(r['status']=='FEASIBLE' for r in sub),
        }
    # Memory accounting: structural graph and complete DP cache both persist
    # across edits. No misleading memory-savings claim is made.
    summary = {
        'protocol': PROTOCOL,
        'epistemic_status': 'EXPLORATORY_AUTHOR_CONSTRUCTED_FORMAL_ONLY',
        'cases': len(originals), 'updates': len(records),
        'frozen_cases_and_edits_sha256': hashlib.sha256(fixture_bytes).hexdigest(),
        'deterministic_results_sha256': hashlib.sha256(stable(deterministic)).hexdigest(),
        'all_incremental_full_and_independent_dp_agree': True,
        'categories': categories,
        'overall': {
            'incremental_states': sum(r['incremental_states'] for r in records),
            'full_states': sum(r['full_states'] for r in records),
            'incremental_edges': sum(r['incremental_edges_scanned'] for r in records),
            'full_edges': sum(r['full_edges_scanned'] for r in records),
            'aggregate_incremental_seconds': round(sum(r['incremental_ns'] for r in records)/1e9, 5),
            'aggregate_full_seconds': round(sum(r['full_ns'] for r in records)/1e9, 5),
        },
        'no_algorithmic_novelty_claim': True,
        'no_real_language_or_music_claim': True,
        'general_incremental_search_baselines_not_yet_executed': ['LPA*', 'D* Lite', 'Ramalingam-Reps'],
        'do_not_claim_speed_superiority_from_microbenchmarks': True,
    }
    (directory / 'SUMMARY.json').write_bytes(stable(summary))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('reports/research/track_a2'))
    a = p.parse_args()
    print(json.dumps(run(a.output), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
