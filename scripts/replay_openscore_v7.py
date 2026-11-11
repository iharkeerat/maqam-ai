"""Reproduce V7 on ORIGINAL pinned OpenScore bytes, fail closed if missing.

Only a source compatibility and tie-chain audit; NO alignment model performance.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.score_ingestion.notation_adapter import extract_score, UnsupportedNotation
from research.score_ingestion.integration import sanitized_projection,held_out_reference

ROOT=Path(__file__).resolve().parents[1]
manifest_file=ROOT/'research/score_ingestion/PINNED_OPENSCORE_V6.json'


def git_blob_sha(data:bytes)->str:
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def check(base:Path)->dict:
    records=json.loads(manifest_file.read_text(encoding='utf-8'))['scores']
    out=[]
    for r in records:
        item={'name':r['name'],'source_path':r['path'],'status':'MISSING_ORIGINAL'}
        p=base/r['path']
        if not p.is_file():out.append(item);continue
        raw=p.read_bytes();sha=git_blob_sha(raw)
        item['git_blob_sha_observed']=sha
        if sha!=r['git_blob_sha1']:
            item['status']='BLOB_SHA_MISMATCH';out.append(item);continue
        try:
            score=extract_score(raw)
            projection=sanitized_projection(score)
            gold=held_out_reference(score)
        except UnsupportedNotation as e:
            if r['v6_expected']=='EXCLUDED' and r.get('expected_reason_contains','') in str(e):
                item['status']='EXPECTED_EXCLUSION';item['reason']=str(e)
            else:
                item['status']='UNEXPECTED_EXCLUSION';item['reason']=str(e)
        else:
            if r['v6_expected']=='EXCLUDED':item['status']='UNEXPECTED_ACCEPTANCE'
            elif (score['chord_count'],score['lyric_anchor_count'])!=(r['chords'],r['lyric_anchors']):
                item['status']='V6_ANCHOR_COUNT_MISMATCH'
            else:
                item['status']='VERIFIED_V7'
                item['original_chords']=score['chord_count']
                item['normalized_events']=projection['normalized_event_count']
                item['tie_chords_removed']=score['chord_count']-projection['normalized_event_count']
                item['annotation_count_private']=gold['annotated_syllables']
                item['gold_lyric_on_tied_continuations']=len(gold['gold_on_tie_continuation_chord_indices'])
        out.append(item)
    ok=all(x['status'] in ('VERIFIED_V7','EXPECTED_EXCLUSION') for x in out)
    return {'source_commit':'38c5db510224d9facdc4b08d741fc788cfb58ea8',
            'original_file_count':sum(x['status']!='MISSING_ORIGINAL' for x in out),
            'all_pinned_originals_replayed':ok,'alignment_accuracy_measured':False,
            'files':out}


def main():
    p=argparse.ArgumentParser();p.add_argument('--score-root',type=Path,required=True)
    p.add_argument('--output',type=Path)
    a=p.parse_args();out=check(a.score_root)
    if a.output:a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,indent=2))
    if not out['all_pinned_originals_replayed']:raise SystemExit(2)

if __name__=='__main__':main()
