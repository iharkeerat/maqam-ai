"""Frozen, split-specific lexical stress diagnostic (Option A).

IMPORTANT: Reuses the project's seed lexicon and musical labels. This is a
NEW synthetic recombination, not independently sourced poetry, and cannot
verify musical fitness or semantic understanding.
"""
from __future__ import annotations
import csv
import hashlib
import json
from collections import Counter
import unicodedata
from pathlib import Path
from research.data_generation import LANGUAGE_BANKS, _primary_rasa, _time_bucket
from research.group_benchmark import sha256_file
from scripts.audit_corpus import audit

SEED = 'maqam-lexical-stress-v3-20261023'
SPLIT_INDEX = {'train': 0, 'dev': 1, 'test': 2}
FIELDNAMES = ('item_id','split','language','poem','primary_raag','accepted_raags',
              'primary_taal','accepted_taals','form','time_hint','template_family',
              'template_id','is_synthetic','provenance','rasa_bucket','variant')


def build_rows(raag_records: list[dict]) -> list[dict[str,str]]:
    if len({r['id'] for r in raag_records}) != len(raag_records):
        raise ValueError('Duplicate Raag identifiers in source')
    rows=[]
    # One representative per generator rasa prevents cloning the same text
    # under multiple Raag labels and creating impossible supervised targets.
    representative={}
    for record in sorted(raag_records,key=lambda r:r['id']):
        representative.setdefault(_primary_rasa(record),record)
    for record in [representative[k] for k in sorted(representative)]:
        rid=str(record['id']); rasa=_primary_rasa(record)
        time=_time_bucket(str(record.get('time','')))
        form=str((record.get('recommendedForms') or ['Khayal'])[0]); taal=str((record.get('recommendedTaals') or ['Teentaal'])[0])
        for language, banks in sorted(LANGUAGE_BANKS.items()):
            for split, index in SPLIT_INDEX.items():
                # Hold out *entire phrase-bank entries*, never mix a phrase
                # from an earlier partition back into development or test.
                primary=banks[rasa][index]
                for variant in range(3):
                    companion_rasas=sorted(banks)
                    companion=companion_rasas[(companion_rasas.index(rasa)+variant+1)%len(companion_rasas)]
                    secondary=banks[companion][index]
                    poem=f'{primary}.\n{secondary}.'
                    item_id='synv3-'+hashlib.sha256(f'{SEED}|{rid}|{language}|{split}|{variant}'.encode()).hexdigest()[:16]
                    rows.append(dict(item_id=item_id, split=split, language=language, poem=poem,
                      primary_raag=rid, accepted_raags=rid, primary_taal=taal,
                      accepted_taals=taal, form=form, time_hint=time,
                      template_family=f'lexical-v3-{split}-{language}-{rasa}',
                      template_id=f'lexical-v3-{split}-{language}-{rasa}',
                      is_synthetic='true', provenance='project-seed-lexicon-recombination-not-independent',
                      rasa_bucket=rasa, variant=str(variant)))
    # text duplicates *within split* can exist if two Raags share rasa; this is
    # disclosed and their conflicting labels are never treated as ground truth.
    return sorted(rows,key=lambda r:r['item_id'])


def normalized_words(text: str) -> list[str]:
    """Unicode-aware tokenization that keeps Devanagari/Gurmukhi/Urdu marks attached."""
    text=unicodedata.normalize('NFC',text).casefold()
    words=[]; current=[]
    for c in text:
        if unicodedata.category(c)[0] in ('L','N','M'):
            current.append(c)
        elif current:
            words.append(''.join(current)); current=[]
    if current:words.append(''.join(current))
    return words


def word_ngrams(text:str,n:int)->set[tuple[str,...]]:
    words=normalized_words(text)
    return {tuple(words[i:i+n]) for i in range(len(words)-n+1)}


def precise_lexical_audit(rows:list[dict],ns=(4,8))->dict:
    result={}
    for n in ns:
        seen={split:set().union(*(word_ngrams(r['poem'],n) for r in rows if r['split']==split)) for split in SPLIT_INDEX}
        result[str(n)]={f'{a}_vs_{b}':{'common_unique_ngrams':len(seen[a]&seen[b]),
                              'examples_affected':sum(bool(word_ngrams(r['poem'],n)&seen[a]) for r in rows if r['split']==b)}
                        for a,b in [('train','dev'),('train','test'),('dev','test')]}
    return result


