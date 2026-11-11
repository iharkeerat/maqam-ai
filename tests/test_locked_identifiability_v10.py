"""V10 independent enumeration and API parity for lock-conditioned formal uncertainty."""
from __future__ import annotations

from itertools import product
from random import Random

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from research.score_ingestion.identifiability import count_compositions
from research.score_ingestion.locked_identifiability_v10 import (
    analyze_locked_formal_paths, summarize_lock_trace_ambiguity,
)


def enumerate_paths(n, k, m, locks):
    """Independent brute-force integer compositions, no DP or V10 internals."""
    found=[]
    for parts in product(range(1,m+1),repeat=k):
        if sum(parts)!=n:
            continue
        endpoints=[];t=0
        for p in parts:
            t+=p;endpoints.append(t)
        starts=[0]+endpoints[:-1]
        if all(starts[j]<=i<endpoints[j] for i,j in locks):
            found.append(tuple(starts))
    return found


def test_exact_brute_force_count_and_start_ranges():
    random=Random(130719)
    for n in range(1,10):
        for k in range(1,n+1):
            for m in range(1,5):
                trials=[()]
                for _ in range(5):
                    indexes=random.sample(range(n),k=random.randrange(min(n,4)+1))
                    trials.append(tuple((event,random.randrange(k)) for event in indexes))
                for locks in trials:
                    got=analyze_locked_formal_paths(n,k,m,locks)
                    explicit=enumerate_paths(n,k,m,locks)
                    assert got.exact_equal_cost_paths==len(explicit),(n,k,m,locks)
                    if explicit:
                        expected=tuple((min(seq[j] for seq in explicit), max(seq[j] for seq in explicit)) for j in range(k))
                        assert got.feasible_start_ranges==expected,(n,k,m,locks)
                        assert got.forced_syllable_starts+got.ambiguous_syllable_starts==k
                    else:
                        assert got.feasible_start_ranges==()


def test_unlocked_agrees_with_independent_v8_composition_counter():
    for n in range(1,40):
        for k in range(1,n+1):
            for m in (1,2,3,8):
                count=analyze_locked_formal_paths(n,k,m).exact_equal_cost_paths
                assert count==count_compositions(n,k,m)


def test_lock_monotonicity_and_restoration():
    initial=analyze_locked_formal_paths(8,4,3)
    first=analyze_locked_formal_paths(8,4,3,((3,1),))
    two=analyze_locked_formal_paths(8,4,3,((3,1),(5,2)))
    assert 0 < two.exact_equal_cost_paths <= first.exact_equal_cost_paths <= initial.exact_equal_cost_paths
    assert initial.exact_equal_cost_paths==analyze_locked_formal_paths(8,4,3,()).exact_equal_cost_paths


def test_infeasible_and_unique_cases():
    assert analyze_locked_formal_paths(4,4,3).exact_equal_cost_paths==1
    assert analyze_locked_formal_paths(4,3,1).exact_equal_cost_paths==0
    assert analyze_locked_formal_paths(5,3,3,((0,1),)).exact_equal_cost_paths==0
    assert analyze_locked_formal_paths(5,3,3,((0,0),(1,2))).exact_equal_cost_paths==0


def test_invalid_locks_are_fail_closed():
    with pytest.raises(ValueError,match='duplicate'):
        analyze_locked_formal_paths(5,3,3,((1,1),(1,1)))
    with pytest.raises(ValueError,match='outside'):
        analyze_locked_formal_paths(5,3,3,((5,1),))
    with pytest.raises(TypeError):
        analyze_locked_formal_paths(5,3,3,((1,True),))
    with pytest.raises(TypeError):
        analyze_locked_formal_paths(True,3,3)


def make_score(n, with_gold=False):
    chord=''.join('<Chord><durationType>quarter</durationType>'+
                  ('<Lyrics><text>secret gold</text></Lyrics>' if with_gold and i%2==0 else '')+
                  f'<Note><pitch>{60+i%5}</pitch></Note></Chord>' for i in range(n))
    return '<museScore version="3.02"><Score><Division>480</Division><Staff id="1"><Measure>'+chord+'</Measure></Staff></Score></museScore>'


def trace(xml, k, edits):
    return TestClient(app).post('/research/score/formal-lock-trace',json={
        'mscx_xml':xml,'syllable_count':k,'max_events_per_syllable':3,'edits':edits,
    })


