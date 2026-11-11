"""API regression: unsafe time structures must return HTTP 422, not a result."""
from fastapi.testclient import TestClient
from backend.main import app

client=TestClient(app)
CHORD='<Chord><durationType>quarter</durationType><Note><pitch>60</pitch></Note></Chord>'

def score(*measures):
    return ('<museScore><Score><Division>480</Division><Staff id="1">'
            + ''.join('<Measure>'+m+'</Measure>' for m in measures)
            + '</Staff></Score></museScore>')

def call(xml):
    return client.post('/research/score/formal-preview',
                       json={'mscx_xml':xml,'syllable_count':2,
                             'max_events_per_syllable':3})

def test_unsafe_empty_intermediate_measure_is_422():
    result=call(score(CHORD,'',CHORD))
    assert result.status_code==422, (result.status_code,result.text)
    assert 'no timed chord/rest' in result.text

def test_outside_wrapped_voice_tick_is_422():
    result=call(score('<tick>0</tick><voice>'+CHORD+'</voice>',CHORD))
    assert result.status_code==422, (result.status_code,result.text)
    assert 'outside-voice timing' in result.text

def test_valid_direct_and_wrapped_produces_formal_only_result():
    result=call(score(CHORD,'<voice>'+CHORD+'</voice>'))
    assert result.status_code==200,(result.status_code,result.text)
    output=result.json()
    assert output['status']=='FEASIBLE'
    assert output['predicted_original_chord_indices']==[0,1]
    assert output['gold_annotation_positions_exposed'] is False
    assert output['audio_or_linguistic_accuracy_evaluated'] is False

def test_timing_safety_independent_of_lyric_gold():
    marked=CHORD.replace('<Note>','<Lyrics><text>privateReference</text></Lyrics><Note>')
    result=call(score(marked,'<voice>'+CHORD+'</voice>'))
    control=call(score(CHORD,'<voice>'+CHORD+'</voice>'))
    assert result.status_code==200 and control.status_code==200
    assert result.json()['predicted_original_chord_indices']==control.json()['predicted_original_chord_indices']
    assert 'privateReference' not in result.text
