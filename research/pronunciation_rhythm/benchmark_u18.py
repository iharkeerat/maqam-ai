"""Frozen-seed exploratory formal graph-search comparison (NO linguistic ground truth)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import statistics
from dataclasses import asdict
from pathlib import Path

from .core import AlignmentCase, Candidate, RhythmSpec, exact_oracle, composed_dp, top_k, verify_solution
from .graph_search_u18 import shortest_path
from .pilot import generated_cases as earlier_cases

SEED = 20261024 + 18
PROTOCOL = "u18_formal_graph_search_exploratory_v1"


def cases() -> list[AlignmentCase]:
    """Old pilot + independent larger constructed stress family; exploratory only."""
    result = earlier_cases()
    rng = random.Random(SEED)
    for i in range(120):
        n = rng.randint(11, 18)
        events = tuple(rng.choice((1, 1, 2, 3)) for _ in range(n))
        total = sum(events)
        alphabet = "abcde"
        candidate_count = rng.randint(2, 7)
        candidates = []
        for j in range(candidate_count):
            k = rng.randint(max(1, n // 3), min(n + 3, 20))
            candidates.append(Candidate(
                key=f"stress_{i:03d}_cand_{j}",
                syllables=tuple(rng.choice(alphabet) for _ in range(k)),
                prior=j,
                ideal_ticks=tuple(rng.randint(1, 4) for _ in range(k)),
            ))
        prefix = []
        t = 0
        for duration in events[:-1]:
            t += duration
            prefix.append(t)
        bounds = tuple(sorted(rng.sample(prefix, rng.randint(0, min(3, len(prefix))))))
        locks = ((rng.randrange(n), rng.choice(alphabet)),) if rng.random() < .12 else ()
        result.append(AlignmentCase(
            f"u18_scale_{i:03d}", tuple(candidates), RhythmSpec(
                events, total, max_syllable_ticks=rng.randint(4, 8),
                max_events_per_syllable=rng.randint(2, 5),
                boundaries=bounds, locked_events=locks,
            )
        ))
    return result


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    collection = cases()
    data = canonical({"protocol": PROTOCOL, "seed": SEED, "cases": [asdict(c) for c in collection]})
    (output / "FORMAL_CASES.json").write_bytes(data)
    rows = []
    for case in collection:
        dp = composed_dp(case)
        graph = shortest_path(case)
        budget = shortest_path(case, max_pops=25)
        t1 = top_k(case, 1) if len(case.rhythm.events) <= 9 else None
        oracle = exact_oracle(case) if len(case.rhythm.events) <= 9 else None
        if graph.solution != dp.solution or graph.status != dp.status:
            raise AssertionError(f"Independent exact algorithms disagree: {case.key}")
        if oracle and (oracle.status != graph.status or oracle.solution != graph.solution):
            raise AssertionError(f"Small-case brute oracle disagreement: {case.key}")
        if graph.solution and not verify_solution(case, graph.solution):
            raise AssertionError(f"Invalid graph witness for {case.key}")
        if budget.status == "INFEASIBLE" and graph.status != "INFEASIBLE":
            raise AssertionError("Budgeted search falsely certified infeasibility")
        if budget.status == "FEASIBLE" and budget.solution != graph.solution:
            raise AssertionError("Budgeted uniform-cost output differs from exact best")
        rows.append({
            "case_id": case.key, "family": "earlier_formal" if oracle else "larger_constructed",
            "num_events": len(case.rhythm.events), "num_candidates": len(case.candidates),
            "exact_status": graph.status,
            "best_cost": graph.solution.cost if graph.solution else "",
            "best_candidate": graph.solution.candidate_key if graph.solution else "",
            "dp_status": dp.status, "graph_popped_states": graph.popped_states,
            "graph_eligible_edges": graph.eligible_edges, "graph_checked_edges": graph.checked_edges,
            "dp_transitions": dp.expansions,
            "budget25_status": budget.status, "budget25_popped_states": budget.popped_states,
            "top1_status": t1.status if t1 else "NOT_EXECUTED_ON_SCALE_SET",
            "oracle_status": oracle.status if oracle else "NOT_EXECUTED_ON_SCALE_SET",
        })
    with (output / "PER_CASE_RESULTS.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    outcomes = {}
    for family in ("earlier_formal", "larger_constructed"):
        sub = [r for r in rows if r["family"] == family]
        outcomes[family] = {
            "cases": len(sub),
            "exact_feasible": sum(r["exact_status"] == "FEASIBLE" for r in sub),
            "budget25_feasible": sum(r["budget25_status"] == "FEASIBLE" for r in sub),
            "budget25_infeasible_certified": sum(r["budget25_status"] == "INFEASIBLE" for r in sub),
            "budget25_incomplete": sum(r["budget25_status"] == "INCOMPLETE" for r in sub),
            "median_graph_popped_states": statistics.median(r["graph_popped_states"] for r in sub),
            "median_dp_transitions": statistics.median(r["dp_transitions"] for r in sub),
        }
    result = {
        "protocol": PROTOCOL, "seed": SEED, "dataset_sha256": hashlib.sha256(data).hexdigest(),
        "epistemic_status": "EXPLORATORY_CONSTRUCTED_FORMAL_ONLY",
        "linguistic_alternatives_attested": False, "sung_alignments_verified": False,
        "algorithmic_novelty_claimed": False,
        "total_cases": len(collection), "exact_dp_graph_agreement_count": len(collection),
        "small_brute_graph_agreement_count": sum(r["oracle_status"] != "NOT_EXECUTED_ON_SCALE_SET" for r in rows),
        "outcomes": outcomes,
        "interpretation": "A finite-state-style shortest-path reference reproduces exact DP optima. A capped search must return INCOMPLETE when unable to decide. Counts of transitions versus heap pops are NOT comparable time units.",
    }
    (output / "SUMMARY.json").write_bytes(canonical(result))
    (output / "PROTOCOL.json").write_bytes(canonical({
        "protocol": PROTOCOL, "pre_registered_before_data_inspection": False,
        "confirmatory": False, "case_origin": "constructed formal examples, no human or linguistic validation",
        "generalization_claim": "none", "primary_check": "agreement of exact independently implemented solvers",
        "baseline_methods": ["small exact brute oracle", "existing exact DP", "finite-state-style uniform-cost graph search", "25-pop budgeted graph search", "top1 exploratory small-only"],
        "warning": "Previous formal cases have been inspected. New scale cases derive from a generator designed by project authors. No formal results imply real music correctness or new algorithmic methods.",
    }))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("reports/research/graph_search_u18"))
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))


if __name__ == "__main__":
    main()
