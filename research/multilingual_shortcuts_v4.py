"""Option-A synthetic multilingual / metadata-shortcut audit (v4).

This is a retrospective engineering diagnostic on the publicly inspected v3
synthetic holdout. It tests generator-label prediction only, NOT music quality,
Rasa semantics, true translation performance, or independent generalization.
"""
from __future__ import annotations
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score

from research.lexical_stress_v3 import verify_v3
from research.lexical_stress_experiment import build_arm, evaluate, SEED
from research.group_benchmark import sha256_file

ARMS = ('text-only','full-metadata','no-time-token','balanced-time-augmentation','metadata-only')
LANGUAGES = ('Hindi','Punjabi','Roman','Urdu')
LABELS = ('bhakti','karuna','shanta','shringara')
VERSION = 'v4-option-a-2026-10-23'


def format_features(row:dict, arm:str)->str:
    if arm == 'text-only':
        return row['poem']
    if arm == 'metadata-only':
        return f"[FORM={row['form']}] [TIME={row['time_hint']}] [LANG={row['language']}]"
    if arm == 'no-time-token':
        return f"{row['poem']} [FORM={row['form']}] [LANG={row['language']}]"
    if arm in ('full-metadata','balanced-time-augmentation'):
        return f"{row['poem']} [FORM={row['form']}] [TIME={row['time_hint']}] [LANG={row['language']}]"
    raise ValueError('Unknown experimental arm')


def make_training(rows:list[dict],arm:str)->tuple[list[str],list[str]]:
    if arm not in ARMS:raise ValueError('Unknown experimental arm')
    examples=[];labels=[]
    for row in rows:
        if arm=='balanced-time-augmentation':
            # Both possible TIME tokens for *every* training example. This removes
            # the marginal time->label signal in training; script stays faithful.
            for clock in ('morning','night'):
                updated={**row,'time_hint':clock}
                examples.append(format_features(updated,arm));labels.append(row['rasa_bucket'])
        else:
            examples.append(format_features(row,arm));labels.append(row['rasa_bucket'])
    return examples,labels


def train_model(rows:list[dict],arm:str):
    X,y=make_training(rows,arm)
    model=build_arm('char-text-only')
    model.fit(X,y)
    return model


def predict(model, rows:list[dict],arm:str)->list[str]:
    return list(model.predict([format_features(r,arm) for r in rows]))


def time_counterfactuals(rows:list[dict])->list[dict]:
    valid={'morning','night'}
    if any(r['time_hint'] not in valid for r in rows):raise ValueError('Unexpected time category')
    return [{**r,'time_hint':'night' if r['time_hint']=='morning' else 'morning'} for r in rows]


def language_marker_counterfactuals(rows:list[dict])->list[dict]:
    # This deliberately changes only LANGUAGE metadata, not script/poetry.
    # It is NOT a translation experiment.
    seq={name:LANGUAGES[(i+1)%len(LANGUAGES)] for i,name in enumerate(LANGUAGES)}
    if any(r['language'] not in seq for r in rows):raise ValueError('Unknown language')
    return [{**r,'language':seq[r['language']]} for r in rows]


def flip_rate(a:list[str],b:list[str])->float:
    if not a or len(a)!=len(b):raise ValueError('Invalid paired predictions')
    return round(sum(x!=y for x,y in zip(a,b))/len(a),6)


def matched_condition_groups(rows:list[dict],predictions:list[str])->dict:
    """Same generator Rasa bucket/variant across four scripts, NOT translations."""
    if len(rows)!=len(predictions):raise ValueError('Missing predictions')
    grouped=defaultdict(list)
    for row,pred in zip(rows,predictions):
        grouped[(row['rasa_bucket'],row['variant'])].append((row['language'],pred))
    all_four=0;identical=0
    for key,values in grouped.items():
        langs=[x[0] for x in values]
        if set(langs)!=set(LANGUAGES) or len(values)!=4:raise ValueError('Unbalanced generator condition '+str(key))
        all_four+=1;identical+=len({x[1] for x in values})==1
    return {'matched_generator_conditions':all_four,
            'all_four_script_prediction_agreement':round(identical/all_four,6),
            'note':'These are different synthetic texts with matched source conditions, NOT translations.'}