def validate_rows(rows: list[dict]) -> dict:
    if not rows or any(r.get('is_synthetic')!='true' for r in rows):
        raise ValueError('Missing or non-synthetic corpus')
    kinds={x['language'] for x in rows}
    labels={x['primary_raag'] for x in rows}
    for split in SPLIT_INDEX:
        partition=[r for r in rows if r['split']==split]
        if {r['language'] for r in partition}!=kinds or {r['primary_raag'] for r in partition}!=labels:
            raise ValueError(f'Unbalanced labels/languages in {split}')
    group_report=audit(rows)
    if not group_report['passed']:
        raise ValueError('Cross-split corpus audit failed: '+str(group_report['problems'][:2]))
    lexical=precise_lexical_audit(rows)
    for n in ('4','8'):
        for _,pair in lexical[n].items():
            if pair['common_unique_ngrams'] or pair['examples_affected']:
                raise ValueError(f'{n}-word precise Unicode phrase overlap: {lexical[n]}')
    conflicts={}
    for row in rows:
        key=(row['split'],row['language'],row['poem'])
        conflicts.setdefault(key,set()).add(row['primary_raag'])
    return {'status':'internal-lexical-diagnostic-only',
            'sample_counts':dict(Counter(x['split'] for x in rows)),
            'languages':sorted(kinds),'source_raag_ids_representative_only':len(labels),'synthetic_rasa_labels':sorted({r['rasa_bucket'] for r in rows}),
            'groups_per_split':{s:len({r['template_id'] for r in rows if r['split']==s}) for s in SPLIT_INDEX},
            'phrase_overlap':lexical, 'corpus_audit':group_report,
            'same_text_multiple_primary_labels_within_split':sum(len(v)>1 for v in conflicts.values()),
            'phrase_source':'Existing project seed lexicon: split 0/1/2 phrase entries for train/dev/test',
            'limitations':['Synthetic seed vocabulary and encoded labels are reused; no independent poetry.',
              'All labels are project-assigned and do not establish musical correctness.',
              'Zero 4-gram overlap does not establish independence of generator mechanism.',
              'Shared rasa class or metadata can act as shortcut cues.',
              'Each rasa uses one reference Raag record; Raag columns are provenance only, not evaluation targets.']}


def write_v3(root:Path)->dict:
    source=root/'web/app/data/raag_seed.json'
    records=json.loads(source.read_text(encoding='utf-8'))
    rows=build_rows(records)
    report=validate_rows(rows)
    out=root/'evaluation/synthetic_lexical_stress_v3.csv'; manifest=root/'evaluation/synthetic_lexical_stress_v3_manifest.json'
    with out.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDNAMES);writer.writeheader();writer.writerows(rows)
    report.update(benchmark='MAQAM Option A lexical stress v3',seed=SEED,
                  source_raag_sha256=sha256_file(source),dataset_sha256=sha256_file(out))
    manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def verify_v3(root:Path)->dict:
    source=root/'web/app/data/raag_seed.json';out=root/'evaluation/synthetic_lexical_stress_v3.csv'
    manifest_path=root/'evaluation/synthetic_lexical_stress_v3_manifest.json'
    report=json.loads(manifest_path.read_text(encoding='utf-8'))
    if report['source_raag_sha256']!=sha256_file(source) or report['dataset_sha256']!=sha256_file(out):
        raise ValueError('Frozen v3 input or dataset checksum changed')
    with out.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    rebuilt=build_rows(json.loads(source.read_text(encoding='utf-8')))
    if rows!=rebuilt:
        raise ValueError('v3 dataset fails deterministic regeneration')
    fresh=validate_rows(rows)
    for key in ('sample_counts','groups_per_split','phrase_overlap','same_text_multiple_primary_labels_within_split'):
        if fresh[key]!=report[key]: raise ValueError(f'v3 manifest mismatch: {key}')
    return report
