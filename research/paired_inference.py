"""Locked paired evaluation with per-item expert sets and cluster bootstrap CIs.

Pure functions: no model is selected from evaluation labels. Zero external
claims are made until an independent study has been completed and attested.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import random

from scripts.raag_vocabulary import canonical_raag


def parse_ranked(value: str) -> list[str]:
    raw = [x.strip() for x in value.split(';') if x.strip()]
    values = [canonical_raag(label) for label in raw]
    if not values or None in values or len(values) != len(set(values)):
        raise ValueError('Ranked predictions must be nonempty, within approved 28-Raag inventory, and nonrepeating')
    return values


def accepted_set(value: str) -> set[str]:
    raw = [x.strip() for x in value.split(';') if x.strip()]
    values = [canonical_raag(label) for label in raw]
    if not values or None in values:
        raise ValueError('Expert accepted sets must use approved 28-Raag inventory labels')
    return set(values)


def evaluate_rows(rows: list[dict], *, resamples: int = 3000, seed: int = 20261023) -> dict:
    """Rows: study_case_id, language, cluster_id, accepted, challenger, baseline.

    Paired cluster bootstrap resamples **source/author groups**, not arbitrary
    observations; percentile interval descriptive and potentially very wide.
    """
    if len(rows) < 1:
        raise ValueError('No eligible evaluated rows: cannot make a comparison')
    if not (100 <= resamples <= 100_000):
        raise ValueError('resamples must be 100–100000')
    ids = [r['study_case_id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate case IDs')

    scored = []
    for r in rows:
        accepted = accepted_set(r['accepted'])
        if not accepted:
            raise ValueError('Empty expert consensus not scoreable')
        challenger = parse_ranked(r['challenger'])
        baseline = parse_ranked(r['baseline'])
        def score(ranked, k):
            return int(bool(accepted.intersection(ranked[:k])))
        def mrr(ranked):
            return next((1 / i for i, label in enumerate(ranked, 1) if label in accepted), 0.0)
        scored.append({
            'study_case_id': r['study_case_id'], 'language': r['language'].strip(),
            'cluster_id': r['cluster_id'].strip(),
            'challenger_hit1': score(challenger,1), 'baseline_hit1': score(baseline,1),
            'challenger_hit3': score(challenger,3), 'baseline_hit3': score(baseline,3),
            'challenger_mrr': mrr(challenger), 'baseline_mrr': mrr(baseline),
        })
    if any(not r['cluster_id'] for r in scored):
        raise ValueError('Missing source/author cluster identifier')

    def average(items, key):
        return sum(r[key] for r in items) / len(items)
    def summary(items):
        return {
            'n': len(items),
            'challenger_hit1': round(average(items,'challenger_hit1'),6),
            'baseline_hit1': round(average(items,'baseline_hit1'),6),
            'challenger_hit3': round(average(items,'challenger_hit3'),6),
            'baseline_hit3': round(average(items,'baseline_hit3'),6),
            'challenger_mrr': round(average(items,'challenger_mrr'),6),
            'baseline_mrr': round(average(items,'baseline_mrr'),6),
            'paired_delta_hit3': round(average(items,'challenger_hit3')-average(items,'baseline_hit3'),6),
        }
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in scored:
        groups[r['cluster_id']].append(r)
    names = sorted(groups)
    rng = random.Random(seed)
    samples = []
    for _ in range(resamples):
        chosen = [groups[rng.choice(names)] for _ in names]
        sample = [row for group in chosen for row in group]
        samples.append(average(sample,'challenger_hit3')-average(sample,'baseline_hit3'))
    samples.sort()
    # Method: cluster percentile bootstrap; resampling clusters with replacement.
    low_idx = max(0, int(0.025*(resamples-1)))
    high_idx = min(resamples-1, int(0.975*(resamples-1)))
    by_language = {}
    for language in sorted({r['language'] for r in scored}):
        by_language[language] = summary([r for r in scored if r['language']==language])
    return {
        'status': 'PAIRED_EVALUATION',
        'n_items': len(scored), 'n_independent_clusters':len(names),
        'primary_metric': 'expert-consensus Hit@3 paired delta (challenger minus baseline)',
        'overall': summary(scored), 'by_language_descriptive':by_language,
        'paired_bootstrap': {'method':'source-cluster percentile bootstrap',
                             'unit':'cluster_id', 'seed':seed,'resamples':resamples,
                             'ci_95': [round(samples[low_idx],6),round(samples[high_idx],6)] if len(names)>=2 else None,
                             'interpretation':'Descriptive uncertainty; not proof of significance, especially with few clusters. CI unavailable for one cluster'},
        'discordant_hit3': {
            'challenger_only':sum(r['challenger_hit3']==1 and r['baseline_hit3']==0 for r in scored),
            'baseline_only':sum(r['challenger_hit3']==0 and r['baseline_hit3']==1 for r in scored),
            'both':sum(r['challenger_hit3']==1 and r['baseline_hit3']==1 for r in scored),
            'neither':sum(r['challenger_hit3']==0 and r['baseline_hit3']==0 for r in scored),
        },
        'caveats':['Consensus is not universal ground truth',
                   'No causal attribution without controlled comparisons',
                   'Per-language analyses are descriptive if sample sizes are small'],
    }
