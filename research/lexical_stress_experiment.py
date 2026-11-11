"""Option A v3 computational diagnostic; selection uses DEV only.

Neither synthetic labels nor any uncertainty interval proves Raag suitability.
Do not compare v2 to v3 as if same evaluation distribution.
"""
from __future__ import annotations
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.metrics import f1_score

from research.lexical_stress_v3 import verify_v3
from research.group_benchmark import sha256_file

SEED=20261023
NORMAL=('char-text-only','char-text-plus-metadata','metadata-only')
CONTROLS=('permuted-training-labels','majority-label')


def text_for(row,arm):
    if arm=='char-text-only':return row['poem']
    if arm in ('char-text-plus-metadata','permuted-training-labels'):
        return row['poem']+' [FORM='+row['form']+'] [TIME='+row['time_hint']+'] [LANG='+row['language']+']'
    if arm=='metadata-only':
        return '[FORM='+row['form']+'] [TIME='+row['time_hint']+'] [LANG='+row['language']+']'
    raise ValueError('Unknown arm')


def build_arm(arm):
    if arm not in NORMAL+CONTROLS:raise ValueError('Unrecognized experimental arm')
    return make_pipeline(TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=2,
                                     max_features=16000,sublinear_tf=True),
              LogisticRegression(max_iter=1500,C=2.0,class_weight='balanced',random_state=SEED))


def evaluate(gold:list[str],pred:list[str],classes:list[str],groups:list[str],replicates=1000,seed=SEED)->dict:
    if len(gold)!=len(pred) or len(gold)!=len(groups) or not gold:raise ValueError('Invalid paired predictions')
    right=np.array([a==b for a,b in zip(gold,pred)],dtype=float)
    unique=sorted(set(groups))
    if len(unique)<3:raise ValueError('Need at least three held-out source groups')
    per={g:np.flatnonzero(np.array(groups)==g) for g in unique}
    rng=np.random.default_rng(seed)
    samples=[]
    for _ in range(replicates):
        selected=rng.integers(0,len(unique),len(unique))
        idx=np.concatenate([per[unique[int(k)]] for k in selected])
        samples.append(float(np.mean(right[idx])))
    return {'top1_generator_label_agreement':round(float(np.mean(right)),6),
      'macro_f1_on_4_synthetic_rasa_labels':round(float(f1_score(gold,pred,labels=classes,average='macro',zero_division=0)),6),
      'cluster_bootstrap_95pct': [round(float(x),6) for x in np.quantile(samples,[0.025,0.975])],
      'bootstrap_replicates':replicates,'independent_group_count':len(unique),
      'interval_interpretation':'descriptive synthetic source-group bootstrap; not a population/human music accuracy CI'}


def fit_predict(arm,train,eval_rows,seed=SEED,permutation=False):
    y=[r['rasa_bucket'] for r in train]
    if permutation:
        y=list(np.random.default_rng(seed).permutation(y))
    if arm=='majority-label':
        majority=sorted(Counter(y).items(),key=lambda x:(-x[1],x[0]))[0][0]
        return [majority]*len(eval_rows)
    model=build_arm(arm)
    model.fit([text_for(r,arm) for r in train],y)
    return list(model.predict([text_for(r,arm) for r in eval_rows]))


