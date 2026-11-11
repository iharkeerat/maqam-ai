"""Pure-formal API lock traces, no musical performance inference."""
from fastapi.testclient import TestClient

from backend.main import app

client=TestClient(app)


def chord(pitch, lyric=None, suffix=''):
    s=f'<Lyrics><text>{lyric}</text></Lyrics>' if lyric is not None else ''
    return f'<Chord><durationType>quarter</durationType>{s}<Note>{suffix}<pitch>{pitch}</pitch></Note></Chord>'


def make_score(*events):
    return ('<museScore version="3.02"><Score><Division>480</Division>'
            '<Staff id="1"><Measure>'+''.join(events)+
            '</Measure></Staff></Score></museScore>')


def trace(xml,k,edits=None,maxspan=3):
    return client.post('/research/score/formal-lock-trace',json={
        'mscx_xml':xml,'syllable_count':k,
        'max_events_per_syllable':maxspan,'edits':edits or []})


def test_api_initial_equals_v8_preview_and_no_gold():
    xml=make_score(chord(60,'secret'),chord(61),chord(62,'private'),chord(63),chord(64))
    a=trace(xml,3)
    v8=client.post('/research/score/formal-preview',json={
        'mscx_xml':xml,'syllable_count':3,'max_events_per_syllable':3})
    assert a.status_code==v8.status_code==200
    assert a.json()['initial']['predicted_original_chord_indices']==v8.json()['predicted_original_chord_indices']
    assert a.json()['initial']['formal_cost']==v8.json()['formal_cost']
    assert 'secret' not in a.text and 'private' not in a.text
    assert not a.json()['gold_positions_exposed']


def test_api_gold_independence():
    a=make_score(chord(60,'Secretly'),chord(61),chord(62,'ThisIsGold'))
    b=make_score(chord(60),chord(61),chord(62))
    edit=[[{'normalized_event_index':1,'syllable_index':0}]]
    e=[{'locks':v} for v in edit]
    x=trace(a,2,e).json(); y=trace(b,2,e).json()
    assert x['initial']==y['initial']
    assert x['updates']==y['updates']


def test_api_edits_and_reversion_match_native_unlocked():
    xml=make_score(*(chord(i+60) for i in range(6)))
    edits=[{'locks':[{'normalized_event_index':0,'syllable_index':1}]},
           {'locks':[{'normalized_event_index':0,'syllable_index':0}]},
           {'locks':[]}]
    r=trace(xml,3,edits)
    assert r.status_code==200,r.text
    d=r.json()
    assert d['updates'][0]['status']=='INFEASIBLE'
    assert d['updates'][0]['predicted_original_chord_indices'] is None
    assert d['updates'][1]['status']=='FEASIBLE'
    assert d['updates'][2]['predicted_original_chord_indices']==d['initial']['predicted_original_chord_indices']
    assert all(item['recomputed_states']>=0 for item in d['updates'])


def test_api_invalid_lock_indices_and_duplicate_rejected():
    xml=make_score(*(chord(i+60) for i in range(4)))
    for locks in (
            [{'normalized_event_index':99,'syllable_index':0}],
            [{'normalized_event_index':0,'syllable_index':99}],
            [{'normalized_event_index':1,'syllable_index':0},
             {'normalized_event_index':1,'syllable_index':1}],
    ):
        r=trace(xml,2,[{'locks':locks}])
        assert r.status_code==422,r.text


def test_api_tie_collapse_does_not_expose_gold():
    tie_start='<Spanner type="Tie"><next><location/></next></Spanner>'
    tie_end='<Spanner type="Tie"><prev><location/></prev></Spanner>'
    xml=make_score(chord(60,'gold',tie_start),chord(60,None,tie_end),chord(62))
    r=trace(xml,1)
    assert r.status_code==200,r.text
    d=r.json()
    assert d['original_chords']==3
    assert d['normalized_note_events']==2
    assert d['initial']['predicted_original_chord_indices']==[0]
    assert not d['gold_positions_exposed']


def test_api_request_bounds():
    xml=make_score(chord(60))
    r=trace(xml,1,edits=[{'locks':[]}]*21)
    assert r.status_code==422,r.text
