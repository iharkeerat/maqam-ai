"""CLI for generating *separated* formal solver inputs and gold references.

This tool will not create files unless all checks pass, and refuses overwrites.
"""
from __future__ import annotations

import argparse, json, shutil, tempfile
from pathlib import Path
from .notation_adapter import extract_score
from .integration import formal_case, held_out_reference, sanitized_projection
from .identifiability import summarize_for_public_api, formal_spans_crossing_rests
from research.pronunciation_rhythm.core import composed_dp, verify_solution


def _isolated(a: Path, b: Path, source: Path) -> None:
    a=a.resolve();b=b.resolve();source=source.resolve()
    if a==b or a in b.parents or b in a.parents:
        raise ValueError('Public/private destinations must be disjoint and nonnested')
    if a.exists() or b.exists():
        raise FileExistsError('Choose fresh output directories; refusing overwrite')
    if a==source or b==source or a in source.parents or b in source.parents or source in a.parents or source in b.parents:
        raise ValueError('Source and outputs cannot contain each other')


def generate(source: Path, public_dir: Path, private_dir: Path, *, syllables: int, max_span: int=3, run_dp: bool=True) -> dict:
    """Prepare sanitized rhythm inputs and a private reference, with strict isolation."""
    _isolated(public_dir,private_dir,source)
    raw=extract_score(source)
    public=sanitized_projection(raw)
    case=formal_case(public,syllables,max_events_per_syllable=max_span)
    ambiguity=(summarize_for_public_api(public['normalized_event_count'],syllables,max_span,public['normalized_groups'])
               if public['normalized_event_count']<=350 else
               {'analysis_skipped':'exact ambiguity summary intentionally capped at 350 events'})
    gold=held_out_reference(raw)
    result=None
    if run_dp:
        solution=composed_dp(case)
        if solution.solution and not verify_solution(case,solution.solution):
            raise AssertionError('independent witness verification failed')
        result={
            'status':solution.status,
            'formal_solution_ends':list(solution.solution.ends) if solution.solution else None,
            'cost':solution.solution.cost if solution.solution else None,
            'dp_expansions':solution.expansions,
            'source_lyric_anchors_used_for_prediction':False,
            'real_accuracy_scored':False,
            'formal_identifiability':ambiguity,
            'predicted_syllable_indices_crossing_score_rests':formal_spans_crossing_rests(
                solution.solution.ends,public['rest_gap_before_normalized_event_indices']) if solution.solution else [],
        }
    info={'published_input_format':public['format'],
          'original_chords':public['original_chord_count'],
          'normalized_events':public['normalized_event_count'],
          'gold_lyric_anchors':gold['annotated_syllables'],
          'external_supplied_syllables':syllables,
          'solver':result,
          'formal_identifiability':ambiguity,
          'model_scope':'formal only, not validated pronunciation/score alignment'}
    public_files={'SOLVER_INPUT.json':public,
                  'FORMAL_SETUP.json':{'external_syllable_count':syllables,'max_events_per_syllable':max_span,
                                       'formal_provenance':'constructed_formal_only'},
                  'FORMAL_OUTPUT.json':result if result is not None else {'solver_not_run':True}}
    private_files={'HELD_OUT_SCORE_REFERENCE.json':gold,
                   'INGESTION_AUDIT.json':info}
    public_dir=public_dir.resolve();private_dir=private_dir.resolve()
    created=[]
    try:
        public_dir.mkdir(parents=True);created.append(public_dir)
        private_dir.mkdir(parents=True);created.append(private_dir)
        for name,obj in public_files.items():
            (public_dir/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        for name,obj in private_files.items():
            (private_dir/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    except Exception:
        for folder in reversed(created): shutil.rmtree(folder,ignore_errors=True)
        raise
    return info


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--public-dir',type=Path,required=True)
    p.add_argument('--private-dir',type=Path,required=True)
    p.add_argument('--syllables',type=int,required=True,help='Count supplied independently, never guessed from annotations')
    p.add_argument('--max-span',type=int,default=3)
    p.add_argument('--no-dp',action='store_true')
    a=p.parse_args()
    result=generate(a.source,a.public_dir,a.private_dir,syllables=a.syllables,max_span=a.max_span,run_dp=not a.no_dp)
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
