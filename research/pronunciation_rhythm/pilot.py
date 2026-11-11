"""Reproducible, purely constructed formal pilot -- NEVER human evidence.

Commands (from repository root):
  python -m research.pronunciation_rhythm.pilot --output reports/research/pronunciation_rhythm_pilot
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import platform
import random
from dataclasses import asdict
from pathlib import Path
from .core import (AlignmentCase, Candidate, RhythmSpec, composed_dp, exact_oracle,
                   exhaustive_two_stage, top_k, verify_solution)

SEED = 20261024
PROTOCOL = "formal_pilot_v1_exploratory"


def generated_cases() -> list[AlignmentCase]:
    rng = random.Random(SEED)
    cases = []
    # Explicit toy adversaries. All symbols are invented and carry no phonological claim.
    manual = [
        ("top1_wrong_length", ("a", "b", "c"), ("a", "b"), (1, 1), 2, (), ()),
        ("top1_wrong_length_2", ("a",), ("a", "b", "c"), (1, 1, 1), 3, (), ()),
        ("top1_conflict_lock", ("a", "b"), ("a", "c"), (1, 1), 2, (), ((1, "c"),)),
        ("boundary_blocks_melisma", ("a", "b"), ("a", "b", "c", "d"), (1, 1, 1, 1), 4, (2,), ()),
        ("all_infeasible", ("x",), ("y",), (1, 1, 1, 1), 4, (2,), ((0, "z"),)),
        ("both_feasible", ("a", "b"), ("a", "b"), (1, 1), 2, (), ()),
    ]
    for idx, (name, a, b, events, cycle, bounds, locks) in enumerate(manual):
        cases.append(AlignmentCase(name, (
            Candidate(f"p{idx}_1", a, prior=0), Candidate(f"p{idx}_2", b, prior=1),
        ), RhythmSpec(events, cycle, max_events_per_syllable=2,
                      boundaries=bounds, locked_events=locks)))
    # Randomly generated formal task cases: not pronunciation samples.
    for i in range(144):
        n = rng.randint(3, 9)
        events = tuple(rng.choice((1, 1, 1, 2)) for _ in range(n))
        total = sum(events)
        max_span = rng.randint(1, 3)
        n_candidates = rng.randint(2, 5)
        cand = []
        alphabet = "abcde"
        for j in range(n_candidates):
            k = rng.randint(1, min(n + 2, 10))
            syllables = tuple(rng.choice(alphabet) for _ in range(k))
            prior = j  # Candidate 0 is top-1; no artificial claim of realistic prior
            target = tuple(rng.randint(1, max(2, total // max(k, 1) + 2)) for _ in range(k))
            cand.append(Candidate(f"r{i:03d}_p{j}", syllables, prior, target))
        possible_bounds = []
        t = 0
        for d in events[:-1]:
            t += d
            possible_bounds.append(t)
        bounds = tuple(sorted(rng.sample(possible_bounds, min(len(possible_bounds), rng.randint(0, 2)))))
        locks = ()
        if rng.random() < 0.20:
            locks = ((rng.randrange(n), rng.choice(alphabet)),)
        spec = RhythmSpec(events, total, min_syllable_ticks=1,
                          max_syllable_ticks=rng.randint(2, 6),
                          max_events_per_syllable=max_span,
                          boundaries=bounds, locked_events=locks)
        cases.append(AlignmentCase(f"constructed_{i:03d}", tuple(cand), spec))
    return cases


def _canonical(obj: object) -> bytes:
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       indent=2, separators=(",", ": ")) + "\n").encode("utf-8")


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    cases = generated_cases()
    records = [asdict(c) for c in cases]
    data = _canonical({"protocol": PROTOCOL, "seed": SEED, "cases": records})
    (output / "FORMAL_CASES.json").write_bytes(data)
    cases_sha = hashlib.sha256(data).hexdigest()
    per_case = []
    for case in cases:
        oracle = exact_oracle(case)
        two_stage = exhaustive_two_stage(case)
        dp = composed_dp(case)
        t1, t2 = top_k(case, 1), top_k(case, 2)
        assert oracle.status == two_stage.status == dp.status
        assert oracle.solution == two_stage.solution == dp.solution
        for res in (oracle, two_stage, dp, t1, t2):
            assert res.solution is None or verify_solution(case, res.solution)
        if oracle.status == "INFEASIBLE":
            assert t1.status == t2.status == "INFEASIBLE"
        per_case.append({
            "case_id": case.key,
            "oracle_status": oracle.status,
            "oracle_cost": oracle.solution.cost if oracle.solution else "",
            "oracle_candidate": oracle.solution.candidate_key if oracle.solution else "",
            "top1_status": t1.status, "top2_status": t2.status,
            "two_stage_status": two_stage.status, "dp_status": dp.status,
            "oracle_expansions": oracle.expansions,
            "two_stage_expansions": two_stage.expansions,
            "dp_transitions": dp.expansions,
        })
    with (output / "PER_CASE_RESULTS.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per_case[0]))
        writer.writeheader()
        writer.writerows(per_case)
    feasible = [r for r in per_case if r["oracle_status"] == "FEASIBLE"]
    n_false1 = sum(r["top1_status"] == "INFEASIBLE" for r in feasible)
    n_false2 = sum(r["top2_status"] == "INFEASIBLE" for r in feasible)
    payload = {
        "protocol": PROTOCOL,
        "epistemic_status": "exploratory constructed formal cases; no real pronunciations or music validation",
        "novelty_status": "not established; DP, exhaustive search and top-k are established methods",
        "seed": SEED,
        "runtime_python": platform.python_version(),
        "dataset_sha256": cases_sha,
        "total_cases": len(cases),
        "feasible_cases": len(feasible),
        "infeasible_cases": len(per_case) - len(feasible),
        "top1_false_infeasible_count": n_false1,
        "top2_false_infeasible_count": n_false2,
        "top1_false_infeasibility_rate": n_false1 / len(feasible) if feasible else None,
        "top2_false_infeasibility_rate": n_false2 / len(feasible) if feasible else None,
        "oracle_and_exact_two_stage_identical": True,
        "oracle_and_composed_dp_identical": True,
        "oracle_total_candidate_assignments_checked": sum(int(r["oracle_expansions"]) for r in per_case),
        "composed_dp_total_transitions": sum(int(r["dp_transitions"]) for r in per_case),
        "warning": "DP transitions are not comparable machine-level operations to brute-force candidate assignments. No efficiency superiority inferred.",
    }
    (output / "PILOT_SUMMARY.json").write_bytes(_canonical(payload))
    (output / "EXPERIMENT_PROTOCOL.json").write_bytes(_canonical({
        "experiment": PROTOCOL,
        "frozen_before_independent_future_test": False,
        "confirmatory": False,
        "formal_tick_model_only": True,
        "candidate_origin": "synthetic, not phonological attestations",
        "primary_outcome": "top1 false infeasibility among oracle-feasible cases",
        "comparators": ["top1 exact", "top2 exact", "exhaustive two-stage", "composed dynamic program", "independent enumerative reference"],
        "claim_boundary": "formal completeness and witness verification only; no artistic, linguistic, or novel-algorithm claims",
    }))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("reports/research/pronunciation_rhythm_pilot"))
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))
