"""U24: fail-closed, source-scoped acquisition and evidence profiling.

Only the one pre-registered small public CSV is automatically downloadable. Acquiring
bytes establishes neither redistribution rights nor real vocal/syllabic validity.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from typing import Any

REGISTRY = Path(__file__).with_name('U24_SOURCE_RECOVERY_REGISTRY.json')
SCHEMA='maqam.u24.evidence_passport.v1'
MAX_CSV_BYTES=5_000_000
MAX_CSV_ROWS=100_000

class RecoveryError(ValueError):
    pass


def sources()->dict[str,dict[str,Any]]:
    d=json.loads(REGISTRY.read_text(encoding='utf-8'))
    if d.get('schema')!='maqam.external_recovery_u24.registry.v1':
        raise RecoveryError('Unsupported source registry')
    result={x['id']:x for x in d['sources']}
    if len(result)!=len(d['sources']):raise RecoveryError('Duplicate registered source IDs')
    return result


def lookup(source_id:str)->dict[str,Any]:
    try: return sources()[source_id]
    except KeyError as e: raise RecoveryError('Unregistered source ID') from e


def sha256(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def _csv_profile(raw:bytes)->dict[str,Any]:
    if not raw or len(raw)>MAX_CSV_BYTES: raise RecoveryError('Empty or oversized CSV')
    if b'\x00' in raw: raise RecoveryError('Binary data in CSV')
    try: text=raw.decode('utf-8-sig')
    except UnicodeDecodeError as e: raise RecoveryError('Expected UTF-8 CSV') from e
    if len(text)>MAX_CSV_BYTES: raise RecoveryError('Decoded CSV too large')
    reader=csv.reader(io.StringIO(text,newline=''),strict=True)
    try: header=next(reader)
    except (StopIteration,csv.Error) as e: raise RecoveryError('Missing CSV header') from e
    if not header or len(header)>100 or any(not h.strip() for h in header):
        raise RecoveryError('Invalid CSV header')
    if len(set(header))!=len(header):raise RecoveryError('Duplicate CSV columns')
    row_count=0
    missing=[0]*len(header)
    try:
        for row in reader:
            if row_count>=MAX_CSV_ROWS:raise RecoveryError('Too many CSV rows')
            if len(row)!=len(header):raise RecoveryError('Ragged CSV data')
            for i,x in enumerate(row):
                if not x.strip():missing[i]+=1
            row_count+=1
    except csv.Error as e: raise RecoveryError('Invalid quoted CSV') from e
    if row_count==0:raise RecoveryError('CSV contains no data rows')
    return {'columns':header,'row_count':row_count,'missing_field_counts':dict(zip(header,missing)),
            'parser':'utf8_csv_native_profile_only','note':'No syllable/phone interpretation is inferred from a column name.'}


def profile_local(source_id:str,path:Path,expected_sha256:str|None=None)->dict[str,Any]:
    source=lookup(source_id)
    path=Path(path)
    if not path.is_file() or path.is_symlink():raise RecoveryError('Supply an existing regular non-symlink file')
    if path.stat().st_size>MAX_CSV_BYTES:raise RecoveryError('Source file exceeds 5 MB safe inspection limit')
    raw=path.read_bytes()
    digest=sha256(raw)
    if expected_sha256 is not None:
        if len(expected_sha256)!=64 or not all(c in '0123456789abcdef' for c in expected_sha256.lower()):
            raise RecoveryError('Expected SHA-256 is malformed')
        if digest!=expected_sha256.lower():raise RecoveryError('Source-file SHA-256 mismatch')
    if path.suffix.lower()!='.csv':raise RecoveryError('Only CSV source artifacts are profiled in U24')
    content=_csv_profile(raw)
    return {'schema':SCHEMA,'source_id':source_id,'documented_modality':source['modality'],
            'file_name':path.name,'file_sha256':digest,'file_bytes':len(raw),
            'original_file_acquired':True,'native_profile':content,
            'rights_review':'PENDING_MANUAL','annotation_semantics_review':'PENDING_MANUAL',
            'verified_sung_pronunciation_pairs':0,
            'verified_lyric_rhythm_alignment_pairs':0,
            'research_claim_status':'NOT_ELIGIBLE_FOR_REAL_LANGUAGE_HYPOTHESIS',
            'prohibited_inferences':source['exclusions'],
            'warning':'Downloaded/source-declared data do not become verified vocal ground truth through CSV parsing or checksum checks.'}

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RecoveryError('HTTP redirect refused: manual review of new host required')


def fetch_registered(source_id:str,out_dir:Path,timeout:int=12)->dict[str,Any]:
    """Opt-in public sample fetch; no arbitrary URL input or redirects allowed."""
    src=lookup(source_id)
    if not src.get('direct_download_approved') or not src.get('download_url'):
        raise RecoveryError('This source requires manual acquisition or rights review')
    u=urlparse(src['download_url'])
    if u.scheme!='https' or u.hostname!='compmusic.upf.edu' or u.port is not None or u.username:
        raise RecoveryError('Download endpoint is not on the exact allowlist')
    if not u.path.startswith('/system/files/static_files/') or not u.path.endswith('.csv'):
        raise RecoveryError('Only documented static sample CSV is allowed')
    req=Request(src['download_url'],headers={'User-Agent':'MAQAM-research-acquisition/1.0'})
    with build_opener(_NoRedirect()).open(req,timeout=timeout) as response:
        if getattr(response,'status',200)!=200:raise RecoveryError('Non-200 response')
        raw=response.read(MAX_CSV_BYTES+1)
    _csv_profile(raw)
    out_dir=Path(out_dir)
    out_dir.mkdir(parents=True,exist_ok=True)
    target=out_dir/(source_id+'.csv')
    if target.exists() or target.is_symlink():raise RecoveryError('Refusing to overwrite an existing acquisition')
    fd,tmp=tempfile.mkstemp(prefix='.acquire-',dir=str(out_dir))
    try:
        with os.fdopen(fd,'wb') as f:f.write(raw)
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return profile_local(source_id,target)


def coverage(registry:dict[str,dict[str,Any]]|None=None)->dict[str,Any]:
    records=registry or sources()
    return {'schema':'maqam.u24.recovery_coverage.v1','source_count':len(records),
            'web_documented_sources':len(records),
            'acquired_original_external_files_in_release':0,
            'independently_attested_pronunciation_variant_pairs':0,
            'same_item_pronunciation_and_lyric_rhythm_gold_pairs':0,
            'prospective_hypothesis_test':'BLOCKED_MISSING_INDEPENDENT_SAME_ITEM_EVIDENCE',
            'source_roles':{k:v['evidence_class'] for k,v in records.items()},
            'next_action':'Obtain original IIT Bombay syllable-level annotations and distinct independently attested pronunciation alternatives, with permissions and same-item correspondence.'}
