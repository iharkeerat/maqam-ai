# Upgrade 16 — Real Hindi lexical evidence (bounded study)

**Date inspected:** 24 October 2026. **Status:** 40-entry, source-indexed, MIT-attributed lexical *excerpt* ingested. Full upstream file NOT packaged. **Not** an independently syllabified, sung, or Punjabi pronunciation benchmark.

## Source and legal audit

1. [Hindi Speech Corpus](https://github.com/aashishyadavally/Hindi-Speech-Corpus) by Aashish Yadavally, MIT licence, copyright 2019. Source lexicon location: [`corpus/lexicon.txt`](https://raw.githubusercontent.com/aashishyadavally/Hindi-Speech-Corpus/master/corpus/lexicon.txt). Source contains **word–phone** transcriptions. Forty entries copied into `lexical_sources/HINDI_LEXICON_SOURCE_EXCERPT.tsv`, retaining upstream 1-based line numbers for independent inspection. This is an **upstream author-supplied lexicon**, not a linguistic ground-truth certification by MAQAM. MIT notice accompanies the excerpt. The upstream branch is mutable: the excerpt's line references must be reconciled with a downloaded snapshot before high-stakes empirical use.
2. [Arora, Gessler, Schneider (ACL 2020)](https://aclanthology.org/2020.acl-main.696/): supervised schwa-deletion for Hindi/Punjabi. [Published code](https://github.com/aryamanarora/schwa-deletion) is a reference and candidate baseline; no data from that repository are redistributed by MAQAM in this release. Github visibility is not permission to redistribute source dictionaries; inspect rights first.
3. [indic-g2p](https://github.com/Bindkushal/indic-g2p), documented as Apache 2.0, contains Hindi and beta Punjabi G2P conversion. Its output would be **model-derived** candidates, not independent pronunciation references. No model-generated outputs are packaged as verified annotations.
4. The [IITM Hindi Speech Corpus](https://github.com/Speech-Lab-IITM/Hindi-ASR-Challenge) has research-only/non-redistribution conditions. It is not copied here.

## Run sample descriptive audit

From the project root:

```bash
python -m research.pronunciation_rhythm.lexical_evidence \
  --source research/pronunciation_rhythm/lexical_sources/HINDI_LEXICON_SOURCE_EXCERPT.tsv \
  --excerpt --output reports/research/pronunciation_lexicon_u16
```

For a legally obtained full upstream `lexicon.txt`, omit `--excerpt`:

```bash
python -m research.pronunciation_rhythm.lexical_evidence \
  --source /path/to/downloaded/lexicon.txt \
  --output reports/research/pronunciation_lexicon_full_u16
```

The full import records SHA-256 of the actual input bytes (the excerpt has a separate SHA-256). **No source SHA-256 is claimed for the full upstream file until it is downloaded locally.** To verify every manually curated source-indexed excerpt line against an independently obtained complete source:

```python
from research.pronunciation_rhythm.lexical_evidence import (
    parse_full_lexicon, parse_source_excerpt, verify_excerpt_against_full)
from pathlib import Path
full = parse_full_lexicon(Path('/path/to/lexicon.txt').read_text(encoding='utf-8'))
excerpt = parse_source_excerpt(Path('research/pronunciation_rhythm/lexical_sources/HINDI_LEXICON_SOURCE_EXCERPT.tsv').read_text(encoding='utf-8'))
print(verify_excerpt_against_full(excerpt, full))
```

If upstream has changed, pin a commit and document the differences rather than silently treating the excerpt as confirmed.

## Explicitly disallowed interpretations

- `lexicon.txt` **does not provide verified syllable boundaries**; its spaces separate phones.
- `phone_vowel_token_proxy` is a *heuristic token counter*, not verified syllable count. It cannot be treated as actual duration or Hindi speech/singing syllabification.
- Zero attested multiple pronunciations in the **40-entry excerpt** says nothing about their prevalence in Hindi generally.
- Exact solver cases from Upgrade 14 remain **constructed** and must not be promoted into authentic aligned music data.
- Musical quality, Raag authenticity and prosodic performance have not been measured.

## Scientific next gate

Obtain or annotate **independently sourced and permission-cleared syllable boundaries and plausible alternate pronunciations**, preferably both languages; validate their source, phonological status and train/test independence. Only then use the formal solver for empirical *pronunciation-to-rhythm* comparisons. If these annotations cannot be obtained under Option A, restrict the publication claim to the formal algorithm and source-aware phoneme analysis.
