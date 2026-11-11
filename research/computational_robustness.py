"""Frozen-model *synthetic* perturbation diagnostics; no external or human labels.

Measures the stability of predictions under simple input transformations.
Robustness is not musical correctness; original benchmark labels are generator-assigned.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np

from research.experiment import align_probabilities, model_text, ranked_from_probabilities, temperature_scale

RESEARCH_STATUS = 'SYNTHETIC_ONLY_NOT_HUMAN_VALIDATED'
REQUIRED_ARTIFACTS = {
    'raag_context_baseline_v1.joblib', 'raag_text_baseline_v1.joblib',
    'raag_rule_baseline_v1.joblib',
}
CONDITIONS = ('original', 'whitespace', 'punctuation', 'missing_metadata')
MODEL_NAMES = ('char-context', 'char-text-only', 'rule-prototype', 'hybrid')


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def perturb_poem(poem: str, condition: str) -> str:
    if condition in ('original', 'missing_metadata'):
        return poem
    if condition == 'whitespace':
        return '  \n '.join(poem.split())  # tokens preserved; altered spacing
    if condition == 'punctuation':
        # Removing Unicode punctuation is a diagnostic; it is NOT assumed
        # to preserve meter, semantics, readability, or musical interpretation.
        return ''.join(' ' if unicodedata.category(c).startswith('P') else c for c in poem)
    raise ValueError(f'Unknown perturbation {condition}')


def model_rows(rows: list[dict[str, str]], condition: str) -> list[dict[str, str]]:
    if condition not in CONDITIONS:
        raise ValueError('Unknown evaluation condition')
    return [dict(poem=perturb_poem(row['poem'], condition),
                 form='' if condition == 'missing_metadata' else row['form'],
                 time_hint='' if condition == 'missing_metadata' else row['time_hint'],
                 language=row['language']) for row in rows]


def read_synthetic_test(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError('Dataset is empty')
    required = {'item_id', 'split', 'language', 'poem', 'form', 'time_hint',
                'primary_raag', 'accepted_raags', 'is_synthetic'}
    if any(not required.issubset(row) for row in rows):
        raise ValueError('Missing expected benchmark columns')
    if any(str(row.get('is_synthetic', '')).strip().casefold() != 'true' for row in rows):
        raise ValueError('Only explicit synthetic seed data is eligible for this audit')
    eligible = [row for row in rows if row['split'] == 'test']
    if not eligible:
        raise ValueError('No synthetic test rows')
    ids = [row['item_id'] for row in eligible]
    if len(ids) != len(set(ids)) or any(not x for x in ids):
        raise ValueError('Duplicate or missing test IDs')
    if any(not row['poem'].strip() or not row['primary_raag'].strip() for row in eligible):
        raise ValueError('Blank synthetic test item or generator label')
    return sorted(eligible, key=lambda row: row['item_id'])


def load_frozen_models(root: Path, protocol: Path) -> tuple[dict, dict, dict, list[str]]:
    cfg = json.loads(protocol.read_text(encoding='utf-8'))
    if cfg.get('status') != 'FROZEN_METHODS_NOT_EXTERNAL_EVIDENCE':
        raise ValueError('Unsupported protocol status')
    hashes = cfg.get('frozen_models_sha256')
    if not isinstance(hashes, dict) or set(hashes) != REQUIRED_ARTIFACTS:
        raise ValueError('Frozen model set incomplete')
    for name in REQUIRED_ARTIFACTS:
        path = root / 'models' / name
        if not path.is_file() or digest_file(path) != hashes[name]:
            raise ValueError(f'Frozen model mismatch: {name}')
    # joblib deserialization must only be done for known, trusted local artifacts.
    context = joblib.load(root / 'models/raag_context_baseline_v1.joblib')
    text = joblib.load(root / 'models/raag_text_baseline_v1.joblib')
    rule = joblib.load(root / 'models/raag_rule_baseline_v1.joblib')
    classes = list(context['classes'])
    if len(classes) != len(set(classes)) or not classes:
        raise ValueError('Invalid class registry')
    return context, text, rule, classes


def predict_all(rows: list[dict[str, str]], condition: str,
                context: dict, text: dict, rule: dict, classes: list[str]) -> dict[str, np.ndarray]:
    records = model_rows(rows, condition)
    cp_raw = context['pipeline'].predict_proba([model_text(row, True) for row in records])
    cp = align_probabilities(cp_raw, list(context['pipeline'].named_steps['classifier'].classes_), classes)
    tp_raw = text['pipeline'].predict_proba([model_text(row, False) for row in records])
    tp = align_probabilities(tp_raw, list(text['pipeline'].named_steps['classifier'].classes_), classes)
    rp_raw = rule['ranker'].predict_proba([model_text(row, False) for row in records])
    rp = align_probabilities(rp_raw, list(rule['ranker'].classes_), classes)
    hybrid = .72 * cp + .28 * rp
    hybrid /= np.maximum(hybrid.sum(axis=1, keepdims=True), 1e-12)
    return {'char-context': temperature_scale(cp, float(context['temperature'])),
            'char-text-only': tp, 'rule-prototype': rp, 'hybrid': hybrid}


def _mean(x: list[float]) -> float:
    return round(float(np.mean(x)), 6) if x else 0.0


def analyze_condition(rows: list[dict[str, str]], original: np.ndarray, current: np.ndarray,
                      classes: list[str]) -> dict:
    before = ranked_from_probabilities(original, classes)
    after = ranked_from_probabilities(current, classes)
    flip = [float(a[0] != b[0]) for a, b in zip(before, after)]
    top3 = [len(set(a[:3]) & set(b[:3])) / 3 for a, b in zip(before, after)]
    primary = [float(b[0] == row['primary_raag']) for b, row in zip(after, rows)]
    # This overlap is scored against *synthetically assigned* acceptable sets,
    # not an independent musician-rated ground truth.
    accepted = [set(filter(None, row['accepted_raags'].split(';'))) for row in rows]
    accepted_hit3 = [float(bool(set(b[:3]) & truth)) for b, truth in zip(after, accepted)]
    by_language: dict[str, dict] = {}
    for language in sorted(set(row['language'] for row in rows)):
        selected = [i for i, row in enumerate(rows) if row['language'] == language]
        by_language[language] = {
            'items': len(selected),
            'top1_flip_rate': _mean([flip[i] for i in selected]),
            'top3_overlap': _mean([top3[i] for i in selected]),
            'generator_primary_top1': _mean([primary[i] for i in selected]),
        }
    return {'items': len(rows), 'top1_flip_rate': _mean(flip),
            'top3_overlap': _mean(top3), 'generator_primary_top1': _mean(primary),
            'generator_accepted_top3': _mean(accepted_hit3),
            'by_language': by_language}


def run(root: Path, *, dataset: Path | None = None, protocol: Path | None = None) -> dict:
    dataset = dataset or root / 'evaluation/seed_benchmark_v1.csv'
    protocol = protocol or root / 'research/locks/development_methods_v1.json'
    rows = read_synthetic_test(dataset)
    context, text, rule, classes = load_frozen_models(root, protocol)
    if any(row['primary_raag'] not in classes for row in rows):
        raise ValueError('Generator primary label outside locked model inventory')
    baseline = predict_all(rows, 'original', context, text, rule, classes)
    results = {}
    for condition in CONDITIONS:
        candidate = baseline if condition == 'original' else predict_all(rows, condition, context, text, rule, classes)
        results[condition] = {name: analyze_condition(rows, baseline[name], candidate[name], classes)
                              for name in MODEL_NAMES}
    return {
        'status': RESEARCH_STATUS, 'claim': 'Prediction stability on template-generated test verses only',
        'research_limitations': [
            'Synthetic benchmark primary and accepted labels were generated from the system inventory; not independently adjudicated.',
            'No claim of musical suitability, cultural correctness, model generalization to authentic poetry, or statistical significance.',
            'Exact train/development text overlap exists in this seed dataset; the test set is also synthetic.',
            'Whitespace and punctuation edits can affect model tokenization; removal of punctuation may also change meaning.',
            'Missing metadata is a deployment input shift, not necessarily a label-preserving transformation.',
            'Reusing the synthetic test split for subsequent development could contaminate future estimates.',
        ],
        'data_sha256': digest_file(dataset), 'protocol_sha256': digest_file(protocol),
        'frozen_model_sha256': {key: digest_file(root / 'models' / key) for key in sorted(REQUIRED_ARTIFACTS)},
        'test_examples': len(rows), 'language_distribution': {
            lang: sum(row['language'] == lang for row in rows)
            for lang in sorted({row['language'] for row in rows})},
        'conditions': list(CONDITIONS), 'models': list(MODEL_NAMES), 'results': results,
        'independent_musician_reviewers': 0, 'authentic_poems_evaluated': 0,
    }


def to_markdown(report: dict) -> str:
    lines = ['# MAQAM AI: Option A computational evaluation (synthetic only)', '',
             f"**Status:** `{report['status']}`. {report['test_examples']} synthetic test verses; "
             '**zero authentic poems and zero independent musician assessments.**', '',
             'This is an executable diagnostic of **prediction stability**, not musical correctness.', '',
             '| Input condition | Model | Top-1 changes | Top-3 overlap | Generator-label Top-1 | Generator-set Top-3 |',
             '|---|---|---:|---:|---:|---:|']
    for condition in CONDITIONS:
        for model in MODEL_NAMES:
            item = report['results'][condition][model]
            lines.append(f"| {condition} | {model} | {item['top1_flip_rate']:.3f} | "
                         f"{item['top3_overlap']:.3f} | {item['generator_primary_top1']:.3f} | "
                         f"{item['generator_accepted_top3']:.3f} |")
    lines.extend(['', '## What the numbers do and do not mean', '',
                  'A flip rate of 0 indicates unchanged leading recommendations under an edit; it does not prove accuracy. '
                  'The generator-label scores reflect consistency with the internal template process and are not external validation.', '',
                  '### Unresolved limitations', ''])
    lines.extend('- ' + x for x in report['research_limitations'])
    lines += ['', '## Reproducibility', '',
              f"- Dataset SHA-256: `{report['data_sha256']}`",
              f"- Protocol SHA-256: `{report['protocol_sha256']}`",
              '- Run from the project root: `python scripts/run_computational_option_a.py`',
              '- This command reads **frozen** model artifacts; it does not train or select using test labels.',
              '- Compare output hashes across runs to check deterministic results.', '']
    return '\n'.join(lines)
