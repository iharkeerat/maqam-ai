"""Upgrade 12: reproducible, *retrospective* synthetic competitive baselines.

No hosted API is called. No musical correctness is measured. v3 test examples
were observed during upgrades 09–11; v5 is a POST-HOC comparator study.
"""
from __future__ import annotations
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC

from research.lexical_stress_v3 import verify_v3
from research.group_benchmark import sha256_file
from research.multilingual_shortcuts_v4 import frozen_dataset_rows, time_counterfactuals

SEED=20261023
LABELS=('bhakti','karuna','shanta','shringara')
ARMS=(
  'majority-prior',
  'time-majority-rule',
  'word-tfidf-logreg',
  'char-tfidf-logreg',
  'char-tfidf-linear-svm',
  'char-count-complement-nb',
  'char-plus-metadata-logreg',
  'metadata-only-logreg',
)
MODEL_SPECS={
 'majority-prior':'Most frequent synthetic training label (tie: sorted label)',
 'time-majority-rule':'Training-only most frequent label conditional on time metadata',
 'word-tfidf-logreg':'Word 1–2 TF-IDF + regularized logistic regression',
 'char-tfidf-logreg':'Char_wb 3–5 TF-IDF + regularized logistic regression',
 'char-tfidf-linear-svm':'Char_wb 3–5 TF-IDF + LinearSVC',
 'char-count-complement-nb':'Char_wb 3–5 counts + ComplementNB',
 'char-plus-metadata-logreg':'Char_wb 3–5 TF-IDF + logistic regression on text + metadata',
 'metadata-only-logreg':'Char_wb 3–5 TF-IDF + logistic regression on metadata only',
}


def features(row:dict,arm:str)->str:
    if arm in ('char-plus-metadata-logreg','metadata-only-logreg'):
        meta=f"[TIME={row['time_hint']}] [LANG={row['language']}] [FORM={row['form']}]"
        if arm=='metadata-only-logreg':return meta
        return row['poem']+' '+meta
    return row['poem']


def model_factory(arm:str):
    if arm=='word-tfidf-logreg':
        return make_pipeline(TfidfVectorizer(analyzer='word',ngram_range=(1,2),lowercase=True,
                             token_pattern=r'(?u)\b\w+\b',min_df=1),
                             LogisticRegression(max_iter=1500,random_state=SEED))
    if arm in ('char-tfidf-logreg','char-plus-metadata-logreg','metadata-only-logreg'):
        return make_pipeline(TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=1),
                             LogisticRegression(max_iter=1500,random_state=SEED))
    if arm=='char-tfidf-linear-svm':
        return make_pipeline(TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=1),
                             LinearSVC(random_state=SEED))
    if arm=='char-count-complement-nb':
        return make_pipeline(CountVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=1),ComplementNB())
    raise ValueError('Unrecognized trainable model: '+arm)


def fit_arm(arm:str,rows:list[dict]):
    if arm not in ARMS or not rows:raise ValueError('Unrecognized arm or empty training rows')
    y=[r['rasa_bucket'] for r in rows]
    if arm=='majority-prior':
        return ('prior',sorted(Counter(y).items(),key=lambda p:(-p[1],p[0]))[0][0])
    if arm=='time-majority-rule':
        groups={}
        for time in sorted({r['time_hint'] for r in rows}):
            values=Counter(r['rasa_bucket'] for r in rows if r['time_hint']==time)
            groups[time]=sorted(values.items(),key=lambda p:(-p[1],p[0]))[0][0]
        global_label=sorted(Counter(y).items(),key=lambda p:(-p[1],p[0]))[0][0]
        return ('time-rule',(groups,global_label))
    model=model_factory(arm)
    model.fit([features(r,arm) for r in rows],y)
    return ('sklearn',model)


def predict_arm(arm:str,fitted,rows:list[dict])->list[str]:
    kind,model=fitted
    if kind=='prior':return [model]*len(rows)
    if kind=='time-rule':
        groups,fallback=model
        return [groups.get(r['time_hint'],fallback) for r in rows]
    return list(model.predict([features(r,arm) for r in rows]))


def metric(gold,pred)->dict:
    if len(gold)!=len(pred) or not gold:raise ValueError('Missing or unequal paired data')
    if set(gold)-set(LABELS) or set(pred)-set(LABELS):raise ValueError('Unrecognized class label')
    return {'agreement':round(float(accuracy_score(gold,pred)),6),
            'macro_f1':round(float(f1_score(gold,pred,labels=LABELS,average='macro',zero_division=0)),6)}


