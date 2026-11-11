# Upgrade 23 — external performance annotation acquisition

**Status (24 October 2026): external annotation files NOT ACQUIRED.**

## What was verified

- Bhake and Rao, *Expressive Timing in Hindustani Vocal Music* (2025),
  https://www.ee.iitb.ac.in/course/~daplab/publications/2025/Expressive%20Timing%20in%20Hindustani%20Vocal%20Music.pdf,
  describe manual annotations of 2,041 syllable onsets in 14 recordings, eight artists, Teentaal. The PDF cites
  supplementary material at https://rb.gy/20whap (reference [5]). The short URL was inaccessible from our tools.
- Bhake, Anand, and Rao, *Melodic and Metrical Elements of Expressiveness in Hindustani Vocal Music*,
  ISMIR 2025, https://www.ee.iitb.ac.in/course/~daplab/publications/2025/YB_AA_PR_ISMIR2025.pdf,
  reports manually corrected lyric-to-audio syllable alignment under a Teentaal grid and **already uses expected
  pronunciation variations to prompt a speech model**. This directly limits novelty claims about considering
  pronunciation alternatives in Hindustani alignment.
- SargamBench, https://zenodo.org/records/21904267, is described as a lyric–Sargam dataset. The downloadable
  README says its reconstructed release has blank lyric fields and missing original token-level lyrics.
  It is not eligible as verified lyric–melody gold in this release.
- Saraga, https://mtg.github.io/saraga/, has genuine rhythm/sama and melodic phrase annotations but does not
  establish same-item alternative sung pronunciation annotations. Do not merge unrelated tracks.

## Where acquisition stands

- Publication and supplement references: IDENTIFIED.
- An original author-supplied annotation CSV, audio-linked event labels, and its distribution rights: NOT CONFIRMED.
- No downloaded recording/onset data have been included in this ZIP.
- User-contactable authors are publicly listed on the research paper; obtain the supplementary folder and
  explicit reuse permission if the inaccessible short URL remains unavailable.

## Intake specifications and what they mean

New `performance_u23.py` audits a user-supplied external *CSV export* containing:
`recording_id,cycle_id,event_id,onset_seconds,cycle_start_seconds,beat_seconds,beat_index,cycle_beats`.
These columns are **MAQAM's proposed interchange schema, not a verified description of the IITB supplementary files**.
An authorized import would require an explicit mapping from the original annotation schema, preserved original files,
recording identifiers and cross-checked timebases. Do not infer onsets from graphs or guess time stamps.

Provide `provenance.json` with `schema`, `source_kind`, `data_filename`, `data_sha256`,
`reference_url`, `annotation_procedure`, `license_assessment`, and `provenance_note`.
A checksum validates local integrity, not the truth of a claimed provenance. Even imported data are marked as
requiring independent provenance and rights review. The tool computes only descriptive beat-offset statistics,
not pronunciation accuracy, composition authenticity, or a claim of novel algorithmic superiority.

Run from project root:

```bash
python scripts/audit_performance_u23.py --source-dir research/pronunciation_rhythm/u23_example_only --out /tmp/u23_demo.json
```

The included example is synthetic and must produce status `SYNTHETIC_FIXTURE_NOT_EXTERNAL_EVIDENCE`.

## Author-data request (draft; do not claim sent)

Subject: Research-data access request — Hindustani vocal expressive timing annotations

Dear researchers,

I am working on an undergraduate computational music research prototype studying
lyric syllable placement and formal rhythm constraints. I read your 2025 work on
expressive timing in Hindustani vocal music and would be grateful to know whether the
syllable-onset and Teentaal-grid annotations, with associated identifiers and usage
conditions, are available for noncommercial research. The supplementary link cited in
the earlier paper was inaccessible in my environment. I would acknowledge the dataset
and respect any access or redistribution restrictions.

Kind regards

**Research scope**: The acquired data, if available, could support evaluation of onset-to-beat timing.
Neither paper establishes the independent multiple-pronunciation labels needed to evaluate our main
*delayed-pronunciation-commitment* hypothesis. A separate pronunciation ground truth remains necessary.
