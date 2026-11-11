"""Constructed software tests, NOT singing-alignment performance evidence."""
from itertools import combinations
from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from research.score_ingestion.identifiability import (
    count_compositions, analyze_untargeted_score,
    summarize_for_public_api, formal_spans_crossing_rests,
)
from research.score_ingestion.notation_adapter import extract_score
from research.score_ingestion.integration import sanitized_projection
from research.score_ingestion.cli import generate

client = TestClient(app)


def note(pitch=60, text=None):
    lyric = f'<Lyrics><text>{text}</text></Lyrics>' if text is not None else ''
    return f'<Chord><durationType>quarter</durationType>{lyric}<Note><pitch>{pitch}</pitch></Note></Chord>'


def score(*elements):
    return ('<museScore version="3.02"><Score><Division>480</Division>'
            '<Staff id="1"><Measure>' + ''.join(elements) +
            '</Measure></Staff></Score></museScore>')


def api(xml, k, span=3):
    return client.post('/research/score/formal-preview',json={
        'mscx_xml':xml,'syllable_count':k,'max_events_per_syllable':span})


def valid_paths(n,k,m):
    for cuts in combinations(range(1,n),k-1):
        starts=(0,)+cuts
        ends=cuts+(n,)
        if all(end-start<=m for start,end in zip(starts,ends)):
            yield starts


def test_01_exact_count_agrees_with_brute_force_on_small_space():
    for n in range(1,11):
        for k in range(1,n+1):
            for m in range(1,6):
                assert count_compositions(n,k,m)==sum(1 for _ in valid_paths(n,k,m))


def test_02_all_possible_start_ranges_match_exhaustive_paths():
    for n in range(1,9):
        for k in range(1,n+1):
            for m in range(1,5):
                paths=list(valid_paths(n,k,m))
                report=analyze_untargeted_score(n,k,m)
                if not paths:
                    assert not report.feasible
                    continue
                assert report.feasible
                for j in range(k):
                    assert report.start_event_ranges[j]==(min(t[j] for t in paths),max(t[j] for t in paths))


def test_03_known_counts_and_constant_cost():
    report=analyze_untargeted_score(5,3,3)
    assert report.exact_equal_cost_paths==6
    assert report.formal_min_cost==2
    assert report.nonunique_start_count==2
    assert report.start_event_ranges==((0,0),(1,3),(2,4))


def test_04_unique_path_when_number_of_events_equals_syllables():
    r=analyze_untargeted_score(8,8,3)
    assert r.exact_equal_cost_paths==1 and r.nonunique_start_count==0
    assert all(x==(i,i) for i,x in enumerate(r.start_event_ranges))


def test_05_unique_maximum_span_packing():
    r=analyze_untargeted_score(9,3,3)
    assert r.exact_equal_cost_paths==1
    assert r.start_event_ranges==((0,0),(3,3),(6,6))


def test_06_infeasible_with_restricted_span():
    r=analyze_untargeted_score(9,2,3)
    assert r.exact_equal_cost_paths==0 and not r.feasible
    assert r.start_event_ranges==()


def test_07_large_valid_path_count_is_exact_integer_string():
    p=summarize_for_public_api(350,175,3,[[i] for i in range(350)])
    assert len(p['number_of_equal_cost_optimal_paths'])>30
    assert int(p['number_of_equal_cost_optimal_paths'])>1
    assert p['all_feasible_paths_have_same_cost']
    assert p['formal_minimum_cost']==175


def test_08_reject_incorrect_or_beyond_350_count_inputs():
    for v in [True,3.0,'3']:
        with pytest.raises(TypeError):count_compositions(v,2,3)
    with pytest.raises(ValueError):count_compositions(351,2,3)
    with pytest.raises(ValueError):count_compositions(1,1,33)


def test_09_source_chord_ranges_respect_collapsed_tie_positions():
    val=summarize_for_public_api(3,2,3,[[0,1],[2],[3,4]])
    assert val['number_of_equal_cost_optimal_paths']=='2'
    assert val['first_ten_possible_original_chord_index_ranges']==[[0,0],[2,3]]


def test_10_api_reports_actual_nonuniqueness_without_gold():
    xml=score(note(60,'SECRET_ANSWER'),note(62,'PRIVATE'),note(64),note(65),note(67))
    r=api(xml,3)
    assert r.status_code==200,r.text
    d=r.json()
    assert d['formal_identifiability']['number_of_equal_cost_optimal_paths']=='6'
    assert d['formal_identifiability']['formal_minimum_cost']==2
    assert not d['formal_identifiability']['unique_formal_path']
    assert d['formal_cost']==2
    assert not d['gold_annotation_positions_exposed']
    assert 'SECRET_ANSWER' not in r.text and 'PRIVATE' not in r.text


