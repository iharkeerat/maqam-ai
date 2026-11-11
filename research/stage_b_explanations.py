"""Stage-B instrument: blinded *model identity*, never blinded content.

Stage A must already be frozen; the two arms are compared within each case.
The score collected here is subjective musicological usefulness, not accuracy.
No participant/permission verification or real musician work occurs in this code.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import secrets
from pathlib import Path
from typing import Any

from research.musicology_audit import audit_phrase, canonical_json_sha256
from scripts.validate_stage_a import validate as validate_stage_a_forms
from scripts.external_study import REVIEW_FIELDS as STAGE_A_FIELDS

REVIEW_FIELDS = ['study_case_id', 'candidate_code', 'reviewer_code', 'consent_version',
                 'consent_accepted', 'raag_plausibility_1_to_5',
                 'taal_structure_1_to_5', 'explanation_helpfulness_1_to_5',
                 'explanation_faithfulness_1_to_5', 'any_hard_musical_error',
                 'abstain', 'abstain_reason', 'comments']
PACKET_FIELDS = ['study_case_id', 'candidate_code', 'language', 'poem', 'raag',
                 'taal', 'notation_json', 'explanation']


def _read_cases(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        if not {'study_case_id', 'language', 'poem'}.issubset(set(r.fieldnames or [])):
            raise ValueError('Stage-A case packet missing expected columns')
        rows = list(r)
    cases = {str(row['study_case_id']).strip(): row for row in rows}
    if not cases or len(cases) != len(rows) or any(not k or not v['poem'].strip() for k, v in cases.items()):
        raise ValueError('Stage-A case packet empty/duplicated/invalid')
    return cases


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_stage_b(*, cases_csv: Path, candidates_json: Path, stage_a_validation_json: Path,
                    stage_a_forms: list[Path], stage_a_manifest_json: Path, output_dir: Path, reviewers: int, consent_version: str,
                    human_clearance_record: Path) -> dict[str, Any]:
    """Prepare private packets and mapping with explicit, inspectable Stage-A gate.

    This gate detects obvious missing/failed Stage-A validation and records the
    input fingerprints; it is NOT a verification of the human clearance record.
    """
    if reviewers < 2 or reviewers > 20:
        raise ValueError('Stage B requires 2–20 independent reviewers')
    if not re.fullmatch(r'[A-Za-z0-9._-]{3,50}', consent_version):
        raise ValueError('Invalid consent-version identifier')
    if not human_clearance_record.is_file() or not human_clearance_record.read_text(encoding='utf-8').strip():
        raise ValueError('Documented human ethics/permissions determination required')
    if not stage_a_forms or any(not x.is_file() or not x.stat().st_size for x in stage_a_forms):
        raise ValueError('Completed Stage-A forms must be supplied as real files')
    verification = json.loads(stage_a_validation_json.read_text(encoding='utf-8'))
    if verification.get('passed') is not True or int(verification.get('reviewer_count', 0)) < 2:
        raise ValueError('Stage-A validation not passed or insufficient reviewers')
    cases = _read_cases(cases_csv)
    stage_a_manifest = json.loads(stage_a_manifest_json.read_text(encoding='utf-8'))
    known_reviewers = stage_a_manifest.get('reviewer_codes', [])
    if not isinstance(known_reviewers, list) or len(known_reviewers) < 2 or len(set(known_reviewers)) != len(known_reviewers):
        raise ValueError('Stage-A manifest has invalid or insufficient reviewer roster')
    if len(known_reviewers) != verification['reviewer_count']:
        raise ValueError('Stage-A review roster does not match validation report')
    if int(verification.get('review_rows', -1)) != len(cases) * int(verification['reviewer_count']):
        raise ValueError('Stage-A row count inconsistent with case packet')
    # Revalidate the ACTUAL forms; a self-declared `passed` report by itself is
    # insufficient. Still does not prove a person really signed the form.
    stage_a_rows = []
    for path in stage_a_forms:
        with path.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if not set(STAGE_A_FIELDS).issubset(set(reader.fieldnames or [])):
                raise ValueError('Stage-A form missing required fields')
            stage_a_rows.extend(reader)
    recheck = validate_stage_a_forms(stage_a_rows, set(cases), stage_a_manifest.get('consent_version'), set(known_reviewers))
    if not recheck['passed'] or recheck['review_rows'] != verification['review_rows']:
        raise ValueError('Stage-A original reviewer forms do not validate: ' + str(recheck['errors'][:3]))
    data = json.loads(candidates_json.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('cases'), list):
        raise ValueError('Candidate input must contain a cases list')
    items = data['cases']
    if len(items) != len(cases):
        raise ValueError('Stage-B candidate case set must match Stage A')
    result_rows, mappings = [], []
    seen = set()
    for item in items:
        cid = item.get('study_case_id')
        if cid not in cases or cid in seen:
            raise ValueError('Unknown/duplicate Stage-B case')
        seen.add(cid)
        arms = item.get('candidates')
        if not isinstance(arms, list) or len(arms) != 2:
            raise ValueError('Exactly two candidate explanations required per case')
        if not all(isinstance(a, dict) and isinstance(a.get('arm_id'), str) and 1 <= len(a['arm_id'].strip()) <= 100 for a in arms):
            raise ValueError('Each arm must have a nonblank string arm_id')
        ids = {a['arm_id'].strip() for a in arms}
        if len(ids) != 2:
            raise ValueError('Each arm_id must be unique and nonblank')
        for arm in arms:
            for key in ('raag_id', 'taal_id', 'notation', 'explanation'):
                if key not in arm:
                    raise ValueError(f'Candidate missing {key}')
            if not isinstance(arm['explanation'], str) or not (8 <= len(arm['explanation'].strip()) <= 4000):
                raise ValueError('Explanation must be a human-readable 8–4000 char string')
            if any(s.lower() in arm['explanation'].lower() for s in ('MAQAM AI', 'baseline model', 'hybrid model')):
                raise ValueError('Explanation leaks recognisable system identity; manually anonymize')
            sample = {k: arm[k] for k in ('raag_id', 'taal_id', 'notation')}
            report = audit_phrase(sample)
            code = 'cand-' + secrets.token_hex(7)
            result_rows.append({'study_case_id': cid, 'candidate_code': code,
                                'language': cases[cid]['language'], 'poem': cases[cid]['poem'],
                                'raag': arm['raag_id'], 'taal': arm['taal_id'],
                                'notation_json': json.dumps(arm['notation'], ensure_ascii=False),
                                'explanation': arm['explanation']})
            mappings.append({'study_case_id': cid, 'candidate_code': code,
                             'arm_id': arm['arm_id'], 'sample_sha256': report['input_sha256'],
                             'explanation_sha256': hashlib.sha256(arm['explanation'].encode('utf-8')).hexdigest(),
                             'encoded_constraints_pass': report['encoded_constraints_pass'],
                             'rule_trace': report['diagnostics']})
    if set(cases) != seen:
        raise ValueError('Missing Stage-B case')
    if output_dir.exists():
        raise FileExistsError('Stage-B output already exists; choose a fresh private directory')
    # All validation before side effects. Keep rights-restricted poetry in private output only.
    output_dir.mkdir(parents=True, exist_ok=False)
    output_dir.chmod(0o700)
    def save_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
        with path.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
            writer.writeheader(); writer.writerows(rows)
        path.chmod(0o600)
    mapping_path = output_dir / 'arm_mapping_PRIVATE_DO_NOT_SHARE.json'
    mapping_path.write_text(json.dumps(mappings, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    mapping_path.chmod(0o600)
    shuffle = random.SystemRandom()
    reviewer_codes = []
    orders = {}
    for num in range(reviewers):
        rev = 'revB-' + secrets.token_hex(6)
        reviewer_codes.append(rev)
        # Independently shuffle the order both across cases and A/B within cases.
        shuffled = list(result_rows)
        shuffle.shuffle(shuffled)
        orders[rev] = canonical_json_sha256([(r['study_case_id'], r['candidate_code']) for r in shuffled])
        save_csv(output_dir / f'reviewer_{num+1:02d}_BLIND_CANDIDATES.csv', PACKET_FIELDS, shuffled)
        form = [{'study_case_id': row['study_case_id'], 'candidate_code': row['candidate_code'],
                 'reviewer_code': rev, 'consent_version': consent_version} for row in shuffled]
        save_csv(output_dir / f'reviewer_{num+1:02d}_RATINGS_PRIVATE.csv', REVIEW_FIELDS, form)
    manifest = {'status': 'STAGE_B_PREPARED_NO_RATINGS', 'case_count': len(cases),
                'candidate_count': len(result_rows), 'reviewers': reviewer_codes,
                'case_packet_sha256': _sha256(cases_csv),
                'candidate_source_sha256': _sha256(candidates_json),
                'stage_a_validation_sha256': _sha256(stage_a_validation_json),
                'stage_a_manifest_sha256': _sha256(stage_a_manifest_json),
                'stage_a_form_sha256': {_sha256(p): p.name for p in stage_a_forms},
                'human_clearance_record_sha256': _sha256(human_clearance_record),
                'consent_version': consent_version, 'reviewer_order_sha256': orders,
                'stage_a_forms_revalidated': True,
                'interpretation': 'Model arms are hidden from reviewers; explanations shown. Preparation does not prove musician recruitment, consent, copyright clearance, valid performance, or efficacy.'}
    dest = output_dir / 'study_manifest_PRIVATE.json'
    dest.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    dest.chmod(0o600)
    (output_dir / 'READ_FIRST_PRIVATE.txt').write_text(
        'Stage B must be after Stage A is frozen. This is model-identity masking, not blind-to-explanation.\n'
        'Before distributing: independently check clearance records and Stage-A form authenticity, rights to share poetry,\n'
        'consent and participant qualifications. Explain that rule audit summaries are not musical truth.\n'
        'Never share arm_mapping_PRIVATE_DO_NOT_SHARE.json or manifest with reviewers.\n'
        'The two arms per case MUST be matched in advance and never selected based on test ratings.\n', encoding='utf-8')
    return {'prepared': True, 'cases': len(cases), 'candidates': len(result_rows),
            'reviewer_forms': reviewers, 'output_directory': str(output_dir),
            'valid_human_study_proven': False}


def validate_stage_b_ratings(forms: list[dict[str, str]], candidate_pairs: set[tuple[str, str]],
                             reviewer_ids: set[str], consent_version: str) -> dict[str, Any]:
    errors = []
    seen = set()
    for i, row in enumerate(forms, start=2):
        case, candidate, reviewer = (row.get(k, '').strip() for k in ('study_case_id', 'candidate_code', 'reviewer_code'))
        if (case, candidate) not in candidate_pairs or reviewer not in reviewer_ids:
            errors.append((i, 'unknown_candidate_or_reviewer'))
        if (case, candidate, reviewer) in seen:
            errors.append((i, 'duplicate_rating'))
        seen.add((case, candidate, reviewer))
        if row.get('consent_version', '').strip() != consent_version or row.get('consent_accepted', '').strip().lower() != 'yes':
            errors.append((i, 'consent_missing_or_wrong_version'))
        if row.get('abstain', '').strip().lower() not in {'yes', 'no'}:
            errors.append((i, 'abstain_missing'))
        if row.get('abstain', '').strip().lower() == 'yes':
            if not row.get('abstain_reason', '').strip():
                errors.append((i, 'abstention_reason_missing'))
            if any(row.get(k, '').strip() for k in REVIEW_FIELDS if k.endswith('_1_to_5')):
                errors.append((i, 'abstainer_provided_scores'))
        else:
            for k in REVIEW_FIELDS:
                if k.endswith('_1_to_5') and row.get(k, '').strip() not in {'1','2','3','4','5'}:
                    errors.append((i, 'invalid_or_missing_' + k))
            if row.get('any_hard_musical_error', '').strip().lower() not in {'yes','no','uncertain'}:
                errors.append((i, 'musical_error_flag_missing'))
    expected = {(c, v, r) for c, v in candidate_pairs for r in reviewer_ids}
    if seen != expected:
        errors.append((0, 'missing_or_unexpected_candidate_rating_pairs'))
    return {'passed': not errors and bool(forms), 'review_rows': len(forms),
            'expected_rows': len(expected), 'errors': errors,
            'independent_human_validation_proven': False}
