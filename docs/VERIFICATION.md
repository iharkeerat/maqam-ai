# MAQAM AI — verification record

**Public portfolio snapshot:** 11 November 2026. Always inspect the [current GitHub Actions workflow](../.github/workflows/ci.yml) for updated outcomes.

## Verified directly on GitHub

The public repository's [successful run 43028435167](https://github.com/iharkeerat/maqam-ai/actions/runs/43028435167) completed on 11 November 2026. The **Python demo/tests job** and the **frontend job** both passed. The frontend job ran `npm ci`, TypeScript typechecking, ESLint and `next build` on Node 22. The Python job installed the pinned public requirements, ran `portfolio_smoke_demo.py` and executed the seven named score/formal test modules.

A prior local fresh-extraction check of the curated source reported **76 fixture-based tests passing** and a passing API demo. This is an engineering result, not an independently annotated music benchmark.

## How to reproduce

```bash
python -m pip install -r requirements.txt
python portfolio_smoke_demo.py
python -m pytest -q \\
  tests/test_score_ingestion_v7.py \\
  tests/test_score_formal_preview_api_v7.py \\
  tests/test_score_timing_integrity_gate_v10.py \\
  tests/test_score_timing_api_gate_v10.py \\
  tests/test_score_identifiability_v8.py \\
  tests/test_locked_identifiability_v10.py \\
  tests/test_pointer_cache_api_v9.py
```

And for the frontend:

```bash
cd web
npm ci
npm run typecheck
npm run lint
npm run build
```

## Scope of evidence

**Demonstrated:** selected constructed-note parsing, validated tie-chain collapse, formal DP correctness within supplied constraints, response sanitization, rejection of unsafe/ambiguous XML, source-index mapping and internal ambiguity checks. **Not demonstrated:** external lyric-to-note accuracy, artist agreement, sung phonology, broad arbitrary polyphony, a deployed website, Docker Compose end-to-end success or top-journal novelty.

The smoke demo's expected output is in [`DEMO_OUTPUT.json`](DEMO_OUTPUT.json). The original OpenScore files were inspected through connected GitHub sources in earlier exploratory research, but were **not locally replayed through the complete Python adapter in this public CI run**.