def test_api_initial_and_edits_exact_counts_parity():
    edits=[{'locks':[{'normalized_event_index':2,'syllable_index':1}]},
           {'locks':[{'normalized_event_index':2,'syllable_index':1},
                     {'normalized_event_index':3,'syllable_index':2}]},
           {'locks':[{'normalized_event_index':0,'syllable_index':2}]},
           {'locks':[]}]
    response=trace(make_score(6),3,edits)
    assert response.status_code==200,response.text
    x=response.json();all_items=[x['initial']]+x['updates']
    locksets=[(),((2,1),),((2,1),(3,2)),((0,2),),()]
    for row,locks in zip(all_items,locksets):
        truth=enumerate_paths(6,3,3,locks)
        summary=row['formal_identifiability']
        assert int(summary['number_of_equal_cost_optimal_paths'])==len(truth)
        assert summary['unique_formal_path']==(len(truth)==1)
        assert (row['status']=='FEASIBLE')==bool(truth)
        assert summary['user_supplied_lock_count']==len(locks)
        if truth:
            assert row['predicted_original_chord_indices'] in map(list,truth)
        else:
            assert row['predicted_original_chord_indices'] is None


def test_api_labels_in_xml_cannot_affect_counts_or_positions():
    edits=[{'locks':[{'normalized_event_index':2,'syllable_index':1}]}]
    a=trace(make_score(6,True),3,edits)
    b=trace(make_score(6,False),3,edits)
    assert a.status_code==b.status_code==200
    for key in ('initial','updates'):
        assert a.json()[key]==b.json()[key]
    assert 'secret gold' not in a.text
    assert not a.json()['gold_positions_exposed']


def test_api_ranges_are_mapped_to_original_chord_indices():
    summary=summarize_lock_trace_ambiguity(5,3,3,((2,1),),[[0],[1,2],[3],[4],[5,6]])
    expected=analyze_locked_formal_paths(5,3,3,((2,1),))
    starts=[0,1,3,4,5]
    assert summary['first_ten_possible_original_chord_index_ranges']==[
        [starts[a],starts[b]] for a,b in expected.feasible_start_ranges
    ]


def test_api_rejects_duplicate_locks():
    a=trace(make_score(4),2,[{'locks':[{'normalized_event_index':1,'syllable_index':0},
                                      {'normalized_event_index':1,'syllable_index':1}]}])
    assert a.status_code==422


def test_api_tie_group_count_uses_normalized_events_and_source_mapping():
    tie_start='<Spanner type="Tie"><next><location/></next></Spanner>'
    tie_end='<Spanner type="Tie"><prev><location/></prev></Spanner>'
    c=lambda pitch,extra='': '<Chord><durationType>quarter</durationType><Note>'+extra+f'<pitch>{pitch}</pitch></Note></Chord>'
    score='<museScore version="3.02"><Score><Division>480</Division><Staff id="1"><Measure>'+''.join((
        c(60,tie_start),c(60,tie_end),c(62),c(63),c(64)
    ))+'</Measure></Staff></Score></museScore>'
    response=trace(score,2,[{'locks':[{'normalized_event_index':1,'syllable_index':1}]}])
    assert response.status_code==200,response.text
    body=response.json()
    assert body['original_chords']==5
    assert body['normalized_note_events']==4
    assert int(body['initial']['formal_identifiability']['number_of_equal_cost_optimal_paths'])==3
    # Count in normalized space; map possible onsets through [0,2,3,4].
    expected=summarize_lock_trace_ambiguity(4,2,3,((1,1),),[[0,1],[2],[3],[4]])
    assert body['updates'][0]['formal_identifiability']==expected
    assert body['updates'][0]['predicted_original_chord_indices'][0]==0


def test_api_unique_path_is_not_claimed_as_music_confidence():
    x=trace(make_score(3),3,[{'locks':[]}])
    assert x.status_code==200,x.text
    report=x.json()['initial']['formal_identifiability']
    assert report['unique_formal_path']
    assert report['number_of_equal_cost_optimal_paths']=='1'
    assert report['number_of_syllable_starts_with_multiple_possible_positions']==0
    assert 'not probabilities' in report['evidence_limitation']
    assert x.json()['real_alignment_accuracy_evaluated'] is False
