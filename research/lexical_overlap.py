"""Descriptive n-gram reuse audit; complements, never replaces, exact/group leakage controls."""
from __future__ import annotations
from collections import Counter
from scripts.audit_corpus import normalize


def shingles(text: str, n: int) -> set[tuple[str, ...]]:
    if n < 1:
        raise ValueError('Shingle length must be positive')
    tokens = normalize(text).split()
    return {tuple(tokens[index:index+n]) for index in range(len(tokens)-n+1)}


def cross_split_lexical_audit(rows: list[dict], n_values: tuple[int, ...] = (4, 8)) -> dict:
    if not rows or any(r.get('split') not in {'train','dev','test'} for r in rows):
        raise ValueError('Need complete rows and recognized split assignments')
    report = {}
    for n in n_values:
        train_shingles = set().union(*(shingles(r['poem'], n) for r in rows if r['split'] == 'train'))
        counters = {}
        for split in ('dev', 'test'):
            held = [r for r in rows if r['split'] == split]
            overlap = [r for r in held if shingles(r['poem'], n) & train_shingles]
            counters[split] = {'items': len(held), 'items_with_shared_train_ngram': len(overlap),
                               'fraction': round(len(overlap)/len(held), 6) if held else None}
        report[str(n)] = counters
    return {'metric': 'normalized word n-gram reuse; not necessarily identical poem',
            'overlap_vs_train': report}