def run_v3(root:Path)->dict:
    m=verify_v3(root)
    dataset=root/'evaluation/synthetic_lexical_stress_v3.csv'
    with dataset.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    train=[r for r in rows if r['split']=='train']
    dev=[r for r in rows if r['split']=='dev']
    test=[r for r in rows if r['split']=='test']
    classes=sorted({r['rasa_bucket'] for r in rows})
    dev_gold=[r['rasa_bucket'] for r in dev]
    dev_results={}
    for arm in NORMAL:
        pred=fit_predict(arm,train,dev)
        dev_results[arm]={'top1':round(float(np.mean(np.array(pred)==np.array(dev_gold))),6),
           'macro_f1':round(float(f1_score(dev_gold,pred,labels=classes,average='macro',zero_division=0)),6)}
    # Selection is locked *before* any test predictions are generated.
    selected=sorted(NORMAL,key=lambda a:(dev_results[a]['top1'],dev_results[a]['macro_f1'],-NORMAL.index(a)),reverse=True)[0]
    train_plus_dev=train+dev
    test_gold=[r['rasa_bucket'] for r in test]
    test_groups=[r['template_id'] for r in test]
    preds={arm:fit_predict(arm,train_plus_dev,test) for arm in NORMAL}
    preds['permuted-training-labels']=fit_predict('permuted-training-labels',train_plus_dev,test,permutation=True)
    preds['majority-label']=fit_predict('majority-label',train_plus_dev,test)
    test_results={arm:evaluate(test_gold,p,classes,test_groups) for arm,p in preds.items()}
    out=root/'reports/research/benchmark_v3';out.mkdir(parents=True,exist_ok=True)
    with (out/'frozen_holdout_predictions_v3.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['item_id','language','template_id','synthetic_rasa_label','reference_raag_id','is_synthetic',*['pred_'+a for a in preds]]
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for i,r in enumerate(test):
            writer.writerow({'item_id':r['item_id'],'language':r['language'],'template_id':r['template_id'],
                  'synthetic_rasa_label':r['rasa_bucket'],'reference_raag_id':r['primary_raag'],'is_synthetic':'true',**{'pred_'+a:preds[a][i] for a in preds}})
    results={
       'benchmark':'MAQAM Option A lexical stress v3',
       'method':'internal split-specific phrase lexicons, seed-derived labels; no musician annotations',
       'label_semantics':'Agreement with four generator-assigned synthetic Rasa theme labels, NOT Raag recognition or musician ratings',
       'all_four_rasa_classes_in_every_split':True,
       'manifest_sha256':sha256_file(root/'evaluation/synthetic_lexical_stress_v3_manifest.json'),
       'frozen_dataset_sha256':m['dataset_sha256'],
       'samples':m['sample_counts'],'groups':m['groups_per_split'],
       'word_ngram_overlap':m['phrase_overlap'],
       'selection_policy':'dev-only: Top1 then macro F1 then fixed arm order',
       'development_scores':dev_results,'selected_model_by_development':selected,
       'test_scores':test_results,
       'negative_control_definition':'permuted-training-labels: deterministic shuffle of train+dev labels, same data/features/hyperparameters; majority-label is lexical-order tie winner',
       'statistical_limits': ['Bootstrap resamples synthetic 36 source groups, all from same generator.',
          'Same split-specific rasa line is reused in many examples; within-group dependency remains.',
          'Synthetic Rasa labels are not assessed or endorsed by musicians; Raag IDs are retained only as source provenance.',
          'This stress test was built after v2 results were inspected, so it is not an unseen prospective benchmark.',
          'A successful metadata model can reflect metadata shortcuts; do not infer poem interpretation.',
          'No across-version accuracy comparison constitutes controlled improvement.'],
       'frontend_build':'not verified in this research experiment'}
    (out/'experiment_summary_v3.json').write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    lines=['# MAQAM AI — Benchmark v3: Lexically disjoint synthetic diagnostic','',
       '**Scope:** synthetic computational evaluation only. No independent musical or human evaluation.','',
       f"Development-selected model: **{selected}**. Dataset: {len(train)} train, {len(dev)} dev, {len(test)} test.",
       'Zero shared four-word and eight-word Unicode-aware phrases across train, dev and test.','',
       '| Arm | Dev Top-1 | Test Top-1 | 95% synthetic source-cluster bootstrap interval |',
       '|---|---:|---:|---:|']
    for arm in NORMAL+CONTROLS:
        score=test_results[arm]
        ci=score['cluster_bootstrap_95pct']
        d=f"{dev_results[arm]['top1']:.3f}" if arm in NORMAL else '—'
        lines.append(f"| {arm} | {d} | {score['top1_generator_label_agreement']:.3f} | [{ci[0]:.3f}, {ci[1]:.3f}] |")
    lines+=['','**DO NOT interpret Rasa classification as Raag correctness.** Synthetic theme labels were assigned by the generator.',
        'The v3 corpus uses different lexical phrases per split but reuses source lexicons, rasa associations and metadata;',
        'the split is not independently collected poetry. Small numbers of generative families create dependence.',
        'A label-permutation diagnostic is a software negative control, not a formal hypothesis test.',
        'Since this benchmark was designed after inspecting v2, it is a retrospective engineering stress test.','']
    (out/'RESULTS_README.md').write_text('\n'.join(lines),encoding='utf-8')
    return results
