"""Upgrade 23: analyse SOURCE-DECLARED recorded syllable onsets, never fabricate gold.

The published IIT Bombay papers motivated this intake schema but no author
supplementary CSV was available at build time. A source description does not
count as acquired annotations, and synthetic fixtures cannot be promoted to
external observations. Results are descriptive onset/beat offsets only; they
are not proof of pronunciation accuracy, melody quality or a novel method.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Any

SCHEMA = "maqam.performance_u23.v1"
FIELDS = (
    "recording_id", "cycle_id", "event_id", "onset_seconds",
    "cycle_start_seconds", "beat_seconds", "beat_index", "cycle_beats",
)
MAX_BYTES = 25_000_000
MAX_ROWS = 100_000

class PerformanceDataError(ValueError):
    pass


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(65536),b""):
            h.update(block)
    return h.hexdigest()


def _finite(row:dict[str,str], name:str, rownum:int) -> float:
    try:
        val=float(row[name])
    except (ValueError, TypeError, KeyError) as e:
        raise PerformanceDataError(f"Row {rownum}: invalid numeric {name}") from e
    if not math.isfinite(val):
        raise PerformanceDataError(f"Row {rownum}: non-finite {name}")
    return val


def audit_performance(source_dir: Path) -> dict[str, Any]:
    """Checksum-gated descriptive timing audit; origin remains source-declared.

    No individual observed syllable, raw text or artist identity is reproduced in output.
    """
    root=Path(source_dir)
    if not root.is_dir() or root.is_symlink():
        raise PerformanceDataError("Source must be a real directory")
    meta=root/'provenance.json'
    if not meta.is_file() or meta.is_symlink():
        return {'schema':SCHEMA,'status':'BLOCKED_PROVENANCE_MISSING',
                'imported_rows':0,'independently_verified_sung_pronunciations':0}
    try:
        info=json.loads(meta.read_text(encoding='utf-8'))
    except (ValueError, UnicodeDecodeError) as e:
        raise PerformanceDataError('Invalid provenance.json') from e
    if not isinstance(info,dict):
        raise PerformanceDataError('Provenance must be JSON object')
    if info.get('schema') != SCHEMA:
        raise PerformanceDataError('Incorrect schema version')
    if info.get('source_kind') not in ('external_source_declared','synthetic_test_fixture'):
        raise PerformanceDataError('source_kind must be explicitly identified')
    filename=info.get('data_filename')
    if not isinstance(filename,str) or not filename or Path(filename).name!=filename or filename.startswith('.'):
        raise PerformanceDataError('Unsafe data filename')
    csvpath=root/filename
    if not csvpath.is_file() or csvpath.is_symlink():
        return {'schema':SCHEMA,'status':'BLOCKED_SOURCE_CSV_MISSING',
                'imported_rows':0,'independently_verified_sung_pronunciations':0}
    if csvpath.stat().st_size>MAX_BYTES:
        raise PerformanceDataError('CSV exceeds input-size limit')
    digest=sha256(csvpath)
    anchor=info.get('data_sha256')
    if not isinstance(anchor,str) or len(anchor)!=64 or any(c not in '0123456789abcdef' for c in anchor.lower()):
        raise PerformanceDataError('Missing or invalid SHA-256 anchor')
    if anchor.lower()!=digest:
        return {'schema':SCHEMA,'status':'BLOCKED_CHECKSUM_MISMATCH',
                'imported_rows':0,'independently_verified_sung_pronunciations':0,
                'data_sha256':digest}
    for k in ('reference_url','annotation_procedure','license_assessment','provenance_note'):
        v=info.get(k)
        if not isinstance(v,str) or not v.strip():
            raise PerformanceDataError('Missing provenance field: '+k)
    if not info['reference_url'].startswith(('https://','http://')):
        raise PerformanceDataError('Source reference URL must be HTTP(S)')
    seen=set()
    cycles={}
    offsets=[]
    nrows=0
    unusual=0
    with csvpath.open('r',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames is None or len(set(reader.fieldnames))!=len(reader.fieldnames):
            raise PerformanceDataError('Invalid or duplicate CSV headers')
        if any(c not in reader.fieldnames for c in FIELDS):
            raise PerformanceDataError('Required CSV columns missing')
        for row in reader:
            nrows+=1
            if nrows>MAX_ROWS:
                raise PerformanceDataError('Too many rows')
            ident=tuple((row.get(k) or '').strip() for k in ('recording_id','cycle_id','event_id'))
            if not all(ident):
                raise PerformanceDataError(f'Row {nrows}: missing event identity')
            if ident in seen:
                raise PerformanceDataError(f'Row {nrows}: duplicate event identity')
            seen.add(ident)
            onset=_finite(row,'onset_seconds',nrows)
            start=_finite(row,'cycle_start_seconds',nrows)
            beat=_finite(row,'beat_seconds',nrows)
            idx=_finite(row,'beat_index',nrows)
            length=_finite(row,'cycle_beats',nrows)
            if onset<0 or start<0 or beat<=0 or length<=0 or length!=int(length) or idx<1 or idx>length:
                raise PerformanceDataError(f'Row {nrows}: invalid timing/beat ranges')
            cycle_key=ident[:2]
            cycle=(start,beat,length)
            if cycle_key in cycles and cycles[cycle_key]!=cycle:
                raise PerformanceDataError(f'Row {nrows}: contradictory grid for same cycle')
            cycles[cycle_key]=cycle
            expected=start+(idx-1)*beat
            delta=(onset-expected)/beat
            offsets.append(delta)
            if abs(delta)>2.0: unusual+=1
    if nrows==0:
        return {'schema':SCHEMA,'status':'BLOCKED_EMPTY_DATA',
                'imported_rows':0,'independently_verified_sung_pronunciations':0}
    is_fixture=info['source_kind']=='synthetic_test_fixture'
    return {
        'schema':SCHEMA,
        'status':'SYNTHETIC_FIXTURE_NOT_EXTERNAL_EVIDENCE' if is_fixture else 'STRUCTURED_EXTERNAL_DATA_REQUIRES_MANUAL_PROVENANCE_CHECK',
        'source_kind':info['source_kind'],
        'imported_rows':nrows,
        'recording_count':len({k[0] for k in cycles}),
        'rhythmic_cycle_count':len(cycles),
        'mean_normalized_signed_offset':round(mean(offsets),8),
        'mean_absolute_beat_offset':round(mean(abs(x) for x in offsets),8),
        'median_absolute_beat_offset':round(median(abs(x) for x in offsets),8),
        'large_offset_count_over_two_beats':unusual,
        'data_sha256':digest,
        'reference_url':info['reference_url'],
        'license_assessment_is_source_declared':True,
        'independently_verified_sung_pronunciations':0,
        'sung_pronunciation_variant_pairs':0,
        'real_world_pronunciation_alignment_advantage':'NOT_MEASURED',
        'note':'Offsets are descriptive against the supplied metrical grid; source accuracy and license claims require independent review.'
    }
