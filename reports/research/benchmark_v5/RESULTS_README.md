# Upgrade 12 — Local competitive baseline study (v5)

**Research scope:** controlled *local* comparison on 48 synthetic, previously examined examples.
The result is NOT confirmation of musical validity, superiority to commercial AI, or transfer to genuine poetry.

Development-selected arm (pre-test for this rerun): **time-majority-rule**.
| Baseline | Dev agreement | Test agreement | Test macro F1 | Time metadata flip |
|---|---:|---:|---:|---:|
| majority-prior | 25.0% | 25.0% | 0.100 | 0.0% |
| time-majority-rule | 50.0% | 50.0% | 0.375 | 100.0% |
| word-tfidf-logreg | 25.0% | 25.0% | 0.241 | 0.0% |
| char-tfidf-logreg | 10.4% | 25.0% | 0.249 | 0.0% |
| char-tfidf-linear-svm | 10.4% | 27.1% | 0.252 | 0.0% |
| char-count-complement-nb | 14.6% | 20.8% | 0.205 | 0.0% |
| char-plus-metadata-logreg | 29.2% | 41.7% | 0.411 | 100.0% |
| metadata-only-logreg | 50.0% | 50.0% | 0.375 | 100.0% |

## Appropriate interpretation

These are **exploratory internal controls**, not a rigorous contest against ChatGPT/Gemini/Suno.
The metadata-swap metric indicates prediction sensitivity, not necessarily an error.
Three deterministic shuffled-label controls are reported in experiment_summary_v5.json; these are NOT formal significance tests.
Model selection within this run is based on development data, but the test dataset was analyzed earlier.
Do not choose claims or hyperparameters by these retrospective test outcomes and call them confirmatory.

## External LLM evaluation (not executed)

- `external_llm_prompts_NO_GOLD.csv` contains blinded item prompts with no gold label.
- `external_llm_responses_TEMPLATE.csv` contains empty prediction cells and must be completed with genuine outputs.
- `python scripts/run_competitive_baselines_v5.py --score-external PATH` validates exact item coverage and allowed labels.
- Record model/version, date, API or UI, prompt, settings, failures and response provenance separately; CSV scoring alone cannot authenticate them.
- Any comparison remains on a retrospectively examined **synthetic Rasa classification** task, not musical aptitude.
