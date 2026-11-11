"""Fail-closed external pronunciation evidence intake for MAQAM AI.

Evidence files are *not* shipped. Checks validate structure and bytes, not the
linguistic correctness, rights, or independence of an external label.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_RANGES = {"hi": ((0x0900, 0x097F),), "pa": ((0x0A00, 0x0A7F),)}
ALLOWED_SOURCE_KINDS = {"published_dictionary", "licensed_lexicon", "qualified_review", "model_prediction", "constructed_demo"}
ALLOWED_AUTHORIZATIONS = {"documented_reuse_permission", "public_domain_evidence", "unknown", "not_permitted"}
ALLOWED_VERIFICATIONS = {"cited_dictionary_entry", "independent_reference", "qualified_review", "model_generated", "none"}
SHA256 = re.compile(r"^[a-f0-9]{64}$")


class EvidenceError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def _text(value: Any, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"Missing {label}")
    _require(value == value.strip() and unicodedata.is_normalized("NFC", value), f"{label} must be trimmed NFC")
    _require(not any(unicodedata.category(c) in {"Cc", "Cf"} for c in value), f"{label} contains control or format characters")
    return value


def _safe_evidence_file(filename: str, root: Path) -> Path:
    name = Path(filename)
    _require(bool(filename) and name.name == filename and not name.is_absolute() and "\\" not in filename and filename not in {".", ".."},
             "Evidence file must be a safe basename")
    path = root / filename
    _require(path.is_file() and not path.is_symlink(), "Evidence file is missing or is a symlink")
    _require(path.stat().st_size > 0, "Evidence file is empty")
    return path


def validate_record(record: dict[str, Any], evidence_root: Path) -> dict[str, Any]:
    """Return an auditable status; never equate an attestation with truth."""
    _require(isinstance(record, dict), "Record must be an object")
    required = {"id", "language", "orthography", "source", "pronunciations"}
    _require(required <= record.keys(), "Required record fields missing")
    rid = _text(record["id"], "id")
    language = record["language"]
    _require(language in SCRIPT_RANGES, "Only hi and pa are in scope")
    spelling = _text(record["orthography"], "orthography")
    # Combining marks belong to the same Indic script blocks; whitespace may separate words.
    _require(all(c.isspace() or any(a <= ord(c) <= b for a, b in SCRIPT_RANGES[language])
                 for c in spelling), "Orthography has foreign-script characters")
    _require(any(not c.isspace() for c in spelling), "Empty orthography")
    source = record["source"]
    _require(isinstance(source, dict), "Source must be an object")
    for key in ("source_id", "source_uri", "kind", "authorization", "verification", "evidence_file", "sha256", "locator"):
        _require(key in source, f"Missing source.{key}")
    _text(source["source_id"], "source_id")
    uri = _text(source["source_uri"], "source_uri")
    _require(uri.startswith("https://") or uri.startswith("doi:"), "Use HTTPS or DOI URI")
    _require(source["kind"] in ALLOWED_SOURCE_KINDS, "Unknown source kind")
    _require(source["authorization"] in ALLOWED_AUTHORIZATIONS, "Unknown authorization")
    _require(source["verification"] in ALLOWED_VERIFICATIONS, "Unknown verification")
    _text(source["locator"], "evidence locator")
    digest = source["sha256"]
    _require(isinstance(digest, str) and bool(SHA256.fullmatch(digest)), "Invalid SHA-256")
    path = _safe_evidence_file(source["evidence_file"], evidence_root)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    _require(actual == digest, "Evidence SHA-256 mismatch")
    candidates = record["pronunciations"]
    _require(isinstance(candidates, list) and len(candidates) > 0 and len(candidates) <= 32, "Need 1–32 pronunciations")
    keys = set()
    normalized_paths = set()
    for cand in candidates:
        _require(isinstance(cand, dict), "Pronunciation must be an object")
        key = _text(cand.get("key"), "pronunciation key")
        _require(key not in keys, "Duplicate candidate key")
        keys.add(key)
        ipa = _text(cand.get("ipa"), "IPA transcription")
        syllables = cand.get("syllables")
        _require(isinstance(syllables, list) and bool(syllables) and len(syllables) <= 128, "Invalid syllable list")
        syllables = [_text(s, "syllable") for s in syllables]
        _require(not any(" " in s for s in syllables), "One syllable per field")
        # IPA is an annotation supplied by an external source; do not infer it from orthography.
        _require("".join(syllables).replace(".", "") == ipa.replace(".", ""),
                 "IPA must match concatenated syllables; no auto-correction")
        spelling_path = tuple(syllables)
        _require(spelling_path not in normalized_paths, "Duplicate syllable path")
        normalized_paths.add(spelling_path)
        _text(cand.get("locator"), "pronunciation-specific source locator")
    declared_rights = source["authorization"] in {"documented_reuse_permission", "public_domain_evidence"}
    documented_reference = source["verification"] in {"cited_dictionary_entry", "independent_reference", "qualified_review"}
    not_demo = source["kind"] not in {"model_prediction", "constructed_demo"}
    qualified_for_review = declared_rights and documented_reference and not_demo
    return {"id": rid, "language": language, "candidate_count": len(candidates),
            "source_evidence_sha256": actual, "declared_research_eligible": qualified_for_review,
            "human_or_independent_validation_performed_by_maqam": False,
            "status": "ELIGIBLE_ON_DECLARED_METADATA_ONLY" if qualified_for_review else "QUARANTINED_UNVERIFIED"}


def validate_corpus(records: list[dict[str, Any]], evidence_root: Path) -> dict[str, Any]:
    _require(isinstance(records, list), "Corpus must be a list")
    ids, pair_set = set(), set()
    results = []
    for r in records:
        result = validate_record(r, evidence_root)
        _require(result["id"] not in ids, "Duplicate record id")
        pair = (result["language"], unicodedata.normalize("NFC", r["orthography"]))
        _require(pair not in pair_set, "Duplicate normalized language/orthography")
        pair_set.add(pair)
        ids.add(result["id"])
        results.append(result)
    return {"total_records": len(results), "eligible_on_declaration": sum(x["declared_research_eligible"] for x in results),
            "quarantined": sum(not x["declared_research_eligible"] for x in results),
            "authenticity_independently_confirmed_by_maqam": False, "records": results}


def load_and_validate(corpus_file: Path, evidence_root: Path) -> dict[str, Any]:
    payload = json.loads(corpus_file.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict) and payload.get("schema_version") == "1.0", "Unsupported corpus schema")
    return validate_corpus(payload.get("records"), evidence_root)


def adapt_to_formal_case(record: dict[str, Any], rhythm: dict[str, Any], evidence_root: Path):
    """Construct a *formal alignment task* from attributed syllables.

    Core's `constructed_formal_only` tag stays intact: we deliberately do NOT
    promote evidence claims into validated singing or musically correct labels.
    """
    status = validate_record(record, evidence_root)
    _require(status["declared_research_eligible"], "Unverified source cannot feed evidence track")
    from research.pronunciation_rhythm.core import AlignmentCase, Candidate, RhythmSpec
    rs = RhythmSpec(**rhythm)
    candidates = tuple(Candidate(c["key"], tuple(c["syllables"]), prior=i,
                                 evidence="constructed_formal_only")
                       for i, c in enumerate(record["pronunciations"]))
    return AlignmentCase(record["id"], candidates, rs, provenance="constructed_formal_only")
