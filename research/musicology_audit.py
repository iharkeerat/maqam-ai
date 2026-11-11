"""Independent *encoded-rule* musicology audit for SURF Upgrade 05.

This audit deliberately never certifies that a composition is authentic, beautiful,
performed correctly, or musically acceptable. It checks inspectable encoded
constraints against a declared seed inventory and produces evidence-linked traces.
A missing rule is 'unassessed', never a pass. Beat indices are zero-based.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'web' / 'app' / 'data'
SWARS = {'S', 'r', 'R', 'g', 'G', 'm', 'M', 'P', 'd', 'D', 'n', 'N'}
ORNAMENTS = {'none', 'meend', 'murki', 'khatka', 'andolan', 'gamak'}
SAPTAKS = {'mandra', 'madhya', 'taar'}


def canonical_json_sha256(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def load_inventory(root: Path = ROOT) -> tuple[dict[str, dict], dict[str, dict]]:
    base = root / 'web' / 'app' / 'data'
    raags = json.loads((base / 'raag_seed.json').read_text(encoding='utf-8'))
    taals = json.loads((base / 'taals.json').read_text(encoding='utf-8'))
    return ({r['id']: r for r in raags if r.get('generationReady') is True},
            {t['id']: t for t in taals if t.get('generationReady') is True})


def _trace(rule: str, outcome: str, beats: list[int], evidence: str, scope: str = 'encoded-rule') -> dict:
    return {'rule': rule, 'outcome': outcome, 'affected_beat_indices': beats, 'evidence': evidence, 'scope': scope}


def audit_phrase(sample: dict[str, Any], *, raags: dict[str, dict] | None = None,
                 taals: dict[str, dict] | None = None) -> dict[str, Any]:
    """Audit a phrase: {'raag_id','taal_id','notation':[{'swar',...}, ...]}.

    Raises ValueError for malformed/unrecognized/unready inventory or note data.
    Encoded failures are returned as diagnostics, not exceptions.
    """
    if raags is None or taals is None:
        raags, taals = load_inventory()
    if not isinstance(sample, dict):
        raise ValueError('Sample must be an object')
    rid, tid = sample.get('raag_id'), sample.get('taal_id')
    if not isinstance(rid, str) or rid not in raags:
        raise ValueError('Unknown or non-generation-ready Raag id')
    if not isinstance(tid, str) or tid not in taals:
        raise ValueError('Unknown or non-generation-ready Taal id')
    r, t = raags[rid], taals[tid]
    notes = sample.get('notation')
    if not isinstance(notes, list) or not notes or len(notes) > 256:
        raise ValueError('Notation must have 1–256 events')
    for i, note in enumerate(notes):
        if not isinstance(note, dict):
            raise ValueError(f'Beat {i}: event must be an object')
        if not isinstance(note.get('swar', ''), (str, type(None))) or (note.get('swar') not in SWARS and note.get('swar') not in {'', None}):
            raise ValueError(f'Beat {i}: unknown Swar token')
        if not isinstance(note.get('saptak', 'madhya'), str) or note.get('saptak', 'madhya') not in SAPTAKS:
            raise ValueError(f'Beat {i}: unknown Saptak')
        if not isinstance(note.get('ornament', 'none'), str) or note.get('ornament', 'none') not in ORNAMENTS:
            raise ValueError(f'Beat {i}: unknown ornament')
        if not isinstance(note.get('kan', ''), str) or note.get('kan', '') not in SWARS | {''}:
            raise ValueError(f'Beat {i}: unknown Kan Swar')
        if not isinstance(note.get('bol', ''), str):
            raise ValueError(f'Beat {i}: bol must be text')

    diagnostics: list[dict] = []
    used = [(idx, n['swar']) for idx, n in enumerate(notes) if n.get('swar')]
    allowed = set(r.get('allowedSwars', []))
    forbidden = set(r.get('forbiddenSwars', []))
    # Unknown-vs-forbidden distinction: no implicit pass for a note outside both sets.
    unsupported = [idx for idx, pitch in used if pitch not in allowed]
    explicitly_forbidden = [idx for idx, pitch in used if pitch in forbidden]
    diagnostics.append(_trace('raag-swar-inventory', 'fail' if unsupported else 'pass', unsupported,
                              f'{len(unsupported)} notes outside working allowed Swars; '
                              f'{len(explicitly_forbidden)} explicitly forbidden; source={r.get("verification", "unverified")}.'))
    if not used:
        diagnostics.append(_trace('melodic-content', 'unassessed', [], 'No filled notes: no melodic suitability conclusion.'))
    else:
        diagnostics.append(_trace('melodic-content', 'observed', [idx for idx, _ in used],
                                  f'{len(used)} filled note events (not a certification of Raag identity).'))

    division = t.get('divisions', [])
    beats = t.get('beats')
    valid_cycle = isinstance(beats, int) and beats > 0 and len(notes) == beats and isinstance(division, list) and all(isinstance(x, int) and x > 0 for x in division) and sum(division) == beats
    diagnostics.append(_trace('taal-cycle-and-vibhag', 'pass' if valid_cycle else 'fail', [],
                              f'events={len(notes)}, cycle={beats}, divisions={division}'))
    marks = t.get('marks', [])
    diagnostics.append(_trace('taal-mark-structure', 'pass' if isinstance(marks, list) and len(marks) == len(division) else 'fail', [],
                              f'{len(marks) if isinstance(marks, list) else "invalid"} marks for {len(division)} divisions'))

    kan_problem = [i for i, n in enumerate(notes) if n.get('kan') and n['kan'] not in allowed]
    diagnostics.append(_trace('kan-working-profile', 'fail' if kan_problem else 'pass', kan_problem,
                              'Kan check tests encoded working swar inventory only.'))
    andolan = [i for i, n in enumerate(notes) if n.get('ornament') == 'andolan']
    unsupported_andolan = [i for i in andolan if notes[i].get('swar') not in r.get('andolan', {})]
    diagnostics.append(_trace('andolan-encoded-rule', 'unassessed' if not andolan else 'warn' if unsupported_andolan else 'pass',
                              unsupported_andolan, 'No encoding is not evidence the ornament is forbidden; manual musical review required.'))
    meend_terminal = [i for i, n in enumerate(notes) if n.get('ornament') == 'meend' and i == len(notes) - 1]
    diagnostics.append(_trace('meend-target', 'warn' if meend_terminal else 'pass', meend_terminal,
                              'Terminal meend lacks an explicit subsequent event in this notation.'))

    sequence = [s for _, s in used]
    signatures = [s for s in r.get('signaturePhrases', []) if isinstance(s, list) and len(s) >= 3]
    present = []
    for phrase in signatures:
        for i in range(len(sequence) - len(phrase) + 1):
            if sequence[i:i + len(phrase)] == phrase:
                present.append(phrase)
                break
    diagnostics.append(_trace('encoded-pakad-contact', 'unassessed' if not signatures else 'observed' if present else 'not-observed', [],
                              f'Exact signature match count={len(present)}; absence is not a musical invalidity test.'))
    nyas = set(r.get('nyasSwars', []))
    diagnostics.append(_trace('phrase-end-nyas', 'unassessed' if not sequence or not nyas else 'observed' if sequence[-1] in nyas else 'not-observed',
                              [used[-1][0]] if used else [], 'Ending is compared with encoded Nyas candidates; mid-phrase endings may differ.'))

    failures = [d['rule'] for d in diagnostics if d['outcome'] == 'fail']
    warnings = [d['rule'] for d in diagnostics if d['outcome'] == 'warn']
    return {'schema_version': 'musicology-trace-v1', 'raag_id': rid, 'taal_id': tid,
            'input_sha256': canonical_json_sha256(sample),
            'raag_record_sha256': canonical_json_sha256(r), 'taal_record_sha256': canonical_json_sha256(t),
            'inventory_review_status': {'raag': r.get('reviewStatus', 'unknown'), 'taal': t.get('reviewStatus', 'unknown')},
            'diagnostics': diagnostics, 'encoded_constraints_pass': not failures and bool(used),
            'sufficiency_status': 'encoded_constraints_checked' if used else 'insufficient_melodic_evidence',
            'encoded_failures': failures, 'review_points': warnings,
            'musician_validated': False,
            'interpretation': 'Automated checks only: encoded-constraint pass does NOT establish Raag/Taal authenticity or aesthetic acceptability.'}
