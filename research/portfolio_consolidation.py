"""Upgrade 11: source-bound claim registry and reproducible portfolio evidence gate.

The gate deliberately verifies *computational claims* only. It never infers external
musical validity from a synthetic benchmark or from an application test suite.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

SOURCE_FILES = {
    "v1": "reports/research/experiment_summary.json",
    "v2": "reports/research/benchmark_v2/experiment_summary_v2.json",
    "v3": "reports/research/benchmark_v3/experiment_summary_v3.json",
    "v4": "reports/research/benchmark_v4/experiment_summary_v4.json",
    "v3_dataset": "evaluation/synthetic_lexical_stress_v3.csv",
    "v3_manifest": "evaluation/synthetic_lexical_stress_v3_manifest.json",
    "v4_predictions": "reports/research/benchmark_v4/frozen_prediction_comparisons_v4.csv",
}
FROZEN_INPUT_SHA256 = {
    'v1': '5c71481735039553147b3630f45e6bc727ce85c7c6b44075444ce975741c24ad',
    'v2': '7dcd887d9da7ae5d218bd04a2cf27240f51fd8e23bc33702f1d1e017f33e4f04',
    'v3': '836700208eb073c7db1edd4e6fd6bed80d1d1c98672a8cab72bc2b2f6c9acbc7',
    'v4': 'f641f0df36b2ae09d4e9372ba8a0e14949a59db2f20fa4c644e63797996236b2',
    'v3_dataset': 'f6c010623188097fdfee1cb33d6a3f4fcac62481755d1c382e56308129d44393',
    'v3_manifest': '8718e9fc9261f8f61050c7b2d043a3dcda0c2ab6d0edb778b658346628556630',
    'v4_predictions': '62b91c16f264fc3445bbbd6dde1359e96f0329224959b893d00a03abacd67c61',
}
CLAIM_BOUNDARY = (
    "Synthetic generator-label agreement and software behavior only; NOT musical "
    "correctness, authentic-poetry generalization, expert agreement, or translation invariance."
)

def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def close(a, b, tol=0.000001):
    return abs(float(a)-float(b)) <= tol

def audit(root: Path) -> dict:
    root = Path(root)
    errors, hashes, sources = [], {}, {}
    for key, rel in SOURCE_FILES.items():
        path=root/rel
        if not path.is_file():
            errors.append(f"Missing required source: {rel}")
            continue
        hashes[key] = {'path':rel,'sha256':checksum(path)}
        if key in ('v1','v2','v3','v4'):
            try: sources[key] = json.loads(path.read_text(encoding='utf-8'))
            except (ValueError,UnicodeError) as exc: errors.append(f"Unreadable JSON {rel}: {exc}")
    if len(sources)!=4 or len(hashes)!=len(SOURCE_FILES):
        return {'status':'BLOCKED','errors':errors,'source_evidence':hashes,'claim_boundary':CLAIM_BOUNDARY}
    a,b,c,d = (sources[k] for k in ('v1','v2','v3','v4'))
    dset=root/SOURCE_FILES['v3_dataset']; manifest=root/SOURCE_FILES['v3_manifest']
    for key, expected in FROZEN_INPUT_SHA256.items():
        if hashes[key]['sha256'] != expected:
            errors.append(f'Frozen {key} SHA-256 differs from archived v11.6.0 source')
    if d['dataset_sha256']!=hashes['v3_dataset']['sha256']:
        errors.append('v4 dataset SHA-256 differs from archived synthetic dataset')
    if d['manifest_sha256']!=hashes['v3_manifest']['sha256']:
        errors.append('v4 manifest SHA-256 differs from archived manifest')
    if c['frozen_dataset_sha256']!=hashes['v3_dataset']['sha256']:
        errors.append('v3 frozen dataset SHA-256 differs from archived synthetic dataset')
    if b['sample_counts']!={'train':448,'dev':112,'test':112}:
        errors.append('v2 split counts differ from baseline expected distribution')
    if d['split_counts']!={'train':48,'dev':48,'test':48}:
        errors.append('v4 split counts differ from frozen v3 dataset')
    arms=['text-only','full-metadata','no-time-token','balanced-time-augmentation','metadata-only']
    scores=d['test_scores']
    if set(scores)!=set(arms): errors.append('v4 model arms differ from experimental specification')
    if d.get('chosen_mitigation_by_dev')!='balanced-time-augmentation':
        errors.append('v4 documented dev-selected mitigation has changed')
    try:
        with (root/SOURCE_FILES['v4_predictions']).open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f))
        if len(rows)!=48: errors.append('v4 frozen predictions should contain exactly 48 cases')
        for arm in arms:
            if arm not in scores: continue
            base=f'base_{arm}'; time=f'time_swap_{arm}'
            if not all(base in r and time in r for r in rows):
                errors.append(f'Missing prediction fields for {arm}');continue
            truth=[r['rasa_generator_label'] for r in rows]
            accuracy=sum(r[base]==t for r,t in zip(rows,truth))/len(rows) if rows else 0
            flip=sum(r[base]!=r[time] for r in rows)/len(rows) if rows else 0
            if not close(accuracy,scores[arm]['top1_generator_label_agreement']):
                errors.append(f'Frozen prediction accuracy mismatch: {arm}')
            if not close(flip,scores[arm]['time_token_flip_rate']):
                errors.append(f'Frozen time flip mismatch: {arm}')
    except (OSError,ValueError,KeyError) as exc:
        errors.append(f'Could not audit frozen predictions: {exc}')
    for n in ('4','8'):
        for pair in ('train_vs_dev','train_vs_test','dev_vs_test'):
            if c['word_ngram_overlap'][n][pair]['common_unique_ngrams']!=0:
                errors.append(f'v3 {n}-word overlap nonzero on {pair}')
    group_v2=b.get('lexical_overlap',{}).get('overlap_vs_train',{}).get('8',{}).get('test',{})
    if group_v2.get('items_with_shared_train_ngram')!=112:
        errors.append('v2 lexical overlap finding has been changed or is unavailable')
    claims = [
       {'id':'V2-GROUP-SPLIT','claim':'v2 has 448/112/112 group-partitioned synthetic examples, with residual phrase reuse','source':'v2','decision':'supported_as_internal_diagnostic'},
       {'id':'V3-LEXICAL-STRESS','claim':'v3 has no cross-split 4- or 8-token overlap under the documented tokenizer','source':'v3','decision':'supported_as_internal_diagnostic'},
       {'id':'V4-TEXT','claim':f"Text-only v4 synthetic label agreement: {scores['text-only']['top1_generator_label_agreement']:.1%}",'source':'v4','decision':'supported_as_internal_diagnostic'},
       {'id':'V4-METADATA','claim':f"Metadata-only v4 synthetic label agreement: {scores['metadata-only']['top1_generator_label_agreement']:.1%}",'source':'v4','decision':'supported_as_internal_diagnostic'},
       {'id':'V4-TIME-FLIP','claim':'Full-metadata and metadata-only arms switch all 48 predictions under time-token swapping','source':'v4_predictions','decision':'supported_as_internal_diagnostic'},
       {'id':'V4-MITIGATION','claim':f"Dev-selected balanced-time mitigation has {scores['balanced-time-augmentation']['top1_generator_label_agreement']:.1%} synthetic test agreement and 0% time-token flip rate",'source':'v4','decision':'supported_as_internal_diagnostic'},
       {'id':'REAL-RAAG-ACCURACY','claim':'Musically appropriate Raag recommendation on genuine poetry','source':None,'decision':'unsupported_no_external_labels'},
       {'id':'HUMAN-EVALUATION','claim':'Independent musician agreement and subjective explainability','source':None,'decision':'unsupported_no_human_review'},
       {'id':'TRANSLATION-INVARIANCE','claim':'Translation-invariant multilingual semantic understanding','source':None,'decision':'unsupported_no_translation_pairs'},
       {'id':'FRESH-CONFIRMATION','claim':'Independent confirmatory test result','source':None,'decision':'unsupported_reused_holdout'},
    ]
    # Strict contract: zero unknown claims are silently promoted to empirical evidence.
    return {'status':'PASS_COMPUTATIONAL_ONLY' if not errors else 'BLOCKED',
            'errors':errors,'source_evidence':hashes,'claim_boundary':CLAIM_BOUNDARY,
            'claims':claims,
            'external_validation':{'musician_reviews':0,'independently_verified_poems':0,
             'real_musical_accuracy':'NOT_MEASURED','fresh_confirmatory_holdout':'NOT_AVAILABLE'},
            'frontend_build':'UNVERIFIED_DEPENDENCIES_NOT_CACHED'}

def report_markdown(result:dict) -> str:
    lines=['# MAQAM AI — Evidence and Claims Register (Option A)', '',
           f"**Computational audit:** {result['status']}", '',
           '**Boundary:** '+result['claim_boundary'],'',
           '| Claim | Admissible interpretation | Evidence |','|---|---|---|']
    for item in result.get('claims',[]):
        rel=result['source_evidence'].get(item['source'],{}).get('path','No independent source')
        lines.append(f"| {item['claim']} | {item['decision']} | `{rel}` |")
    lines+=['','## Evidence checksums','','Each checksum below is SHA-256 of an input evidence file, NOT a proof of independent validation.','']
    for key, v in result.get('source_evidence',{}).items():
        lines.append(f"- `{v['path']}`: `{v['sha256']}`")
    lines+=['','## Open blockers','',
       '- Real poetry corpus and independent musical assessments: unavailable under Option A.',
       '- v3 test reused in upgrades 09–10; no independent confirmatory holdout.',
       '- Next.js frontend production build not verified in offline environment.',
       '- Synthetic categories, scripts and metadata inherit the generator assumptions.',
       '', '## Audit errors', '', *(f'- {x}' for x in result['errors'])]
    if not result['errors']: lines.append('- None in the specified computational source-consistency checks.')
    return '\n'.join(lines)+'\n'
