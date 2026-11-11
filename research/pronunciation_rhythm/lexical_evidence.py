"""Evidence-isolated Hindi word/phone lexicon import and descriptive diagnostics.

License: MAQAM original code; example lexical rows separately credited to
Hindi-Speech-Corpus (MIT). This module NEVER supplies verified syllable cuts.

The phoneme lexicon is a third-party transcription source, not independent
proof of observed pronunciations or singing behavior.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

UPSTREAM = "https://github.com/aashishyadavally/Hindi-Speech-Corpus"
RAW_UPSTREAM = "https://raw.githubusercontent.com/aashishyadavally/Hindi-Speech-Corpus/master/corpus/lexicon.txt"
LANGUAGE = "hi"
# Purposefully conservative *token* heuristic, not an IPA syllabifier.
NUCLEUS_START = tuple("aeiouəɛɔɪʊɐɑɒᴔᴂ")
SEPARATOR = re.compile(r"^(\S+)\s{2,}(.+?)\s*$")
VALID_PHONE = re.compile(r"^[^\s\x00-\x1f\x7f]+$")


class LexiconError(ValueError):
    pass


@dataclass(frozen=True)
class Lexeme:
    source_line: int
    orthography: str
    phones: tuple[str, ...]


def _validate_word(word: str) -> None:
    if not word or not unicodedata.is_normalized("NFC", word):
        raise LexiconError("Orthography must be non-empty NFC")
    if any(not 0x0900 <= ord(ch) <= 0x097F for ch in word):
        raise LexiconError("Non-Devanagari character in Hindi lexical item")
    if any(unicodedata.category(ch) == "Cf" for ch in word):
        raise LexiconError("Invisible format character in orthography")


def _validate_phones(phones: tuple[str, ...]) -> None:
    if not phones or any(not VALID_PHONE.fullmatch(p) for p in phones):
        raise LexiconError("Empty or malformed phone token")
    # Flag mistaken syllable segmentation: source transcriptions are space-separated phones.
    if any("." in p or "|" in p or "/" in p for p in phones):
        raise LexiconError("Ambiguous phone-delimiter format; manual inspection required")


def parse_full_lexicon(text: str) -> list[Lexeme]:
    """Read the upstream word<2+ spaces>phone1 phone2 ... format.

    Does NOT transform phones into IPA-standardized or syllabified data.
    """
    rows: list[Lexeme] = []
    if not text.strip():
        raise LexiconError("Empty lexicon")
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        match = SEPARATOR.fullmatch(line)
        if match is None:
            raise LexiconError(f"Line {index}: missing wide whitespace separator")
        word, transcript = match.groups()
        _validate_word(word)
        phones = tuple(transcript.split())
        _validate_phones(phones)
        rows.append(Lexeme(index, word, phones))
    if not rows:
        raise LexiconError("No lexical entries")
    return rows


def parse_source_excerpt(text: str) -> list[Lexeme]:
    """Version-controlled selected samples: upstream 1-based line<TAB>word<TAB>phones.

    Line indices refer to the upstream master URL as inspected 2026-10-24.
    This snapshot does not imply the upstream branch will remain unchanged.
    """
    rows: list[Lexeme] = []
    used_lines: set[int] = set()
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise LexiconError(f"Excerpt row {index}: three tab columns required")
        try:
            source_line = int(parts[0])
        except ValueError as exc:
            raise LexiconError("Invalid upstream line reference") from exc
        if source_line < 1 or source_line in used_lines:
            raise LexiconError("Duplicate or invalid upstream line number")
        used_lines.add(source_line)
        word = parts[1]
        _validate_word(word)
        phones = tuple(parts[2].split())
        _validate_phones(phones)
        rows.append(Lexeme(source_line, word, phones))
    if not rows:
        raise LexiconError("No excerpt entries")
    return rows


def verify_excerpt_against_full(excerpt: list[Lexeme], full: list[Lexeme]) -> dict:
    """Check *every* source line against a separately acquired upstream lexicon.

    Protects against transcription mistakes, stale branches and fabricated lines.
    Aborts if any selected original line, orthography, or phone string differs.
    """
    if not excerpt or not full:
        raise LexiconError("Both excerpt and acquired full source required")
    by_line = {record.source_line: record for record in full}
    mismatched = []
    for record in excerpt:
        actual = by_line.get(record.source_line)
        if actual is None or actual.orthography != record.orthography or actual.phones != record.phones:
            mismatched.append(record.source_line)
    if mismatched:
        raise LexiconError("Excerpt disagrees with downloaded upstream on lines: " + ",".join(map(str, mismatched)))
    return {"reconciled_rows": len(excerpt), "upstream_rows": len(full),
            "status": "SOURCE_LINES_MATCH_FULL_FILE", "phonological_validity_checked": False}


def phone_vowel_nuclei_proxy(phones: tuple[str, ...]) -> int:
    """Count vowel-initial tokens; NOT confirmed syllabic segmentation.

    Outputs can differ from actual syllable counts (diphthongs, vocalic liquids,
    coalescence, singing elision, and source-inventory conventions).
    """
    _validate_phones(phones)
    count = 0
    for phone in phones:
        if phone.startswith(NUCLEUS_START) or phone.startswith("r̥"):
            count += 1
    return count


def audit_lexicon(rows: list[Lexeme], raw_sha: str, source_type: str, source_url: str) -> dict:
    if not rows or len(raw_sha) != 64 or not re.fullmatch(r"[0-9a-f]{64}", raw_sha):
        raise LexiconError("Invalid audit input or SHA256")
    seen: dict[str, set[tuple[str, ...]]] = {}
    zero_nuclei = []
    duplicates = []
    for row in rows:
        found = seen.setdefault(row.orthography, set())
        if row.phones in found:
            duplicates.append(row.source_line)
        found.add(row.phones)
        if phone_vowel_nuclei_proxy(row.phones) == 0:
            zero_nuclei.append(row.source_line)
    multivariant = {word: len(paths) for word, paths in sorted(seen.items()) if len(paths) > 1}
    return {
        "status": "DESCRIPTIVE_EXTERNAL_LEXICON_AUDIT_ONLY",
        "source_type": source_type,
        "source_url": source_url,
        "source_file_sha256": raw_sha,
        "source_license_statement": "GitHub upstream README claims MIT; redistribution subject to license compliance",
        "lexical_rows": len(rows),
        "unique_spelling_count": len(seen),
        "identical_duplicate_line_count": len(duplicates),
        "identical_duplicate_lines": duplicates,
        "spelling_with_multiple_transcriptions_count": len(multivariant),
        "multiple_transcriptions_by_spelling": multivariant,
        "phone_nuclei_proxy_zero_count": len(zero_nuclei),
        "phone_nuclei_proxy_zero_lines": zero_nuclei,
        "independent_syllable_boundaries": 0,
        "verified_sung_pronunciations": 0,
        "confirmed_rhythm_alignment_pairs": 0,
        "real_world_false_infeasibility_rate": None,
        "warnings": [
            "Source data lists word-to-phone transcriptions, not syllable boundaries.",
            "Phone vowel-token counts are an exploratory proxy, not a validated syllable count.",
            "No source variant is assumed to be equally valid in speech or song.",
            "The source transcript and source rights are third-party statements, not independently verified by MAQAM.",
        ],
    }


def write_audit(source: Path, output: Path, *, excerpt: bool) -> dict:
    data = source.read_bytes()
    text = data.decode("utf-8-sig")
    rows = parse_source_excerpt(text) if excerpt else parse_full_lexicon(text)
    sha = hashlib.sha256(data).hexdigest()
    report = audit_lexicon(rows, sha, "curated_upstream_excerpt" if excerpt else "upstream_full_lexicon", RAW_UPSTREAM)
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "LEXICON_AUDIT.json"
    manifest.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with (output / "PHONE_SEQUENCE_DIAGNOSTICS.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(("upstream_line", "orthography", "phone_tokens", "phone_vowel_token_proxy", "has_syllable_boundaries"))
        for r in rows:
            writer.writerow((r.source_line, r.orthography, len(r.phones), phone_vowel_nuclei_proxy(r.phones), "NO"))
    return report


def assert_no_implicit_syllabification(rows: list[Lexeme]) -> None:
    """Explicit fail-closed boundary between phone evidence and the formal solver."""
    if rows:
        raise LexiconError("Word/phone lexicon is NOT a syllabified singing corpus; alignment adapter blocked")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--excerpt", action="store_true", help="Read manually sourced upstream-indexed TSV excerpt")
    a = p.parse_args()
    print(json.dumps(write_audit(a.source, a.output, excerpt=a.excerpt), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
