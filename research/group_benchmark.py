"""Construct an immutable, explicitly synthetic, group-disjoint benchmark v2.

This is a *resplitting* of the v1 examples, not independent new poetry.
Connected components link identical normalized poems and common template families.
Source label conflicts and shared lexical fragments remain limitations.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from scripts.audit_corpus import audit as corpus_audit, normalize

SEED = 'maqam-option-a-group-split-20261023'
SPLITS = ('train', 'dev', 'test')


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        required = {'item_id', 'split', 'language', 'poem', 'primary_raag',
                    'accepted_raags', 'template_family', 'is_synthetic', 'provenance'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('Source benchmark missing required fields')
        rows = list(reader)
    if len(rows) < 12 or any(not row['item_id'].strip() or not normalize(row['poem']) or
                                 not row['template_family'].strip() or not row['language'].strip() or
                                 not row['primary_raag'].strip() or
                                 row['is_synthetic'].strip().lower() != 'true' for row in rows):
        raise ValueError('Only complete, explicitly synthetic examples are supported')
    if len({row['item_id'] for row in rows}) != len(rows):
        raise ValueError('Duplicate item_id in source')
    return rows


def connected_groups(rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    parent = list(range(len(rows)))

    def root(n: int) -> int:
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    def merge(a: int, b: int) -> None:
        a, b = root(a), root(b)
        if a != b:
            parent[max(a, b)] = min(a, b)

    first: dict[tuple[str, str], int] = {}
    for index, row in enumerate(rows):
        for key in (('poem', normalize(row['poem'])),
                    ('template_family', row['template_family'].strip().casefold())):
            if key in first:
                merge(index, first[key])
            else:
                first[key] = index
    groups: dict[int, list[dict[str, str]]] = defaultdict(list)
    for index, row in enumerate(rows):
        groups[root(index)].append(row)
    return sorted([sorted(group, key=lambda row: row['item_id']) for group in groups.values()],
                  key=lambda group: group[0]['item_id'])


def group_key(group: list[dict[str, str]]) -> str:
    # Stable regardless of CSV source ordering; no legacy split information used.
    ids = '\n'.join(sorted(row['item_id'] for row in group))
    return 'grp-' + hashlib.sha256(ids.encode('utf-8')).hexdigest()[:16]


def build_v2(source: Path) -> tuple[list[dict[str, str]], dict]:
    rows = read_rows(source)
    groups = connected_groups(rows)
    by_language: dict[str, list[list[dict[str, str]]]] = defaultdict(list)
    for group in groups:
        langs = {row['language'] for row in group}
        if len(langs) != 1:
            raise ValueError('Text/template component joins languages; cannot stratify safely')
        by_language[next(iter(langs))].append(group)

    assigned: dict[str, str] = {}
    group_details: list[dict] = []
    for language in sorted(by_language):
        lang_groups = by_language[language]
        if len(lang_groups) < 3:
            raise ValueError(f'{language}: fewer than three independent groups')
        # Hold out the smallest components. Assign independently per language.
        # This limits the number of missing classes in this 28-label synthetic seed.
        by_size = sorted(lang_groups, key=lambda g: (len(g), hashlib.sha256(
            (SEED + group_key(g)).encode()).hexdigest()))
        for split, group in [('dev', by_size[0]), ('test', by_size[1])]:
            assigned[group_key(group)] = split
        for group in lang_groups:
            key = group_key(group)
            split = assigned.get(key, 'train')
            assigned[key] = split
            group_details.append({'group_id': key, 'language': language,
                                  'rows': len(group), 'split': split,
                                  'template_families': sorted({r['template_family'] for r in group})})

    split_rows = []
    for group in groups:
        key = group_key(group)
        for row in group:
            new = dict(row)
            new['original_split'] = row['split']
            new['split'] = assigned[key]
            new['template_id'] = key
            split_rows.append(new)
    split_rows.sort(key=lambda r: r['item_id'])

    result = corpus_audit(split_rows)
    if not result['passed']:
        raise ValueError(f'Group leakage/invalid rows detected: {result["problems"][:2]}')
    classes = {row['primary_raag'] for row in rows}
    for split in SPLITS:
        observed = {row['primary_raag'] for row in split_rows if row['split'] == split}
        if observed != classes:
            raise ValueError(f'{split} lacks labels: {sorted(classes - observed)}')
    for language in by_language:
        if any(not any(row['language'] == language and row['split'] == split
                       for row in split_rows) for split in SPLITS):
            raise ValueError(f'Language {language} missing from a partition')

    text_to_labels: dict[str, set[str]] = defaultdict(set)
    for row in split_rows:
        text_to_labels[normalize(row['poem'])].add(row['primary_raag'])
    report = {
        'benchmark': 'MAQAM Synthetic Seed v2: Connected-Group Split',
        'scope': 'INTERNAL_SYNTHETIC_REPARTITION_ONLY_NO_HUMAN_VALIDATION',
        'source': str(source.name), 'source_sha256': sha256_file(source),
        'seed': SEED, 'split_rule': 'normalized-text and template-family connected components, stratified by language',
        'splits': dict(Counter(row['split'] for row in split_rows)),
        'languages': {language: dict(Counter(row['split'] for row in split_rows if row['language'] == language))
                      for language in sorted(by_language)},
        'classes': len(classes), 'connected_groups': len(groups),
        'per_group': sorted(group_details, key=lambda detail: detail['group_id']),
        'leakage_audit': result,
        'unique_normalized_poems': len(text_to_labels),
        'multi_label_normalized_poems': sum(len(values) > 1 for values in text_to_labels.values()),
        'note': ('No exact normalized text or original template-family crosses splits. '
                 'Individual source phrases, generator logic and some label ambiguity can still cross splits. '
                 'This does not create independent poetry or musically correct labels.'),
    }
    return split_rows, report


def write_v2(rows: list[dict[str, str]], report: dict, dataset_path: Path, manifest_path: Path) -> None:
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with dataset_path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    report = dict(report)
    report['dataset_sha256'] = sha256_file(dataset_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def verify_v2(dataset_path: Path, manifest_path: Path, source_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('dataset_sha256') != sha256_file(dataset_path):
        raise ValueError('Frozen v2 dataset hash mismatch')
    if manifest.get('source_sha256') != sha256_file(source_path):
        raise ValueError('Original source dataset changed')
    expected_rows, expected = build_v2(source_path)
    if expected['per_group'] != manifest.get('per_group') or expected['splits'] != manifest.get('splits'):
        raise ValueError('Frozen group partition differs from deterministic recomputation')
    with dataset_path.open(encoding='utf-8-sig', newline='') as stream:
        actual = list(csv.DictReader(stream))
    if actual != expected_rows:
        raise ValueError('Frozen v2 content does not match deterministic source derivation')
    if not corpus_audit(actual)['passed']:
        raise ValueError('Frozen dataset fails independent leakage audit')
    return manifest
