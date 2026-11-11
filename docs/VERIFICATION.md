# Verification notes — portfolio snapshot (11 November 2026)

The following was executed locally against this **curated public repository**, not a private full research archive:

```bash
python portfolio_smoke_demo.py
python -m pytest -o addopts='' -q \
  tests/test_score_ingestion_v7.py \
  tests/test_score_formal_preview_api_v7.py \
  tests/test_score_timing_integrity_gate_v10.py \
  tests/test_score_timing_api_gate_v10.py \
  tests/test_score_identifiability_v8.py \
  tests/test_locked_identifiability_v10.py \
  tests/test_pointer_cache_api_v9.py
```

**Result:** 76 passed in 1.55 seconds; API demonstration completed successfully. An example of the output is in `DEMO_OUTPUT.json`.

**Scope:** Tests use constructed XML fixtures and finite formal cases. They verify API behaviour, correctness within explicitly specified rules and rejection of ambiguous score timing. They do not measure real-world lyric-to-note accuracy.

**Not tested here:** the complete Next.js build in this restricted environment (frontend CI is configured to check it after publishing), independent musician agreement, audio/sung lyric alignment or raw replay of original OpenScore `.mscx` bytes through local Python.

No deployment link or hosted demo is claimed until a deployment is actually operational.
