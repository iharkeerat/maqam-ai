"""Upgrade 22: verify external SargamBench artifacts against their own files.

No corpus files are embedded. Public abstracts and metadata MUST NOT be
promoted to verified lyric/syllable/taal research measurements.

CLI: python scripts/inspect_sargambench_u22.py --source-dir /path/to/downloaded/files --out report.json
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

REQUIRED = ('README.md', 'manifest.json', 'pairs.csv')
LYRIC_FIELDS = ('lyric_devanagari', 'lyric_latin')


class ArtifactAuditError(ValueError):
    pass


def regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _digest_file(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open('rb') as f:
        for block in iter(lambda: f.read(65536), b''):
            h.update(block)
    return h.hexdigest()


def inspect_artifacts(source_dir: Path, *, published_md5: dict[str, str] | None = None) -> dict[str, Any]:
    """Inspect actual local bytes. Never infer downstream validity from a record description."""
    source_dir = Path(source_dir)
    if not source_dir.is_dir() or source_dir.is_symlink():
        raise ArtifactAuditError('Source directory must be a real directory')
    absent = [n for n in REQUIRED if not regular_file(source_dir / n)]
    if absent:
        return {'schema_version': '1.0', 'status': 'BLOCKED_SOURCE_ARTIFACTS_MISSING',
                'missing_files': absent, 'verified_lyric_alignment_rows': 0,
                'real_world_pronunciation_advantage': 'NOT_MEASURED'}
    readme = (source_dir/'README.md').read_text(encoding='utf-8-sig')
    try:
        manifest = json.loads((source_dir/'manifest.json').read_text(encoding='utf-8-sig'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ArtifactAuditError('Invalid manifest JSON') from e
    if not isinstance(manifest, dict) or not isinstance(manifest.get('files'), list):
        raise ArtifactAuditError('Manifest must contain files list')
    file_info={}
    for item in manifest['files']:
        if not isinstance(item,dict):
            raise ArtifactAuditError('Invalid manifest entry')
        name=item.get('path')
        if not isinstance(name,str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ArtifactAuditError('Unsafe manifest path')
        if name in file_info:
            raise ArtifactAuditError('Duplicate manifest file')
        file_info[name]=item
    observed = {}
    checksum_errors=[]
    for name in REQUIRED:
        path=source_dir/name
        actual_size=path.stat().st_size
        actual_sha=_digest_file(path,'sha256')
        actual_md5=_digest_file(path,'md5')
        info=file_info.get(name)
        if info:
            if isinstance(info.get('size_bytes'),int) and info['size_bytes']!=actual_size:
                checksum_errors.append(f'{name}: size mismatch against internal manifest')
            if info.get('sha256') and info['sha256'].lower()!=actual_sha:
                checksum_errors.append(f'{name}: SHA-256 mismatch against internal manifest')
        elif name=='pairs.csv':
            checksum_errors.append('pairs.csv: not present in internal file manifest')
        if published_md5 and name in published_md5 and actual_md5!=published_md5[name].lower():
            checksum_errors.append(f'{name}: MD5 mismatch against published Zenodo file listing')
        observed[name]={'bytes':actual_size,'sha256':actual_sha,'md5':actual_md5}
    summary=manifest.get('summary') if isinstance(manifest.get('summary'),dict) else {}
    with (source_dir/'pairs.csv').open('r',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        headers=reader.fieldnames or []
        lyric_cols=[col for col in LYRIC_FIELDS if col in headers]
        row_count=0
        any_lyric=0
        complete_lyric=0
        for row in reader:
            row_count+=1
            filled=sum(bool((row.get(k) or '').strip()) for k in lyric_cols)
            if filled: any_lyric+=1
            if len(lyric_cols)==len(LYRIC_FIELDS) and filled==len(LYRIC_FIELDS): complete_lyric+=1
    if isinstance(summary.get('reconstructed_base_rows'),int) and summary['reconstructed_base_rows']!=row_count:
        checksum_errors.append('pairs.csv: row count differs from source manifest reconstruction summary')
    reconstructed='reconstruct' in readme.lower() or 'reconstruct' in str(manifest.get('release','')).lower()
    missing_lyrics_reported=summary.get('missing_lyrics')
    claims_inconsistent = bool(missing_lyrics_reported==row_count and any_lyric>0)
    if claims_inconsistent:
        checksum_errors.append('Manifest claims every lyric missing but CSV contains nonempty lyrics')
    if checksum_errors:
        status='BLOCKED_INTEGRITY_OR_CROSS_FILE_CONTRADICTION'
    elif row_count==0:
        status='BLOCKED_EMPTY_CORPUS'
    elif not lyric_cols or complete_lyric==0:
        status='BLOCKED_NO_COMPLETE_LYRIC_COLUMNS'
    elif reconstructed:
        status='BLOCKED_RECONSTRUCTION_NEEDS_INDEPENDENT_ANNOTATION_CHECK'
    else:
        status='STRUCTURE_PRESENT_INDEPENDENT_ADJUDICATION_REQUIRED'
    return {'schema_version':'1.0','status':status,'source_type':'EXTERNAL_UNADJUDICATED',
            'release_claims_reconstructed':reconstructed, 'manifest_reported_missing_lyrics':missing_lyrics_reported,
            'row_count':row_count,'lyric_fields_present':lyric_cols,'rows_with_any_lyric':any_lyric,
            'rows_with_both_lyric_fields':complete_lyric,'file_digests':observed,
            'checksum_or_consistency_errors':checksum_errors,
            'verified_lyric_alignment_rows':0,'verified_taal_lyric_gold_rows':0,
            'verified_sung_pronunciation_variants':0,
            'real_world_pronunciation_advantage':'NOT_MEASURED',
            'note':'Presence of a lyric column is not independently validated syllable alignment.'}


def inspect_published_observations(observations_path:Path)->dict[str,Any]:
    """Evaluate SOURCE-DESCRIBED attributes only. This is not a corpus-byte audit."""
    x=json.loads(Path(observations_path).read_text(encoding='utf8'))
    published=x['published_record_description']
    manifest=x['downloadable_manifest_observations']
    readme=x['downloadable_readme_observations']
    mismatch=(published['advertised_has_syllable_alignment'] and
              readme['states_lyric_fields_blank'] and
              manifest['missing_lyrics']>=manifest['base_rows'])
    return {'schema_version':'1.0','evidence_type':'WEB_OBSERVED_METADATA_NOT_CORPUS_BYTES',
            'source_url':x['record_url'],'descriptive_conflict':bool(mismatch),
            'advertised_pairs':published['advertised_lyric_sargam_pairs'],
            'manifest_missing_lyrics':manifest['missing_lyrics'],
            'metadata_only_eligible_confirmatory_records':0,
            'taal_annotations_verified':0,
            'download_status':'NOT_OBTAINED',
            'scientific_status':'BLOCKED_RELEASE_ANNOTATION_CONFLICT' if mismatch else 'BLOCKED_CORPUS_NOT_INSPECTED'}


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir', type=Path)
    p.add_argument('--observations',type=Path)
    p.add_argument('--anchor-observations',type=Path, help='Published Zenodo md5 checksums to compare against downloaded bytes')
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if (args.source_dir is None)==(args.observations is None):
        p.error('Provide exactly one of --source-dir or --observations')
    if args.observations:
        res=inspect_published_observations(args.observations)
    else:
        anchors=None
        if args.anchor_observations:
            meta=json.loads(args.anchor_observations.read_text(encoding='utf8'))
            anchors={name:v['md5'] for name,v in meta['published_download_checksums'].items()}
        res=inspect_artifacts(args.source_dir,published_md5=anchors)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(res,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps({'status':res.get('status',res.get('scientific_status')),
                      'eligible_confirmatory_rows':res.get('verified_lyric_alignment_rows',res.get('metadata_only_eligible_confirmatory_records',0))},sort_keys=True))

if __name__=='__main__': main()
