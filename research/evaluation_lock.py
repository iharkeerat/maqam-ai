"""Development-only comparator lock and immutable input file fingerprints."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CHALLENGER = 'hybrid-char-plus-rules-v1'
BASELINE_IDS = ('rules-prototype-v1','word-tfidf-logreg-v1','char-tfidf-text-only-v1',
                'char-tfidf-context-v1','char-tfidf-calibrated-v1')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def best_development_baseline(comparisons: list[dict]) -> str:
    """Uses only development metrics; never accepts a test comparison payload."""
    options = {v['model']:v for v in comparisons if v.get('model') in BASELINE_IDS}
    if set(BASELINE_IDS)-set(options):
        raise ValueError('Missing development-only comparator baselines')
    if len(options)!=len(BASELINE_IDS):
        raise ValueError('Duplicate development baseline IDs')
    for r in options.values():
        if any(k not in r for k in ('primaryTop3Recall','macroF1PrimaryLabel','expectedCalibrationError')):
            raise ValueError('Missing preregistered development metric')
    return max(BASELINE_IDS, key=lambda name: (
        float(options[name]['primaryTop3Recall']),
        float(options[name]['macroF1PrimaryLabel']),
        -float(options[name]['expectedCalibrationError'])))


def make_protocol(config: Path, development_summary: Path, registry: Path, model_dir: Path | None = None) -> dict:
    if model_dir is None: model_dir = registry.parent
    required_artifacts = {
        'raag_context_baseline_v1.joblib',
        'raag_text_baseline_v1.joblib',
        'raag_rule_baseline_v1.joblib',
    }
    for file in required_artifacts:
        if not (model_dir / file).is_file():
            raise ValueError(f'Missing model artifact: {file}')
    cfg = json.loads(config.read_text(encoding='utf-8'))
    summary = json.loads(development_summary.read_text(encoding='utf-8'))
    reg = json.loads(registry.read_text(encoding='utf-8'))
    if summary.get('benchmark',{}).get('type') != 'internal-synthetic' or summary.get('benchmark',{}).get('expertValidated') is not False:
        raise ValueError('Expected v10 synthetic developmental experiment only')
    if summary.get('selectionSplit') != 'dev (train-only candidates)':
        raise ValueError('Selected candidate not from documented development split')
    if 'developmentComparisons' not in summary:
        raise ValueError('Development-only model comparisons required')
    comparator = best_development_baseline(summary['developmentComparisons'])
    if reg.get('selectedModel') != CHALLENGER or summary.get('selectedModel') != CHALLENGER:
        raise ValueError('Fixed hybrid challenger does not match training summary/registry')
    if cfg.get('modelSelection') != 'development only; test held out':
        raise ValueError('Source config does not document development-only selection')
    return {
        'protocol_version':'1.0', 'status':'FROZEN_METHODS_NOT_EXTERNAL_EVIDENCE',
        'research_question':'On independently reviewed source-held-out poems, does the fixed hybrid improve expert-set Hit@3 over the development-selected single baseline?',
        'hypotheses': {'null':'paired Hit@3 delta is zero', 'alternative':'paired Hit@3 delta is positive'},
        'challenger':CHALLENGER, 'baseline':comparator,
        'baseline_selected_from':'synthetic DEV metrics only; no external review or test labels',
        'selection_metric_order':['primaryTop3Recall','macroF1PrimaryLabel','negative_expectedCalibrationError'],
        'primary_metric':'expert-consensus Hit@3 paired delta; same study cases and blinded ratings',
        'secondary_metrics':['expert-set Hit@1','mean reciprocal rank','language strata','abstention rate','reviewer disagreement'],
        'uncertainty':'95% source-cluster bootstrap percentile CI (seed=20261023, 3000 replicates)',
        'study_inclusion':'Only Stage-A consensus cases with >=3 reviewers, no abstention, no unresolved adjudication; show attrition from all cases',
        'test_data_policy':'No external test labels used for tuning, selection or calibration; freeze ranked predictions before unblinding Stage A',
        'development_evidence_sha256':{'config':sha256(config),'summary':sha256(development_summary),'model_registry':sha256(registry)},
        'frozen_models_sha256':{name:sha256(model_dir/name) for name in sorted(required_artifacts)},
        'evaluation_status':'PENDING_INDEPENDENT_MUSICIAN_STUDY',
        'caution':'This lock preserves a fixed protocol, not proof that external data, reviewers, or permissions exist.'
    }


def check_fingerprints(files: dict[str,Path], hashes: dict[str,str]) -> None:
    for name,path in files.items():
        if name not in hashes or sha256(path)!=hashes[name]:
            raise ValueError(f'Locked input was changed: {name}')