def clustered_paired_difference(gold:list[str],pred_a:list[str],pred_b:list[str],groups:list[str],
                                  seed:int=SEED,reps:int=2000)->dict:
    if not(len(gold)==len(pred_a)==len(pred_b)==len(groups)) or not gold:
        raise ValueError('Unequal paired inputs')
    ordered=sorted(set(groups))
    if len(ordered)<3:raise ValueError('Need at least three source groups')
    by_group={g:[i for i,x in enumerate(groups) if x==g] for g in ordered}
    delta=np.array([int(a==g)-int(b==g) for g,a,b in zip(gold,pred_a,pred_b)],dtype=float)
    rng=np.random.default_rng(seed)
    draws=[]
    for _ in range(reps):
        chosen=rng.integers(0,len(ordered),len(ordered))
        idx=[i for choice in chosen for i in by_group[ordered[int(choice)]]]
        draws.append(float(np.mean(delta[idx])))
    return {'paired_agreement_difference':round(float(np.mean(delta)),6),
            'descriptive_95pct_cluster_bootstrap':[round(float(v),6) for v in np.quantile(draws,[0.025,0.975])],
            'source_group_count':len(ordered),'bootstrap_draws':reps,
            'not_inference_for':'Natural poetry, musical correctness, or independent external generalization'}


def _csv_rows(path:Path)->list[dict]:
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def validate_external_predictions(root:Path,submission:Path)->dict:
    """Fail-closed offline ingestion. No claim outputs came from actual hosted LLM.

    Only an externally obtained model response may be entered in user-filled CSV.
    Results are descriptive on a REUSED, synthetic diagnostic, never expert truth.
    """
    if not submission.is_file():raise ValueError('External predictions file missing')
    train,dev,test=frozen_dataset_rows(root)
    rows=_csv_rows(submission)
    required={'item_id','predicted_rasa'}
    if not rows or not required.issubset(rows[0]):raise ValueError('Missing prediction CSV fields')
    expected={r['item_id']:r for r in test}
    if len(rows)!=len(expected) or len({r['item_id'] for r in rows})!=len(rows):
        raise ValueError('Incomplete or duplicate external response rows')
    if {r['item_id'] for r in rows}!=set(expected):
        raise ValueError('External responses do not match exact frozen item IDs')
    for row in rows:
        if row['predicted_rasa'] not in LABELS:
            raise ValueError('Invalid label, refusal or nonconforming response: '+str(row['predicted_rasa']))
    by_id={r['item_id']:r['predicted_rasa'] for r in rows}
    ordered=[by_id[r['item_id']] for r in test]
    results=metric([r['rasa_bucket'] for r in test],ordered)
    return {'status':'INGESTED_UNVERIFIED_MODEL_PROVENANCE',
      'submitted_file_sha256':sha256_file(submission),
      'dataset_sha256':sha256_file(root/'evaluation/synthetic_lexical_stress_v3.csv'),
      'sample_n':len(test),'synthetic_generator_label_scores':results,
      'source_warning':'User-supplied prediction file. Model identity, prompt, sampling settings and genuine API execution cannot be established by this parser.',
      'scientific_warning':'Already-inspected synthetic holdout; not musical correctness or a prospective model contest.'}


def write_external_scoring_template(root:Path,out:Path)->None:
    """Write an UNFILLED scoring CSV. Does not invent hosted model predictions."""
    _,_,test=frozen_dataset_rows(root)
    with out.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['item_id','predicted_rasa'])
        for row in test:w.writerow([row['item_id'],''])


def write_external_prompts(root:Path,out:Path)->None:
    """Make blinded prompt inputs; never include target synthetic class labels."""
    _,_,test=frozen_dataset_rows(root)
    with out.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['item_id','language','poem','prompt'])
        for r in test:
            prompt=('Classify the following synthetic poetry excerpt into exactly one of '
                    'bhakti, karuna, shanta, shringara. Output only the single lowercase label. '
                    'Do not assume this label establishes a musically appropriate Raag.\n\n'+r['poem'])
            w.writerow([r['item_id'],r['language'],r['poem'],prompt])


