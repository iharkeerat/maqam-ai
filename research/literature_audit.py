"""Auditable novelty-policy gate; never equates literature search with proof of novelty.

Offline-only. References are a curated, timestamped snapshot of verified publisher or
preprint metadata, not an automated citation or comprehensive literature search.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

REGISTRY = Path('research/literature/SOURCE_REGISTER.json')
CLAIMS = Path('research/literature/NOVELTY_CLAIMS.json')
MATRIX = Path('research/literature/NOVELTY_MATRIX.csv')
REPORT = Path('portfolio/SURF_2027/UPGRADE_13_NOVELTY_AUDIT.md')
DECISIONS = {'BLOCK_PRIOR_ART', 'BLOCK_NOT_ESTABLISHED', 'BLOCK_NO_COMPARISON',
             'BLOCK_NO_EXTERNAL_VALIDATION', 'BLOCK_NO_VALIDATION', 'BLOCK_REUSED_HOLDOUT',
             'SUPPORT_AS_ENGINEERING', 'SUPPORT_SYNTHETIC_ONLY', 'OPEN_HYPOTHESIS'}
BLOCKED_PREFIX = 'BLOCK_'
SUPPORTED = {'SUPPORT_AS_ENGINEERING', 'SUPPORT_SYNTHETIC_ONLY'}
KEY_REFERENCES = {'mandlik2023','kader2026','geirhos2020','ribeiro2020','singh2024','doddapaneni2023'}
REQUIRED_CLAIMS = {'FIRST_LYRICS_RAAG','FIRST_SOUTH_ASIAN_LLM_BENCHMARK',
                   'SHORTCUT_INVENTION','FIRST_COUNTERFACTUAL_TEST','FIRST_EXPLAINABLE_RAGA',
                   'FIRST_INDIC_NLP','NEW_EXPLANATION_METHOD','BETTER_THAN_CHATGPT',
                   'MUSICAL_CORRECTNESS','CONFIRMATORY_FINDING','REPRO_CASE',
                   'METADATA_SHORTCUT','COMPARABLE_BASELINES','POTENTIAL_EVAL_GAP'}
ACCEPTED_HOSTS = {'aclanthology.org', 'www.nature.com', 'arxiv.org',
                  'compmusic.upf.edu', 'www.ijcrt.org', 'doi.org',
                  'ojs.aaai.org'}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def audit(root: Path) -> dict:
    root = Path(root)
    errors=[]
    try:
        raw_sources = (root/REGISTRY).read_bytes()
        raw_claims = (root/CLAIMS).read_bytes()
        raw_matrix = (root/MATRIX).read_bytes()
        raw_report = (root/REPORT).read_bytes()
        sources=json.loads(raw_sources)
        policy=json.loads(raw_claims)
        with (root/MATRIX).open(encoding='utf-8',newline='') as f:
            matrix=list(csv.DictReader(f))
    except (OSError, UnicodeError, ValueError, csv.Error) as exc:
        return {'status':'BLOCKED', 'errors':[f'Missing/unreadable registry: {exc}']}

    records=sources.get('sources', [])
    source_by_id={r.get('id'):r for r in records}
    claims=policy.get('claims',[])
    by_id={c.get('id'):c for c in claims}
    if not sources.get('review_date') or not sources.get('scope'):
        errors.append('Review date and search-scope disclosure required')
    if 'not systematic' not in sources.get('scope','').lower():
        errors.append('Review must explicitly disclose non-systematic scope')
    if len(source_by_id)!=len(records) or not KEY_REFERENCES.issubset(source_by_id):
        errors.append('Unique IDs and six mandatory close prior-art sources are required')
    for r in records:
        for k in ('title','authors','venue','url','source_type','assessment','relation','year'):
            if not r.get(k): errors.append(f"{r.get('id')}: missing {k}")
        host=urlparse(r.get('url','')).hostname
        if host not in ACCEPTED_HOSTS: errors.append(f"{r.get('id')}: unknown evidence host {host}")
        if r.get('year',0)>2026: errors.append(f"{r.get('id')}: publication is future-dated")
        if r.get('source_type')=='preprint' and not ('arxiv.org/' in r.get('url','')):
            errors.append(f"{r.get('id')}: preprint missing appropriate source")
    if len(by_id)!=len(claims) or not REQUIRED_CLAIMS.issubset(by_id):
        errors.append('Required policy claims or unique IDs missing')
    for c in claims:
        cid=c.get('id','<missing>')
        if c.get('decision') not in DECISIONS: errors.append(f'{cid}: invalid decision')
        if not c.get('reason'): errors.append(f'{cid}: no justification')
        refs=c.get('related_prior_work',[])
        if not refs: errors.append(f'{cid}: no prior work reference')
        for s in refs:
            if s not in source_by_id: errors.append(f'{cid}: missing source {s}')
        if c.get('decision','').startswith(BLOCKED_PREFIX) and not refs:
            errors.append(f'{cid}: blocked claim has no literature context')
        if c.get('decision') in SUPPORTED:
            evidence=c.get('internal_evidence',[])
            if not evidence: errors.append(f'{cid}: missing local evidence')
            for e in evidence:
                local=root/e
                if not local.is_file(): errors.append(f'{cid}: missing evidence file: {e}')
                elif not local.resolve().is_relative_to(root.resolve()):
                    errors.append(f'{cid}: evidence path traversal')
        elif c.get('internal_evidence'):
            errors.append(f'{cid}: claim is not supported but provides empirical evidence as if supported')
    for critical in ('FIRST_LYRICS_RAAG','FIRST_SOUTH_ASIAN_LLM_BENCHMARK',
                     'SHORTCUT_INVENTION','FIRST_COUNTERFACTUAL_TEST',
                     'FIRST_EXPLAINABLE_RAGA','FIRST_INDIC_NLP'):
        if by_id.get(critical,{}).get('decision')!='BLOCK_PRIOR_ART':
            errors.append(f'{critical}: must recognize established prior art')
    for unsupported in ('MUSICAL_CORRECTNESS','BETTER_THAN_CHATGPT','CONFIRMATORY_FINDING'):
        if not by_id.get(unsupported,{}).get('decision','').startswith('BLOCK_'):
            errors.append(f'{unsupported}: unsupported real-world claim was promoted')
    if by_id.get('POTENTIAL_EVAL_GAP',{}).get('decision')!='OPEN_HYPOTHESIS':
        errors.append('Research gap must remain a hypothesis')
    if len(matrix)!=len(claims): errors.append('CSV matrix must contain every claim')
    matrix_by_id={r.get('id'):r for r in matrix}
    if len(matrix_by_id)!=len(matrix): errors.append('Duplicated claim in CSV matrix')
    for c in claims:
        m=matrix_by_id.get(c.get('id'))
        if not m or any(m.get(k)!=c.get(k) for k in ('claim','decision','reason')):
            errors.append(f"{c.get('id')}: CSV and JSON claim policies differ")
    text=raw_report.decode('utf-8','replace')
    for phrase in ('2023 Mandlik','2026 Kader','not a','NOT','research','novelty'):
        if phrase.lower() not in text.lower():
            errors.append(f'Report missing key discussion: {phrase}')
    return {'status':'PASS_CLAIM_POLICY_ONLY' if not errors else 'BLOCKED',
            'errors':errors, 'references':len(records),'claims':len(claims),
            'blocked_claims':sum(c['decision'].startswith('BLOCK_') for c in claims),
            'supported_internal':sum(c['decision'] in SUPPORTED for c in claims),
            'open_hypotheses':sum(c['decision']=='OPEN_HYPOTHESIS' for c in claims),
            'sha256':{'sources':_sha(raw_sources),'claims':_sha(raw_claims),
                      'matrix':_sha(raw_matrix),'review':_sha(raw_report)},
            'limits':['No exhaustive novelty search or patent landscape',
                      'Literature abstracts/method excerpts do not establish identical implementation',
                      'No human assessment or hosted LLM run',
                      'No fresh confirmatory holdout',
                      'Research novelty remains unproven']}
