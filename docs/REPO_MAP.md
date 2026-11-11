# Repository map — what each file is for

The public repository deliberately contains a curated set of runnable files. It is **not** the full historical private research archive. Some archived notes mention old scripts that are not distributed here.

| Folder / file | Purpose | Good entry point |
|---|---|---|
| `README.md` | Public overview and navigation | [Main README](../README.md) |
| `portfolio_smoke_demo.py` | Reproducible three-chord API example | [Demo](../portfolio_smoke_demo.py) |
| `web/app/` | Next.js pages, notation workbench and alignment lab | [Homepage code](../web/app/page.tsx) · [Alignment lab](../web/app/alignment-lab/page.tsx) |
| `web/app/lib/` | Frontend musicology, formal and semantic modules | [Formal alignment](../web/app/lib/formal-alignment.ts) |
| `web/app/data/` | Bundled Raag/Taal and constructed research data | [Data directory](../web/app/data/) |
| `web/app/api/` | Frontend API endpoints and offline/optional external analysis | [Analysis route](../web/app/api/analyse/route.ts) |
| `backend/main.py` | FastAPI health, synthesis and formal diagnostic endpoints | [API](../backend/main.py) |
| `backend/research.py` | Locally loaded synthetic Raag/Taal baseline artifacts | [Baseline service](../backend/research.py) |
| `engine/` · `backend/synthesis.py` | Basic synthesized audio functions | [Synthesis](../backend/synthesis.py) |
| `research/pronunciation_rhythm/core.py` | Exact DP, constructed formal oracle and witness checks | [Formal core](../research/pronunciation_rhythm/core.py) |
| `research/score_ingestion/` | MSCX parser, tie normalization, score projection, ambiguity checking | [Score module guide](../research/score_ingestion/README.md) |
| `research/` | Additional archived research prototypes and controlled experiments | [Research scope](RESULTS_AND_LIMITATIONS.md) |
| `models/` | Three local serialized baseline artifacts plus a **legacy** metadata registry | [Registry](../models/registry.json) |
| `reports/research/` | Internal experiment summaries; never general musical accuracy | [Controlled baseline note](../reports/research/benchmark_v5/RESULTS_README.md) |
| `tests/` | Fixture-based software tests run in public CI | [CI definition](../.github/workflows/ci.yml) |
| `scripts/` | Small constructed score demos and pinned original-score replay helper | [Demo bridge](../scripts/demo_score_bridge_v7.py) |
| `docs/` | Evidence, limits, verification and reviewer documentation | [Docs index](START_HERE.md) |
| `.github/workflows/ci.yml` | Python demo/tests plus TypeScript lint/typecheck/build | [Workflow](../.github/workflows/ci.yml) |
| `LICENSE` | MIT terms for the included code | [License](../LICENSE) |

## Important completeness notes

1. Historical research notes may mention modules such as `tests/test_pronunciation_rhythm.py`, `scripts/run_competitive_baselines_v5.py`, or `scripts/run_research_suite.py`, which are **not included** in the curated repository. Use the checked-in `tests/`, smoke demo and CI configuration to reproduce the **public snapshot**.
2. `models/registry.json` is research metadata, **not the backend runtime loader**. Its legacy context-model entry was not shipped; `backend/research.py` uses only the shipped `raag_text`, `raag_rules` and `taal_text` artifacts. Do not claim every historical model is included.
3. Raw original OpenScore scores and confidential study materials are not bundled. `scripts/replay_openscore_v7.py` fails closed if authentic files are absent.
4. The screenshot guide describes how to capture **real** local UI screenshots; it does not include fabricated interface imagery.
