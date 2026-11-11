# Upgrade 15: externally evidenced pronunciation intake (v12.1.0)

**Research status:** Implemented fail-closed evidence intake. **Zero genuine pronunciation records or verified Hindi/Punjabi examples** are bundled in this release. No claims of automatically resolved schwa deletion, accurate G2P or real singing alignment.

## Verified starting points

- Arora, Gessler & Schneider (ACL 2020), *Supervised Grapheme-to-Phoneme Conversion of Orthographic Schwas in Hindi and Punjabi*: https://aclanthology.org/2020.acl-main.696/ ; authors' code/data https://github.com/aryamanarora/schwa-deletion
- Hindi Speech Corpus: https://github.com/aashishyadavally/Hindi-Speech-Corpus (includes word/phoneme lexicon; inspect item-level rights).
- Indic-g2p open project: https://github.com/Bindkushal/indic-g2p (Punjabi support described as beta; not validated here).

These are candidate **sources**, not datasets ingested or independently validated by this release. Inspect versions, underlying lexicon licenses, sampling, phonemic transcription conventions and file redistribution rights *before* adding anything.

## Intake steps

1. Acquire material legally from its source. Keep original evidence outside the public repository in a folder of read-only files. Verify the actual license and attribution requirements manually.
2. For each word create a record using `evidence_sources/EXTERNAL_CORPUS_TEMPLATE.json`. Use only original, source-transcribed pronunciation and **explicit externally supported** syllable boundaries. Do not invent schwa alternatives to fill multiple paths.
3. Store evidence as a single basename under your evidence folder and populate SHA-256 (`sha256sum evidence.pdf`). `locator` must identify the supporting record; cryptographic fingerprints merely detect file changes, not truth.
4. Run `python scripts/validate_pronunciation_evidence.py --corpus CORPUS.json --evidence-root PROOF_DIR --output OUT.json` from project root.
5. `eligible_on_declaration` means the supplied metadata is structurally eligible; it **does not** mean MAQAM verified a dictionary's accuracy, permissions or any research participant consent.
6. Before any evaluation: resolve syllabification conventions, manuscript version, pronunciation variants, dialect, lexical ambiguity and data split unit, and obtain genuinely independent gold references.

## Important boundaries

- Preserve baseline `research/pronunciation_rhythm/core.py`. The adapter can convert documented IPA syllables into **formal tokens** so existing solvers can be tested. Results describe the formal constraint problem, **not a verified Taal or natural singing arrangement**.
- The validator rejects missing/corrupted/unsafe evidence files, duplicated paths, non-NFC text and invalid script mixing. `constructed_demo` and `model_prediction` cannot enter the evidence-eligible path merely by setting a permissions flag.
- No network access or automatic corpus download is required; this supports manual, rights-aware future import.
- If a source has only phoneme strings and does not specify syllable divisions, it is **not** ground truth for syllable segmentation. Do not assume a syllabifier's prediction is a gold annotation.
- This upgrade **does not yet provide enough external data to estimate false infeasibility rates on authentic lyrics**.
