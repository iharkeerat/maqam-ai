# Upgrade 21 — Source-matched independent evaluation readiness

**Date:** 24 October 2026. **Status:** Discovery and formal audit; not a real-data performance result.

## Newly cross-checked external evidence

- Hindi Speech Corpus (MIT repository statement) provides word–phone sequences, not syllabified sung lyrics. The versioned 40-row excerpt has not been reconciled to the full upstream file. https://github.com/aashishyadavally/Hindi-Speech-Corpus
- Arora, Gessler & Schneider (ACL 2020) support schwa-deletion modelling for Hindi and Punjabi; a generated alternate is not an independent observed pronunciation. https://aclanthology.org/2020.acl-main.696/
- SargamBench (Zenodo, 2026) reports 1,026 syllable-level lyric–Sargam pairs in Hindi, Sanskrit and Bengali, **without Taal annotations**. https://zenodo.org/records/21904267
- IIT Bombay's 2025 expressive-timing study describes 2,041 annotated sung syllable onsets in 14 recordings by eight singers, with Teentaal beat placement. Underlying annotation files and reuse permissions are not in this release. https://www.ee.iitb.ac.in/course/~daplab/publications/2025/Expressive%20Timing%20in%20Hindustani%20Vocal%20Music.pdf
- CompMusic Hindustani Rhythm Dataset has manually annotated Taal-cycle positions, but no same-performance lexical alternatives are established by its public description. https://compmusic.upf.edu/ta/hindustani-rhythm-dataset

## Claim-to-data distinction

SargamBench is an externally reported lyric–**melody** alignment source. The IIT Bombay study is an externally reported lyric–**rhythm** timing source. They do not combine into a single ground-truth item because the performances and annotations are not co-indexed.

The decisive proposed hypothesis, 'preserving naturally attested Hindi/Punjabi pronunciation alternatives improves sung lyric-to-Taal alignment', requires **same-item attested variants, independently defensible syllable boundaries, and a reference rhythm alignment**. None are together in the present project.

## Data acquisition and preregistration milestones

1. Verify source-level rights and obtain original bytes; record immutable SHA-256 hashes and exact upstream release IDs. No third-party corpus copied into this release.
2. Audit annotation units and cross-references before selecting metrics. SargamBench can support lyric–melody sequence tests; it cannot provide real Taal-onset gold.
3. When the IIT Bombay timing annotations are legitimately accessible, independently inspect same-syllable event IDs, onset times, and Taal beat positions. They may support a **separate** lyric–Taal alignment benchmark, not pronunciation ambiguity.
4. Identify separate documented alternative pronunciations for the **same** orthographic item, adjudicate linguistic validity, and ensure no development benchmark leakage. If this is unavailable, retain a formal-only paper instead of claiming real speech improvement.
5. Freeze an eligible corpus version, split by composition/recording/source, preregister baselines and thresholds, then evaluate once. Include exact Top-1, Top-K, exhaustive and bounded methods, with correct INCOMPLETE status.
6. Do not automatically promote provenance metadata into scientific ground truth. Corpus access, permitted redistribution, verified spellings, syllable boundaries and real sung timing are separate checks.

## Final gate

**NO-GO** for real-world pronunciation–rhythm superiority. **GO** for continued source-acquisition and formal-evaluation tooling. **Not a novel algorithm claim.**
