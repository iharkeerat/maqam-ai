"""Run a separate v2 experiment without modifying v1 models, UI data, or reports.

Selection and calibration use *development* only, after verifying the frozen v2
partition. Test is used solely to report predeclared candidate comparisons.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np

from research.experiment import (align_probabilities, build_char_pipeline, build_word_pipeline,
    choose_temperature, model_text, ranked_from_probabilities, read_dataset, score_model,
    score_taal_model, temperature_scale)
from research.group_benchmark import sha256_file, verify_v2
from research.lexical_overlap import cross_split_lexical_audit
from research.rule_ranker import PrototypeRuleRanker

MODEL_ORDER = ('rules-prototype', 'word-tfidf-context', 'char-tfidf-text-only',
               'char-tfidf-context', 'char-tfidf-calibrated', 'hybrid-72-28')
CLAIM_BOUNDARY = ('Synthetic generator-assigned labels, NOT independent musical accuracy. '
                  'Old v1 and new v2 holdout scores are not directly comparable due to changed splits. '
                  'Vocabulary and phrases are still shared across group partitions.')


def _probs(model, rows: list[dict], include_context: bool, classes: list[str]) -> np.ndarray:
    pipeline = model.get('pipeline', model.get('ranker'))
    if pipeline is None:
        raise ValueError('Model wrapper has no estimator')
    model_classes = (list(pipeline.classes_) if 'ranker' in model else
                     list(pipeline.named_steps['classifier'].classes_))
    return align_probabilities(pipeline.predict_proba([model_text(row, include_context) for row in rows]),
                               model_classes, classes)


def _fit(rows: list[dict]) -> dict:
    labels = [row['primary_raag'] for row in rows]
    no_context = [model_text(row, False) for row in rows]
    with_context = [model_text(row, True) for row in rows]
    return {
        'rules-prototype': {'ranker': PrototypeRuleRanker().fit(no_context, labels), 'include_context': False},
        'word-tfidf-context': {'pipeline': build_word_pipeline().fit(with_context, labels), 'include_context': True},
        'char-tfidf-text-only': {'pipeline': build_char_pipeline().fit(no_context, labels), 'include_context': False},
        'char-tfidf-context': {'pipeline': build_char_pipeline().fit(with_context, labels), 'include_context': True},
    }


def _all_probabilities(models: dict, rows: list[dict], classes: list[str], temp: float) -> dict[str, np.ndarray]:
    p = {name: _probs(model, rows, model['include_context'], classes)
         for name, model in models.items()}
    p['char-tfidf-calibrated'] = temperature_scale(p['char-tfidf-context'], temp)
    p['hybrid-72-28'] = 0.72 * p['char-tfidf-context'] + 0.28 * p['rules-prototype']
    p['hybrid-72-28'] /= p['hybrid-72-28'].sum(axis=1, keepdims=True)
    return p


def _selection_tuple(row: dict) -> tuple:
    return (float(row['primaryTop3Recall']), float(row['macroF1PrimaryLabel']),
            -float(row['expectedCalibrationError']))


def run_v2(root: Path) -> dict:
    source = root / 'evaluation/seed_benchmark_v1.csv'
    dataset_path = root / 'evaluation/synthetic_benchmark_v2_group_disjoint.csv'
    manifest_path = root / 'evaluation/synthetic_benchmark_v2_manifest.json'
    manifest = verify_v2(dataset_path, manifest_path, source)
    dataset = read_dataset(dataset_path)
    train, dev, test = [dataset.split(name) for name in ('train', 'dev', 'test')]
    classes = sorted({row['primary_raag'] for row in train})
    if set(row['primary_raag'] for row in dev + test) != set(classes):
        raise ValueError('The group-split class set is inconsistent')

    development_models = _fit(train)
    # Dev probabilities/labels exclusively fit temperature and choose model.
    uncali_dev = _probs(development_models['char-tfidf-context'], dev, True, classes)
    temperature = choose_temperature(uncali_dev, [row['primary_raag'] for row in dev], classes)
    dev_prob = _all_probabilities(development_models, dev, classes, temperature)
    dev_scores = {name: score_model(name, dev_prob[name], classes, dev) for name in MODEL_ORDER}
    selected = sorted(MODEL_ORDER, key=lambda name: _selection_tuple(dev_scores[name]), reverse=True)[0]

    # Refit on train + dev; all hyperparameters/selection remain frozen.
    refit = _fit(train + dev)
    test_probs = _all_probabilities(refit, test, classes, temperature)
    test_scores = {name: score_model(name, test_probs[name], classes, test) for name in MODEL_ORDER}
    test_rankings = {name: ranked_from_probabilities(test_probs[name], classes) for name in MODEL_ORDER}

    # Separately predeclared Taal reference baseline, not a Raag-selection candidate.
    taal_train_y = [row['primary_taal'] for row in train + dev]
    taal_classes = sorted(set(taal_train_y))
    taal_model = build_char_pipeline().fit([model_text(row, True) for row in train + dev], taal_train_y)
    taal_probs = align_probabilities(taal_model.predict_proba([model_text(row, True) for row in test]),
                                    list(taal_model.named_steps['classifier'].classes_), taal_classes)
    taal_score = score_taal_model('taal-char-tfidf-context', taal_probs, taal_classes, test)

    result_dir = root / 'reports/research/benchmark_v2'
    artifact_dir = root / 'models/benchmark_v2'
    result_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for name, wrapper in refit.items():
        joblib.dump({'model': wrapper, 'classes': classes,
                     'status': 'synthetic-not-deployed', 'benchmark': 'v2'},
                    artifact_dir / f'{name}.joblib', compress=3)
    joblib.dump({'pipeline': taal_model, 'classes': taal_classes, 'status': 'synthetic-not-deployed'},
                artifact_dir / 'taal-char-tfidf-context.joblib', compress=3)

    model_hashes = {path.name: sha256_file(path) for path in sorted(artifact_dir.glob('*.joblib'))}
    summary = {
        'benchmark': manifest['benchmark'], 'scope': manifest['scope'], 'claim_boundary': CLAIM_BOUNDARY,
        'source_dataset_sha256': manifest['source_sha256'],
        'frozen_v2_dataset_sha256': manifest['dataset_sha256'],
        'manifest_sha256': sha256_file(manifest_path),
        'lexical_overlap': cross_split_lexical_audit(dataset.rows),
        'sample_counts': manifest['splits'], 'classes': len(classes),
        'train_groups': Counter(r['template_id'] for r in train).__len__(),
        'dev_groups': Counter(r['template_id'] for r in dev).__len__(),
        'test_groups': Counter(r['template_id'] for r in test).__len__(),
        'model_candidates_predeclared': list(MODEL_ORDER),
        'selection_policy': 'dev only: primary Top3 then macro F1 then lower expected calibration error',
        'selected_by_development': selected,
        'selected_test_score': {
            'primaryTop1Accuracy': test_scores[selected]['primaryTop1Accuracy'],
            'primaryTop3Recall': test_scores[selected]['primaryTop3Recall'],
            'macroF1PrimaryLabel': test_scores[selected]['macroF1PrimaryLabel']},
        'temperature_dev_only': round(temperature, 6),
        'development_results': {name: {'primaryTop1Accuracy': dev_scores[name]['primaryTop1Accuracy'],
                                       'primaryTop3Recall': dev_scores[name]['primaryTop3Recall'],
                                       'macroF1PrimaryLabel': dev_scores[name]['macroF1PrimaryLabel']}
                                for name in MODEL_ORDER},
        'test_results': {name: {'primaryTop1Accuracy': test_scores[name]['primaryTop1Accuracy'],
                                'primaryTop3Recall': test_scores[name]['primaryTop3Recall'],
                                'macroF1PrimaryLabel': test_scores[name]['macroF1PrimaryLabel'],
                                'top1Agreement': test_scores[name]['top1Agreement'],
                                'top3Agreement': test_scores[name]['top3Agreement'],
                                'perLanguage': test_scores[name]['perLanguage']}
                         for name in MODEL_ORDER},
        'taal_synthetic_results': {'primaryTop1Accuracy': taal_score['primaryTop1Accuracy'],
                                   'primaryTop3Recall': taal_score['primaryTop3Recall']},
        'model_artifact_sha256': model_hashes,
        'limitations': [
            'Only four held-out connected groups in total, one per language; no reliable population inference.',
            'Same generator, underlying phrase banks and rule inventory across all partitions.',
            'Generator-assigned primary labels conflict for some identical poems.',
            'Metadata and source-specific prose cues may facilitate superficial prediction.',
            'No genuine poetry or independent musician annotations have been evaluated.',
            'Previously inspected v1 benchmarks must not be described as prospective held-out results.',
        ]}
    (result_dir / 'experiment_summary_v2.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    with (result_dir / 'holdout_predictions_v2.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        fields = ['item_id', 'split', 'language', 'template_id', 'primary_raag', 'accepted_raags',
                  'selected_model', 'top1', 'top3', 'top1_confidence', 'is_synthetic']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for index, row in enumerate(test):
            writer.writerow({'item_id': row['item_id'], 'split': 'test', 'language': row['language'],
                             'template_id': row['template_id'], 'primary_raag': row['primary_raag'],
                             'accepted_raags': row['accepted_raags'], 'selected_model': selected,
                             'top1': test_rankings[selected][index][0],
                             'top3': ';'.join(test_rankings[selected][index][:3]),
                             'top1_confidence': f'{float(test_probs[selected][index].max()):.6f}',
                             'is_synthetic': 'true'})
    (result_dir / 'model_comparison_v2.csv').write_text('model,dev_top1,dev_top3,test_top1,test_top3,test_macro_f1\n' +
        '\n'.join(f"{name},{dev_scores[name]['primaryTop1Accuracy']},{dev_scores[name]['primaryTop3Recall']},"
                  f"{test_scores[name]['primaryTop1Accuracy']},{test_scores[name]['primaryTop3Recall']},"
                  f"{test_scores[name]['macroF1PrimaryLabel']}" for name in MODEL_ORDER) + '\n', encoding='utf-8')
    top_sorted = sorted(MODEL_ORDER, key=lambda name: test_scores[name]['primaryTop1Accuracy'], reverse=True)
    markdown = [
        '# MAQAM AI — Synthetic Benchmark v2 Experimental Results', '',
        '**Internal generator-label agreement only; no human or real-poetry validation.**', '',
        f"Frozen set: train {len(train)}, dev {len(dev)}, test {len(test)}; 28 Raags, 4 languages, 20 connected groups.",
        f"Dev-selected model: **{selected}**; temperature fitted on dev: {temperature:.4f}.", '',
        '| Candidate | Development primary Top-1 | Test primary Top-1 | Test primary Top-3 |',
        '|---|---:|---:|---:|',
    ]
    for name in MODEL_ORDER:
        markdown.append(f"| {name} | {dev_scores[name]['primaryTop1Accuracy']:.3f} | "
                        f"{test_scores[name]['primaryTop1Accuracy']:.3f} | {test_scores[name]['primaryTop3Recall']:.3f} |")
    markdown += ['', 'These metrics are **not** musical correctness, real-world generalization, or a prospective independent evaluation.',
                 'The new split removes exact normalized cross-split poem overlap and cross-split template-family overlap; ',
                 'it cannot remove shared generator vocabulary, label contradictions or other correlated templates.',
                 'Four test groups are too few for strong uncertainty estimates.',
                 'Old v1 and new v2 numbers are not comparable as a controlled experiment.',
                 'The lexical audit measures shared 4-word and 8-word training phrases in dev/test samples.',
                 'Review `experiment_summary_v2.json` before making any robustness claim.', '']
    (result_dir / 'RESULTS_README.md').write_text('\n'.join(markdown), encoding='utf-8')
    return summary
