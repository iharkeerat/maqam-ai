import json
from fastapi.testclient import TestClient
from backend.main import app

client=TestClient(app)


def sample(gold=True):
    first='<Lyrics><text>privateAnswerA</text></Lyrics>' if gold else ''
    second='<Lyrics><text>privateAnswerB</text></Lyrics>' if gold else ''
    return ('<museScore><Score><Staff><Measure>'
            '<Chord><durationType>quarter</durationType>'+first+
            '<Note><pitch>60</pitch><Spanner type="Tie"><next/></Spanner></Note></Chord>'
            '<Chord><durationType>quarter</durationType><Note><pitch>60</pitch>'
            '<Spanner type="Tie"><prev/></Spanner></Note></Chord>'
            '<Chord><durationType>quarter</durationType>'+second+
            '<Note><pitch>62</pitch></Note></Chord>'
            '</Measure></Staff></Score></museScore>')


def test_live_api_score_gold_not_leaked_and_inference_independent():
    a=client.post('/research/score/formal-preview',json={'mscx_xml':sample(True),'syllable_count':2})
    b=client.post('/research/score/formal-preview',json={'mscx_xml':sample(False),'syllable_count':2})
    assert a.status_code==200,(a.status_code,a.text)
    assert b.status_code==200
    for d in (a.json(),b.json()):
        assert d['predicted_original_chord_indices']==[0,2]
        assert d['normalized_note_events']==2
        assert not d['audio_or_linguistic_accuracy_evaluated']
        assert d['gold_annotation_positions_exposed'] is False
    assert a.json()['predicted_original_chord_indices']==b.json()['predicted_original_chord_indices']
    assert 'privateAnswerA' not in a.text and 'privateAnswerB' not in a.text


def test_bad_syllable_count_is_422_and_no_private_output():
    r=client.post('/research/score/formal-preview',json={'mscx_xml':sample(),'syllable_count':4})
    assert r.status_code==422
    assert 'privateAnswer' not in r.text


def test_unsupported_score_is_422():
    xml='<museScore><Score><Staff><Measure><voice><Tuplet/></voice></Measure></Staff></Score></museScore>'
    r=client.post('/research/score/formal-preview',json={'mscx_xml':xml,'syllable_count':1})
    assert r.status_code==422


def test_dtd_rejected():
    xml='<!DOCTYPE x [<!ENTITY secret "expansion">]>'+sample()
    r=client.post('/research/score/formal-preview',json={'mscx_xml':xml,'syllable_count':2})
    assert r.status_code==422


def test_malformed_xml_is_422():
    r=client.post('/research/score/formal-preview',json={'mscx_xml':'<museScore><bad xml','syllable_count':2})
    assert r.status_code==422