def language_breakdown(rows:list[dict],predictions:list[str])->dict:
    out={}
    for name in LANGUAGES:
        idx=[i for i,r in enumerate(rows) if r['language']==name]
        if not idx:raise ValueError('Missing language '+name)
        correct=sum(predictions[i]==rows[i]['rasa_bucket'] for i in idx)
        out[name]={'n':len(idx),'generator_label_agreement':round(correct/len(idx),6)}
    return out


def frozen_dataset_rows(root:Path):
    verify_v3(root)
    path=root/'evaluation/synthetic_lexical_stress_v3.csv'
    with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    if len(rows)!=144 or Counter(r['split'] for r in rows)!=Counter({'train':48,'dev':48,'test':48}):
        raise ValueError('Unexpected frozen dataset counts')
    if {r['language'] for r in rows}!=set(LANGUAGES) or {r['rasa_bucket'] for r in rows}!=set(LABELS):
        raise ValueError('Unexpected source language/label definition')
    train=[r for r in rows if r['split']=='train']
    dev=[r for r in rows if r['split']=='dev']
    test=[r for r in rows if r['split']=='test']
    return train,dev,test


def run_v4(root:Path)->dict:
    train,dev,test=frozen_dataset_rows(root)
    # All arms fixed a priori. Scores on dev are computed BEFORE any test inference.
    dev_scores={}
    for arm in ARMS:
        model=train_model(train,arm)
        p=predict(model,dev,arm)
        dev_scores[arm]={'generator_label_agreement':round(float(np.mean([a==r['rasa_bucket'] for a,r in zip(p,dev)])),6),
                         'macro_f1':round(float(f1_score([r['rasa_bucket'] for r in dev],p,labels=LABELS,average='macro',zero_division=0)),6)}
    mitigations=('no-time-token','balanced-time-augmentation')
    # Selection only among the two prespecified mitigation arms; deterministic tie-break.
    chosen=sorted(mitigations,key=lambda a:(-dev_scores[a]['generator_label_agreement'],-dev_scores[a]['macro_f1'],mitigations.index(a)))[0]
    combined=train+dev
    outdir=root/'reports/research/benchmark_v4';outdir.mkdir(parents=True,exist_ok=True)
    scores={};preds={};timepred={};langpred={};frozen=[]
    for arm in ARMS:
        model=train_model(combined,arm)
        base=predict(model,test,arm)
        altered_time=predict(model,time_counterfactuals(test),arm)
        altered_lang=predict(model,language_marker_counterfactuals(test),arm)
        preds[arm]=base;timepred[arm]=altered_time;langpred[arm]=altered_lang
        e=evaluate([r['rasa_bucket'] for r in test],base,list(LABELS),[r['template_id'] for r in test],replicates=1000,seed=SEED)
        scores[arm]={**e,'by_language':language_breakdown(test,base),
            'time_token_flip_rate':flip_rate(base,altered_time),
            'language_token_flip_rate':flip_rate(base,altered_lang),
            'matched_generator_script_consistency':matched_condition_groups(test,base)}
    with (outdir/'frozen_prediction_comparisons_v4.csv').open('w',encoding='utf-8-sig',newline='') as f:
        names=['item_id','language','template_id','rasa_generator_label',*sum(([f'base_{arm}',f'time_swap_{arm}',f'language_marker_swap_{arm}'] for arm in ARMS),[])]
        writer=csv.DictWriter(f,fieldnames=names);writer.writeheader()
        for i,r in enumerate(test):
            item={'item_id':r['item_id'],'language':r['language'],'template_id':r['template_id'],'rasa_generator_label':r['rasa_bucket']}
            for arm in ARMS:
                item.update({f'base_{arm}':preds[arm][i],f'time_swap_{arm}':timepred[arm][i],f'language_marker_swap_{arm}':langpred[arm][i]})
            writer.writerow(item)
    # Leave-one-script-out diagnostic: no training text in target script.
    loso={}
    for withheld in LANGUAGES:
        subset=[r for r in combined if r['language']!=withheld]
        held=[r for r in test if r['language']==withheld]
        model=train_model(subset,'text-only')
        p=predict(model,held,'text-only')
        loso[withheld]={'train_n':len(subset),'test_n':len(held),
            'text_only_generator_label_agreement':round(sum(a==r['rasa_bucket'] for a,r in zip(p,held))/len(held),6),
            'note':'Retrospective script withholding within synthetic source-generator family; not zero-shot language understanding.'}
    out={
      'study':'MAQAM Option A multilingual / metadata-shortcut v4',
      'version':VERSION,'status':'retrospective computational diagnostic; no external validation',
      'dataset_sha256':sha256_file(root/'evaluation/synthetic_lexical_stress_v3.csv'),
      'manifest_sha256':sha256_file(root/'evaluation/synthetic_lexical_stress_v3_manifest.json'),
      'split_counts':{'train':len(train),'dev':len(dev),'test':len(test)},
      'synthetic_rasa_labels':list(LABELS),
      'protocol':{
        'model':'char_wb TF-IDF 3-5 + logistic regression, C=2.0, class balanced; same fixed hyperparameters across arms',
        'time_augmentation':'every train row repeated with morning and night time token; same gold label and poem',
        'time_intervention':'swap morning and night in test metadata while preserving text, form, language and labels',
        'language_intervention':'cyclically swap language marker in metadata only; preserve poem script (not translation)',
        'matched_groups':'same generator Rasa bucket and variant across four language-specific, nontranslated source texts',
        'selection':'dev-only, among two prespecified mitigation arms; test outcomes not used to select',
        'training':'dev uses train; test models use train+dev; LOSO uses train+dev excluding target language',
        'statistical_limits':'48 synthetic test cases; 16 generator source groups; bootstrap is descriptive',
      },
      'development_scores':dev_scores,'chosen_mitigation_by_dev':chosen,
      'test_scores':scores,'leave_one_script_out_text_only':loso,
      'limitations':[
        'Four generator-defined Rasa labels are not expert-validated semantic or musical truth.',
        'The v3 test has already been analyzed in Upgrade 09; v4 is not an unseen independent confirmatory test.',
        'Texts matched by generator condition are NOT translations and cannot validate translation invariance.',
        'Language-tag counterfactual is intentionally out of distribution (tag and script disagree).',
        'The time-token swap alters potentially meaningful metadata; a stable prediction is not automatically more correct.',
        'Time and synthetic label are confounded by corpus generation (one theme night; three morning).',
        'Same generator vocabulary, templates and sources underlie all four scripts and experiment arms.',
        'No genuine poetry, independent expert evaluation, or real-world Raag recognition is assessed.'
      ]}
    (outdir/'experiment_summary_v4.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# MAQAM AI — Upgrade 10: Multilingual and shortcut diagnostic', '',
      '**Method:** synthetic internal Rasa-label agreement only. No musician validation, translation pairs, or independent corpus.','',
      f"Dev-selected mitigation (among two): **{chosen}**. Test set: **{len(test)}** synthetic examples.",'',
      '| Arm | Development | Test | Time swap flip | Language-tag swap flip | Across-script matched condition consistency |',
      '|---|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        x=scores[arm]
        lines.append(f"| {arm} | {dev_scores[arm]['generator_label_agreement']:.3f} | {x['top1_generator_label_agreement']:.3f} | {x['time_token_flip_rate']:.3f} | {x['language_token_flip_rate']:.3f} | {x['matched_generator_script_consistency']['all_four_script_prediction_agreement']:.3f} |")
    lines+=['','## Script-held-out synthetic stress','', '| Held-out script | Text-only synthetic test agreement |','|---|---:|']
    for k,v in loso.items():lines.append(f"| {k} | {v['text_only_generator_label_agreement']:.3f} |")
    lines+=['','**Do not treat matched-condition texts as translations**, or generator Rasa agreement as real-world Raag accuracy.',
             'Development selection is prospective only within this already-inspected v3 dataset; results are exploratory.',
             'Source group bootstrap intervals are descriptive and do not quantify uncertainty for natural-language poems.','']
    (outdir/'RESULTS_README.md').write_text('\n'.join(lines),encoding='utf-8')
    return out