def run_v5(root:Path)->dict:
    root=Path(root)
    verify_v3(root)
    train,dev,test=frozen_dataset_rows(root)
    source=root/'evaluation/synthetic_lexical_stress_v3.csv'
    ydev=[r['rasa_bucket'] for r in dev]
    dev_scores={}
    for arm in ARMS:
        obj=fit_arm(arm,train)
        dev_scores[arm]=metric(ydev,predict_arm(arm,obj,dev))
    # Winner chosen using development labels, never test labels. However v3
    # holdout was previously inspected in earlier upgrades; report is retrospective.
    selected=sorted(ARMS,key=lambda a:(-dev_scores[a]['agreement'],-dev_scores[a]['macro_f1'],ARMS.index(a)))[0]
    combined=train+dev
    gold=[r['rasa_bucket'] for r in test]
    groups=[r['template_id'] for r in test]
    swapped=time_counterfactuals(test)
    preds={};swapped_preds={};test_scores={}
    for arm in ARMS:
        obj=fit_arm(arm,combined)
        predictions=predict_arm(arm,obj,test)
        alt=predict_arm(arm,obj,swapped)
        preds[arm]=predictions;swapped_preds[arm]=alt
        test_scores[arm]={**metric(gold,predictions),
            'time_metadata_swap_flip_rate':round(sum(x!=y for x,y in zip(predictions,alt))/len(test),6),
            'by_language':{lang:{'n':len(idx),'agreement':round(sum(predictions[i]==gold[i] for i in idx)/len(idx),6)}
                           for lang in sorted({r['language'] for r in test})
                           for idx in [[i for i,r in enumerate(test) if r['language']==lang]]}}
    differences={arm:clustered_paired_difference(gold,preds[arm],preds['majority-prior'],groups)
                 for arm in ARMS if arm!='majority-prior'}
    # Negative control: deliberately destroy training-label association. Three
    # deterministic permutations are descriptive checks, not a null test.
    shuffled_label_controls=[]
    original_labels=np.array([r['rasa_bucket'] for r in combined])
    for control_seed in (17, 43, 101):
        permuted=np.random.default_rng(control_seed).permutation(original_labels)
        shuffled_model=model_factory('char-tfidf-logreg')
        shuffled_model.fit([features(r,'char-tfidf-logreg') for r in combined],permuted)
        control_predictions=list(shuffled_model.predict([features(r,'char-tfidf-logreg') for r in test]))
        shuffled_label_controls.append({'seed':control_seed,**metric(gold,control_predictions),
          'note':'Training-label permutation; synthetic exploratory negative control only'})
    # Do not train on test labels, even when generating a diagnostic.
    out=root/'reports/research/benchmark_v5';out.mkdir(parents=True,exist_ok=True)
    with (out/'frozen_local_predictions_v5.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['item_id','language','template_id','synthetic_rasa_label',*['pred_'+a for a in ARMS],*['time_swap_'+a for a in ARMS]]
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for i,r in enumerate(test):
            writer.writerow({'item_id':r['item_id'],'language':r['language'],'template_id':r['template_id'],
                 'synthetic_rasa_label':r['rasa_bucket'],
                 **{f'pred_{a}':preds[a][i] for a in ARMS},
                 **{f'time_swap_{a}':swapped_preds[a][i] for a in ARMS}})
    write_external_scoring_template(root,out/'external_llm_responses_TEMPLATE.csv')
    write_external_prompts(root,out/'external_llm_prompts_NO_GOLD.csv')
    result={
      'name':'MAQAM Option A v5 local competitive baselines',
      'status':'POST_HOC_COMPUTATIONAL_DIAGNOSTIC_NOT_INDEPENDENT_VALIDATION',
      'dataset_sha256':sha256_file(source),
      'manifest_sha256':sha256_file(root/'evaluation/synthetic_lexical_stress_v3_manifest.json'),
      'split_counts':{'train':len(train),'dev':len(dev),'test':len(test)},
      'independent_synthetic_source_groups_test':len(set(groups)),
      'task':'4-class generator-assigned synthetic Rasa category agreement, NOT Raag or music correctness',
      'label_set':list(LABELS),
      'random_seed':SEED,
      'baseline_specs':MODEL_SPECS,
      'selection_policy':'Fixed candidate set; select on development agreement, macro F1, then model order; refit all on train + development',
      'development_scores':dev_scores,
      'selected_by_development':selected,
      'test_scores':test_scores,
      'paired_vs_majority':differences,
      'shuffled_training_label_controls':shuffled_label_controls,
      'hosted_llm_runs':0,
      'hosted_llm_comparison_status':'NOT RUN; no authenticated API output or verified model provenance',
      'limitations':[
         'Retrospective: v3 test partition has been inspected in upgrades 09–11; not independent confirmatory evidence.',
         'Dataset is generated from project lexicons and contains only 48 held-out synthetic cases.',
         'All outcomes score synthetic generator labels, not Raag suitability, poetry interpretation or artistic quality.',
         'Source clusters are generated from one source mechanism; bootstrap intervals are descriptive only.',
         'An internal majority/time rule may exploit dataset confounding and is not a published music-theory baseline.',
         'No large language model, music generator or external API was tested.',
         'Language subgroup sizes are very small (12 each); comparisons are exploratory.',
         'The benchmark was constructed after prior system development; formal musical-rule benchmarks need independently sourced standards.'
      ]}
    (out/'experiment_summary_v5.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    lines=['# Upgrade 12 — Local competitive baseline study (v5)','',
       '**Research scope:** controlled *local* comparison on 48 synthetic, previously examined examples.',
       'The result is NOT confirmation of musical validity, superiority to commercial AI, or transfer to genuine poetry.','',
       f"Development-selected arm (pre-test for this rerun): **{selected}**.",
       '| Baseline | Dev agreement | Test agreement | Test macro F1 | Time metadata flip |',
       '|---|---:|---:|---:|---:|']
    for arm in ARMS:
        a=dev_scores[arm];b=test_scores[arm]
        lines.append(f"| {arm} | {a['agreement']:.1%} | {b['agreement']:.1%} | {b['macro_f1']:.3f} | {b['time_metadata_swap_flip_rate']:.1%} |")
    lines += ['', '## Appropriate interpretation','',
       'These are **exploratory internal controls**, not a rigorous contest against ChatGPT/Gemini/Suno.',
       'The metadata-swap metric indicates prediction sensitivity, not necessarily an error.',
       'Three deterministic shuffled-label controls are reported in experiment_summary_v5.json; these are NOT formal significance tests.',
       'Model selection within this run is based on development data, but the test dataset was analyzed earlier.',
       'Do not choose claims or hyperparameters by these retrospective test outcomes and call them confirmatory.','',
       '## External LLM evaluation (not executed)','',
       '- `external_llm_prompts_NO_GOLD.csv` contains blinded item prompts with no gold label.',
       '- `external_llm_responses_TEMPLATE.csv` contains empty prediction cells and must be completed with genuine outputs.',
       '- `python scripts/run_competitive_baselines_v5.py --score-external PATH` validates exact item coverage and allowed labels.',
       '- Record model/version, date, API or UI, prompt, settings, failures and response provenance separately; CSV scoring alone cannot authenticate them.',
       '- Any comparison remains on a retrospectively examined **synthetic Rasa classification** task, not musical aptitude.','']
    (out/'RESULTS_README.md').write_text('\n'.join(lines),encoding='utf-8')
    return result


def verify_v5(root:Path)->dict:
    """Recalculate every archived test score and sensitivity rate from frozen rows."""
    root=Path(root)
    summary=json.loads((root/'reports/research/benchmark_v5/experiment_summary_v5.json').read_text(encoding='utf-8'))
    assert summary['dataset_sha256']==sha256_file(root/'evaluation/synthetic_lexical_stress_v3.csv'), 'Dataset changed'
    assert summary['manifest_sha256']==sha256_file(root/'evaluation/synthetic_lexical_stress_v3_manifest.json'), 'Dataset manifest changed'
    _,_,test=frozen_dataset_rows(root)
    frozen=_csv_rows(root/'reports/research/benchmark_v5/frozen_local_predictions_v5.csv')
    if len(test)!=len(frozen):raise ValueError('Frozen predictions have incorrect row count')
    by_id={r['item_id']:r for r in frozen}
    if len(by_id)!=len(test) or set(by_id)!={r['item_id'] for r in test}:
        raise ValueError('Missing/duplicate/mismatched prediction IDs')
    for arm in ARMS:
        ordered=[by_id[r['item_id']] for r in test]
        for r,p in zip(test,ordered):
            if p['synthetic_rasa_label']!=r['rasa_bucket'] or p['language']!=r['language'] or p['template_id']!=r['template_id']:
                raise ValueError('Frozen source metadata mismatch')
        original=[p['pred_'+arm] for p in ordered]
        alternate=[p['time_swap_'+arm] for p in ordered]
        computed=metric([r['rasa_bucket'] for r in test],original)
        flip=round(sum(a!=b for a,b in zip(original,alternate))/len(test),6)
        if any(computed[k]!=summary['test_scores'][arm][k] for k in computed):
            raise ValueError(f'Frozen score mismatch: {arm}')
        if flip!=summary['test_scores'][arm]['time_metadata_swap_flip_rate']:
            raise ValueError(f'Frozen time intervention mismatch: {arm}')
        if set(original+alternate)-set(LABELS):raise ValueError('Invalid frozen predicted class')
    if summary['hosted_llm_runs']!=0 or not summary['status'].startswith('POST_HOC'):
        raise ValueError('Unsubstantiated research/evaluation status')
    if set(summary['test_scores'])!=set(ARMS) or set(summary['development_scores'])!=set(ARMS):
        raise ValueError('Missing/comparator arms differ')
    return {'status':'PASS_ARCHIVED_SYNTHETIC_SCORES_ONLY','rows':len(test),'arms':len(ARMS),
       'dataset_sha256':summary['dataset_sha256'],'hosted_llm_runs':0,
       'interpretation':'Internal consistency only; not independently confirmed or musician validated'}
