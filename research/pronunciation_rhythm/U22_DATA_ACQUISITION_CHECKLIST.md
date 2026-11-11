# Upgrade 22 — real external data acquisition checklist

| Dataset | Public description | Material confirmed in this run | Blocking issue | Next concrete action |
|---|---|---|---|---|
| SargamBench, Zenodo DOI 10.5281/zenodo.21904267 | 1,026 lyric–Sargam pairs | Landing page, manifest, README **text only** | Reconstructed release reports all 1,026 lyrics missing; data bytes inaccessible; license unresolved | Fetch `README.md`, `manifest.json`, `pairs.csv`; run the source inspector; request original annotations where applicable |
| IIT Bombay ISMIR 2025 Bhake et al. | Two compositions in two Raags, sung onset and beat-grid analysis | Published PDF methodological description | Data/supplementary CSV acquisition and redistribution rights unresolved | Obtain authors' supplementary annotations or permission for reproducible study |
| Hindi Speech Corpus | Word–phone resources | Existing 40 local excerpted words, not full-source reconciled | No independently verified sung syllables or alternate paths | Independently reconcile full source then obtain genuine alternatives |

**Necessary evidence for MAQAM's proposed scientific hypothesis:** multiple independently attested pronunciations *for the same lyric item*; syllable boundaries; matched lyric–Taal alignments; provenance; documented permissions. One unrelated dataset supplying each column is NOT equivalent to complete same-item gold.

**Access methods attempted:** `requests.get` to Zenodo API and CSV, container download service, and web CSV link (returned 429). All failed in this runtime. Never treat the web-readable README/manifest as downloaded actual examples.
