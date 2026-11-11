"""Source-independent software tests: constructed XML is NOT musical validation."""
from fractions import Fraction
import json
from pathlib import Path

import pytest

from research.score_ingestion.notation_adapter import UnsupportedNotation, extract_score
from research.score_ingestion.integration import sanitized_projection, held_out_reference, formal_case
from research.score_ingestion.cli import generate
from research.pronunciation_rhythm.core import composed_dp, verify_solution


def score(content, div=480):
    return (f'<museScore version="3.02"><Score><Division>{div}</Division>'
            '<Staff id="1"><Measure>'+content+'</Measure></Staff></Score></museScore>').encode()

def note(d='quarter', *, pitch=60, text=None, start=False, end=False, slur=False):
    lyrics='' if text is None else f'<Lyrics><text>{text}</text></Lyrics>'
    forward='<Spanner type="Tie"><next/></Spanner>' if start else ''
    backward='<Spanner type="Tie"><prev/></Spanner>' if end else ''
    sl='<Spanner type="Slur"><prev/></Spanner>' if slur else ''
    return f'<Chord><durationType>{d}</durationType>{lyrics}{sl}<Note><pitch>{pitch}</pitch>{forward}{backward}</Note></Chord>'

def test_exact_tie_collapse_and_normalized_reference():
    a=extract_score(score(note(start=True,text='a')+note(end=True)+note(pitch=62,text='b')))
    p=sanitized_projection(a)
    assert p['event_durations']==[960,480]
    assert p['normalized_groups']==[[0,1],[2]]
    assert p['original_chord_count']==3
    assert 'lyric_anchor_indices' not in p
    assert 'lyric_anchor_count' not in p
    g=held_out_reference(a)
    assert g['original_gold_chord_indices']==[0,2]
    assert g['normalized_gold_group_indices']==[0,1]
    case=formal_case(p,2)
    result=composed_dp(case)
    assert result.solution and verify_solution(case,result.solution)
    assert result.solution.ends==(1,2)


def test_three_note_tie_chain():
    a=extract_score(score(note(start=True,text='a')+note(end=True,start=True)+note(end=True)+note(pitch=62,text='b')))
    p=sanitized_projection(a)
    assert p['normalized_groups']==[[0,1,2],[3]]
    assert p['event_durations']==[1440,480]


def test_slur_ending_with_new_lyric_not_excluded():
    a=extract_score(score(note(text='a')+note(pitch=62,text='b',slur=True)))
    assert a['chords'][1]['slur_end']
    assert sanitized_projection(a)['normalized_groups']==[[0],[1]]


def test_orphan_backwards_tie_rejected():
    a=extract_score(score(note(end=True)))
    with pytest.raises(UnsupportedNotation,match='unpaired'):sanitized_projection(a)


def test_orphan_forward_tie_rejected():
    a=extract_score(score(note(start=True)))
    with pytest.raises(UnsupportedNotation,match='trailing'):sanitized_projection(a)


def test_tie_wrong_pitch_rejected():
    a=extract_score(score(note(start=True)+note(end=True,pitch=64)))
    with pytest.raises(UnsupportedNotation,match='pitch changes'):sanitized_projection(a)


def test_tie_across_rest_rejected():
    xml=score(note(start=True)+'<Rest><durationType>quarter</durationType></Rest>'+note(end=True))
    a=extract_score(xml)
    with pytest.raises(UnsupportedNotation,match='intervening rest'):sanitized_projection(a)


def test_polyphonic_chord_rejected_in_formal_bridge():
    xml=score('<Chord><durationType>quarter</durationType><Note><pitch>60</pitch></Note><Note><pitch>64</pitch></Note></Chord>')
    with pytest.raises(UnsupportedNotation,match='single-pitch'):sanitized_projection(extract_score(xml))


def test_tuplet_fraction_exact():
    xml=score('<voice><Tuplet><normalNotes>2</normalNotes><actualNotes>3</actualNotes><baseNote>eighth</baseNote></Tuplet>'+note('eighth',text='a')+note('eighth',text='b')+note('eighth',text='c')+'<endTuplet/></voice>')
    a=extract_score(xml)
    assert a['chords'][0]['duration_ticks']=='160'
    assert sanitized_projection(a)['event_durations']==[160,160,160]


def test_pure_rhythm_independent_of_reference_lyrics():
    a=extract_score(score(note(text='alpha')+note(pitch=61,text='beta')))
    b=extract_score(score(note()+note(pitch=61)))
    aa=sanitized_projection(a);bb=sanitized_projection(b)
    aa.pop('source_sha256');bb.pop('source_sha256')
    assert aa==bb


def test_external_syllable_count_not_inferred_from_gold():
    raw=extract_score(score(note(text='a')+note(pitch=61)))
    pub=sanitized_projection(raw)
    assert formal_case(pub,2).candidates[0].syllables==('token_0','token_1')
    with pytest.raises(ValueError):formal_case(pub,3)


def test_explicit_public_private_separation(tmp_path):
    src=tmp_path/'src.mscx';src.write_bytes(score(note(start=True,text='a')+note(end=True)+note(pitch=62,text='b')))
    public=tmp_path/'public';private=tmp_path/'private'
    result=generate(src,public,private,syllables=2)
    assert result['solver']['status']=='FEASIBLE'
    assert {p.name for p in public.iterdir()}=={'SOLVER_INPUT.json','FORMAL_SETUP.json','FORMAL_OUTPUT.json'}
    assert {p.name for p in private.iterdir()}=={'HELD_OUT_SCORE_REFERENCE.json','INGESTION_AUDIT.json'}
    assert json.loads((private/'HELD_OUT_SCORE_REFERENCE.json').read_text())['original_gold_chord_indices']==[0,2]
    for path in public.iterdir():
        txt=path.read_text()
        assert 'original_gold_chord_indices' not in txt
        assert 'lyric_anchor_indices' not in txt
    assert json.loads((public/'FORMAL_OUTPUT.json').read_text())['real_accuracy_scored'] is False
    assert src.read_bytes().startswith(b'<museScore')


def test_no_output_on_bad_gold_independent_input(tmp_path):
    src=tmp_path/'src.mscx';src.write_bytes(score(note(text='a')))
    with pytest.raises(ValueError):generate(src,tmp_path/'public',tmp_path/'private',syllables=2)
    assert not (tmp_path/'public').exists()


def test_no_nested_public_private_or_overwrites(tmp_path):
    src=tmp_path/'src.mscx';src.write_bytes(score(note(text='a')))
    with pytest.raises(ValueError):generate(src,tmp_path/'pub',tmp_path/'pub'/'private',syllables=1)
    p=tmp_path/'pub';p.mkdir()
    with pytest.raises(FileExistsError):generate(src,p,tmp_path/'private',syllables=1)


def test_original_v6_direct_measure_syntax_supported():
    xml=score('<Rest><durationType>measure</durationType><duration z="3" n="4"/></Rest>'+note('quarter',text='a'))
    a=extract_score(xml)
    assert a['chords'][0]['onset_ticks']=='1440'
    p=sanitized_projection(a)
    assert p['original_written_onsets']==['1440']
    assert p['event_durations']==[480]
