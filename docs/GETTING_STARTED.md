# Getting started — run MAQAM AI locally

You can try MAQAM without external AI keys. The easiest demonstration is the Python smoke test; the browser is optional.

## Prerequisites

- **Python 3.11 or later** (the CI uses 3.12).
- **Node.js 22 or later** for the optional web interface (the CI uses 22).
- Git and an internet connection to install dependencies initially. For Windows, PowerShell is fine.

## Route A: Python demonstration

From the repository root (the folder containing `README.md`):

```bash
python -m pip install -r requirements.txt
python portfolio_smoke_demo.py
```

Some systems use `python3` or `py` instead of `python`.

**Expected result:** JSON with `original_notated_chords: 3`, `normalized_events_after_tie_collapse: 2`, and `formal_chord_start_indices: [0, 2]`. It also explicitly sets `real_world_alignment_accuracy_evaluated: false`. Full sample: [`DEMO_OUTPUT.json`](DEMO_OUTPUT.json).

This uses constructed notation to check parser behaviour and the API contract; it does **not** compare predictions with actual human singing.

## Route B: Web interface

In a terminal:

```bash
cd web
npm ci
npm run dev
```

Open `http://localhost:3000`. Pages include:

- `/` — music-workbench overview, Raag/Taal exploration and interactive notation;
- `/alignment-lab` — editable formal alignment comparisons;
- `/research` — clearly labelled internal synthetic research records;
- `/review` — review interface (not proof of a completed external human study).

The built-in offline heuristic does not require a paid API. Optional Gemini features involve third-party API calls **only when a user sets a server-side `GEMINI_API_KEY`**. Do not put keys in public GitHub files. See [`web/.env.example`](../web/.env.example).

## Route C: Optional Python API

From a **second terminal at repository root**:

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for the interactive API schema or `http://localhost:8000/health` to check basic service health. The key formal endpoint is `POST /research/score/formal-preview`. It takes a small MSCX XML string and an **independently supplied** syllable count; it does not infer lyrics from the embedded score reference. Do not upload private music scores to a server you do not control.

## Run tests

```bash
python -m pytest -q tests/
```

From `web/`, frontend checks:

```bash
npm run typecheck
npm run lint
npm run build
```

These check software and constructed formal fixtures. See [Verification](VERIFICATION.md) for the precise claim boundary and CI link.

## Docker Compose (optional / not part of published CI checks)

For an experimental local container build, the project includes `docker-compose.yml`, `web/Dockerfile`, and `backend/Dockerfile`. From repository root, run `docker compose up --build`. This path is **not certified by the published CI**; prefer Routes A–C if container build fails. Never publish local `.env` files.

## Troubleshooting

| Symptom | Check |
|---|---|
| `python` not found | Try `python3` / `py`; install Python 3.11+ |
| `ModuleNotFoundError` | Run commands **from repository root**, then install `requirements.txt` |
| `npm ci` error | Check Node.js 22+, network access and `web/package-lock.json` |
| Port 3000/8000 already used | Stop the existing server; use an available port if needed |
| XML rejected (422) | The parser deliberately rejects unsupported timing, voices or malformed scores |
| A model file is missing | Use the supplied three baseline artifacts; a legacy context-model reference is not a distributable runtime dependency |
| No live website | This repository provides **local** run instructions, not a verified public deployment |

For deeper context see the [repository map](REPO_MAP.md), [architecture](ARCHITECTURE.md) and [limitations](RESULTS_AND_LIMITATIONS.md).
