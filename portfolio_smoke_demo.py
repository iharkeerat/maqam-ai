"""Reproducible in-process demonstration of EXISTING MAQAM formal API.

The score below is CONSTRUCTED; results demonstrate software behaviour,
not alignment accuracy on sung audio or authentic musical ground truth.
"""
from __future__ import annotations
import json
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def score(with_private_lyrics: bool) -> str:
    label_a = '<Lyrics><text>not-public-A</text></Lyrics>' if with_private_lyrics else ''
    label_b = '<Lyrics><text>not-public-B</text></Lyrics>' if with_private_lyrics else ''
    return ('<museScore version="3.02"><Score><Division>480</Division>'
            '<Staff id="1"><Measure>'
            '<Chord><durationType>quarter</durationType>' + label_a +
            '<Note><pitch>60</pitch><Spanner type="Tie"><next/></Spanner></Note></Chord>'
            '<Chord><durationType>quarter</durationType><Note><pitch>60</pitch>'
            '<Spanner type="Tie"><prev/></Spanner></Note></Chord>'
            '<Chord><durationType>quarter</durationType>' + label_b +
            '<Note><pitch>62</pitch></Note></Chord>'
            '</Measure></Staff></Score></museScore>')

def run() -> dict:
    health = client.get('/health')
    assert health.status_code == 200
    a = client.post('/research/score/formal-preview', json={'mscx_xml': score(True), 'syllable_count': 2})
    b = client.post('/research/score/formal-preview', json={'mscx_xml': score(False), 'syllable_count': 2})
    assert a.status_code == b.status_code == 200, (a.text, b.text)
    assert a.json()['predicted_original_chord_indices'] == [0, 2]
    assert a.json()['predicted_original_chord_indices'] == b.json()['predicted_original_chord_indices']
    assert a.json()['normalized_note_events'] == 2
    assert not a.json()['gold_annotation_positions_exposed']
    assert 'not-public' not in a.text
    unsafe = client.post('/research/score/formal-preview', json={'mscx_xml': '<!DOCTYPE x><museScore/>', 'syllable_count': 2})
    assert unsafe.status_code == 422
    return {
        'demo_type': 'constructed_synthetic_score_formal_api_smoke',
        'api_health': health.json(),
        'original_notated_chords': a.json()['original_chords'],
        'normalized_events_after_tie_collapse': a.json()['normalized_note_events'],
        'formal_chord_start_indices': a.json()['predicted_original_chord_indices'],
        'identical_result_if_lyrics_removed': a.json()['predicted_original_chord_indices'] == b.json()['predicted_original_chord_indices'],
        'private_lyric_text_absent_from_response': 'not-public' not in a.text,
        'unsupported_dtd_rejected_http': unsafe.status_code,
        'formal_identifiability': a.json()['formal_identifiability'],
        'real_world_alignment_accuracy_evaluated': False,
        'note': 'This shows parser, formal DP, and safe API behaviour; NOT correctness against real music.'
    }

if __name__ == '__main__':
    print(json.dumps(run(), indent=2, ensure_ascii=False))
