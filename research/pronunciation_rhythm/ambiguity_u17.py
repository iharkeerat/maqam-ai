"""Upgrade 17: strictly evidence-bounded linguistic ambiguity triage.

Records observed schwa-phone tokens and hypothetical deletion transforms without
misrepresenting either as attested alternative pronunciation or as syllabified
music evidence. Keeps third-party phone sequences and constructed probes apart.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .lexical_evidence import (
    Lexeme, LexiconError, RAW_UPSTREAM, parse_full_lexicon,
    parse_source_excerpt, verify_excerpt_against_full,
)

# This token is the literal source lexicon symbol; not a general phonology rule.
ORTHOGRAPHIC_SCHWA_TOKEN = "ə"


@dataclass(frozen=True)
class Counterfactual:
    source_line: int
    orthography: str
    phone_index: int
    observed_phones: tuple[str, ...]
    hypothetical_phones: tuple[str, ...]
    evidence_level: str = "HYPOTHETICAL_PHONE_DELETION_UNATTESTED"


def generate_deletion_probes(rows: list[Lexeme]) -> list[Counterfactual]:
    """Delete one literal schwa token, at most one at a time.

    This is a bounded diagnostic manipulation. The result is **not** asserted
    to be a valid word pronunciation, a syllable count or singing evidence.
    """
    seen = set()
    results = []
    for row in rows:
        for index, phon in enumerate(row.phones):
            if phon != ORTHOGRAPHIC_SCHWA_TOKEN:
                continue
            altered = row.phones[:index] + row.phones[index + 1:]
            if not altered:
                continue
            key = (row.source_line, index, altered)
            if key in seen:
                continue
            seen.add(key)
            results.append(Counterfactual(row.source_line, row.orthography, index,
                                          row.phones, altered))
    return results


def inventory(rows: list[Lexeme]) -> dict:
    if not rows:
        raise LexiconError("Empty dataset is not an evidence source")
    words: dict[str, set[tuple[str, ...]]] = {}
    for row in rows:
        words.setdefault(row.orthography, set()).add(row.phones)
    multi = {w: len(v) for w, v in sorted(words.items()) if len(v) > 1}
    probes = generate_deletion_probes(rows)
    return {
        "lexical_records": len(rows),
        "unique_spellings": len(words),
        "source_documented_multiple_transcriptions": len(multi),
        "documented_ambiguity_examples": multi,
        "records_containing_literal_schwa_phone": sum(ORTHOGRAPHIC_SCHWA_TOKEN in r.phones for r in rows),
        "schwa_phone_tokens": sum(r.phones.count(ORTHOGRAPHIC_SCHWA_TOKEN) for r in rows),
        "hypothetical_single_deletion_probes": len(probes),
        "externally_verified_alternative_sung_pronunciations": 0,
        "independently_verified_syllable_boundaries": 0,
        "verified_lyric_taal_alignments": 0,
    }


def reconcile(excerpt: list[Lexeme], full_source: Path | None) -> dict:
    if full_source is None:
        return {
            "status": "BLOCKED_FULL_UPSTREAM_FILE_UNAVAILABLE",
            "upstream_sha256": None,
            "rows_reconciled": 0,
            "source_url": RAW_UPSTREAM,
        }
    if not full_source.exists() or full_source.is_symlink() or not full_source.is_file():
        raise LexiconError("Full source must be a regular local file, not symlink")
    payload = full_source.read_bytes()
    full = parse_full_lexicon(payload.decode("utf-8-sig"))
    matched = verify_excerpt_against_full(excerpt, full)
    return {
        "status": "SOURCE_LINES_MATCH_FULL_FILE",
        "upstream_sha256": hashlib.sha256(payload).hexdigest(),
        "rows_reconciled": matched["reconciled_rows"],
        "full_source_rows": matched["upstream_rows"],
        "source_url": RAW_UPSTREAM,
        "linguistic_gold_labels_verified": False,
    }


def analyze(excerpt_file: Path, output_dir: Path, full_source: Path | None = None) -> dict:
    if not excerpt_file.is_file():
        raise LexiconError("Source excerpt file missing")
    original = excerpt_file.read_bytes()
    excerpt = parse_source_excerpt(original.decode("utf-8-sig"))
    matched = reconcile(excerpt, full_source)
    counts = inventory(excerpt)
    # Observed phonemic paths in this lexicon do not prove pronunciation variability;
    # even multiple spellings with distinct phones don't certify sung alternatives.
    gate = {
        "status": "NO_GO_EXTERNAL_PRONUNCIATION_RHYTHM_CLAIMS",
        "required": [
            "Independently attested alternative pronunciations for same spelling",
            "Independently attested syllable boundaries for each relevant alternative",
            "Licensed lyric-to-rhythm task labels or clearly limited formal reference tasks",
            "Source-line reconciliation with complete upstream bytes",
            "Prospectively frozen benchmark and baseline selection",
        ],
        "reason": "No sourced sung alternatives, independently sourced syllable boundaries or lyric-to-Taal reference alignments",
        "measured_real_world_false_infeasibility_rate": None,
        "does_not_prevent_formal_computational_experiments": True,
    }
    result = {
        "schema_version": "1.0",
        "upgrade": "17",
        "source_excerpt_sha256": hashlib.sha256(original).hexdigest(),
        "upstream_reconciliation": matched,
        "inventory": counts,
        "research_gate": gate,
        "evidence_boundaries": {
            "original_phones": "EXTERNALLY_SOURCED_TRANSCRIPTION_CANDIDATES_NOT_INDEPENDENTLY_VALIDATED",
            "deletion_probes": "ARTIFICIAL_COUNTERFACTUAL_NOT_ATTESTED_PRONUNCIATIONS",
            "syllable_evidence": "ABSENT",
            "rhythmic_singing_evidence": "ABSENT",
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "UPGRADE_17_EVIDENCE_STATUS.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "UNATTESTED_SCHWA_PROBES.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["upstream_line", "orthography", "deleted_phone_index_0based",
                         "original_phone_sequence", "hypothetical_phone_sequence", "evidence_level"])
        for cf in generate_deletion_probes(excerpt):
            writer.writerow([cf.source_line, cf.orthography, cf.phone_index,
                             " ".join(cf.observed_phones), " ".join(cf.hypothetical_phones), cf.evidence_level])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excerpt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--full-upstream", type=Path,
                        help="Optional independently obtained original upstream lexicon.txt")
    args = parser.parse_args()
    report = analyze(args.excerpt, args.output, args.full_upstream)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
