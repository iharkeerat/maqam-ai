# MAQAM architecture at a glance

The project is composed of two related but separate explorations:

1. **Music-workbench user interface** (`web/`): poetry forms and languages, selectable Raag/Taal knowledge, constraint-aware notation and browser audio previews.
2. **Formal score-alignment module** (`research/score_ingestion`, `research/pronunciation_rhythm`): conservative XML parsing, tie-aware normalization, exact dynamic programming and formal-path ambiguity analysis. This module does not claim genuine pronunciation inference.

The API in `backend/main.py` exposes a constructed formal preview at `POST /research/score/formal-preview`, plus basic health, synthesis and synthetic-baseline research endpoints.

See the checked-in architecture graphic in `assets/architecture.svg` and the [limitations](RESULTS_AND_LIMITATIONS.md).