def test_11_api_is_independent_of_score_gold_fields():
    a=api(score(note(60,'SECRET'),note(62,'SECRET2'),note(64)),2).json()
    b=api(score(note(60),note(62),note(64)),2).json()
    for field in ('formal_identifiability','predicted_original_chord_indices','formal_cost'):
        assert a[field]==b[field]


def test_12_api_handles_infeasible_without_fake_prediction():
    r=api(score(*(note(60+i) for i in range(7))),2,span=3)
    assert r.status_code==200,r.text
    d=r.json()
    assert d['predicted_original_chord_indices'] is None
    assert d['formal_identifiability']['number_of_equal_cost_optimal_paths']=='0'
    assert not d['formal_identifiability']['all_feasible_paths_have_same_cost']


def test_13_silent_gap_preserved_without_hard_rest_constraint():
    xml=score(note(60),'<Rest><durationType>quarter</durationType></Rest>',note(62))
    raw=extract_score(xml.encode())
    public=sanitized_projection(raw)
    assert public['rest_gap_before_normalized_event_indices']==[1]
    r=api(xml,1)
    assert r.status_code==200,r.text
    d=r.json()
    assert d['note_event_rests_removed']==1
    assert d['predicted_syllable_indices_crossing_score_rests']==[0]
    assert d['formal_identifiability']['unique_formal_path']


def test_14_rest_before_first_onset_not_a_span_crossing():
    xml=score('<Rest><durationType>quarter</durationType></Rest>',note(60),note(62))
    d=api(xml,1).json()
    assert d['rest_gaps_before_normalized_event_indices']==[0]
    assert d['predicted_syllable_indices_crossing_score_rests']==[]


def test_15_rest_crossing_witness_on_multiple_syllables():
    assert formal_spans_crossing_rests((2,5),[1,2,4])==[0,1]
    assert formal_spans_crossing_rests((1,3),[1])==[]


def test_16_api_tie_collapse_changes_number_of_options():
    xml=score('<Chord><durationType>quarter</durationType><Note><pitch>60</pitch>'
              '<Spanner type="Tie"><next/></Spanner></Note></Chord>',
              '<Chord><durationType>quarter</durationType><Note><pitch>60</pitch>'
              '<Spanner type="Tie"><prev/></Spanner></Note></Chord>',
              note(62),note(64))
    d=api(xml,2).json()
    assert d['normalized_note_events']==3
    assert d['formal_identifiability']['number_of_equal_cost_optimal_paths']=='2'
    assert d['formal_identifiability']['first_ten_possible_original_chord_index_ranges']==[[0,0],[2,3]]


def test_17_cli_separate_public_private_and_warning(tmp_path):
    src=tmp_path/'score.mscx'
    src.write_text(score(note(60,'SENSITIVE-LYRIC'),note(62),note(64)),encoding='utf-8')
    pub,pri=tmp_path/'solver_only',tmp_path/'private_gold'
    out=generate(src,pub,pri,syllables=2)
    assert out['formal_identifiability']['number_of_equal_cost_optimal_paths']=='2'
    public_json=(pub/'FORMAL_OUTPUT.json').read_text()
    assert 'SENSITIVE-LYRIC' not in public_json
    assert 'original_gold_chord_indices' not in public_json
    assert json.loads((pri/'HELD_OUT_SCORE_REFERENCE.json').read_text())['annotated_syllables']==1


def test_18_api_inference_remains_formal_not_music_accuracy():
    d=api(score(note(60),note(62),note(64)),2).json()
    assert d['cost_is_not_singing_accuracy']
    assert not d['audio_or_linguistic_accuracy_evaluated']
    assert 'not confidence' in d['formal_identifiability']['evidence_limitation']


def test_19_uninformative_rhythm_does_not_suddenly_become_unique():
    d=api(score(note(60),note(62),note(64),note(65)),2,span=3).json()
    assert d['formal_identifiability']['number_of_equal_cost_optimal_paths']=='3'
    assert d['formal_identifiability']['number_of_syllable_starts_with_multiple_possible_positions']==1


def test_20_strict_no_ghost_lyrics_in_identifiability_module():
    src=Path(__file__).parents[1]/'research'/'score_ingestion'/'identifiability.py'
    text=src.read_text()
    assert 'lyric_anchor_indices' not in text
    assert 'held_out_reference' not in text
