"""Local inference service for reproducible MAQAM research baselines."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
SUMMARY = ROOT / "reports/research/experiment_summary.json"


@lru_cache(maxsize=1)
def _load_artifacts() -> dict[str, Any]:
    required = {
        "raag_text": MODELS / "raag_text_baseline_v1.joblib",
        "raag_rules": MODELS / "raag_rule_baseline_v1.joblib",
        "taal_text": MODELS / "taal_text_baseline_v1.joblib",
    }
    missing = [str(path.relative_to(ROOT)) for path in required.values() if not path.exists()]
    if missing:
        raise RuntimeError(f"Research model artifacts are missing: {', '.join(missing)}")
    return {key: joblib.load(path) for key, path in required.items()}


def _align(probabilities: np.ndarray, source: list[str], target: list[str]) -> np.ndarray:
    output = np.zeros((probabilities.shape[0], len(target)), dtype=float)
    target_index = {label: index for index, label in enumerate(target)}
    for index, label in enumerate(source):
        if label in target_index:
            output[:, target_index[label]] = probabilities[:, index]
    output /= np.maximum(output.sum(axis=1, keepdims=True), 1e-12)
    return output


def _rank(probabilities: np.ndarray, classes: list[str], top_k: int) -> list[dict[str, float | str]]:
    row = probabilities[0]
    return [
        {"id": classes[index], "score": round(float(row[index]), 6)}
        for index in np.argsort(row)[::-1][:top_k]
    ]


def predict(poetry: str, language: str = "unknown", form: str = "unknown", time_hint: str = "unknown", top_k: int = 5) -> dict[str, object]:
    artifacts = _load_artifacts()
    top_k = max(1, min(10, top_k))

    text_artifact = artifacts["raag_text"]
    text_pipeline = text_artifact["pipeline"]
    raag_classes = list(text_artifact["classes"])
    text_raw = text_pipeline.predict_proba([poetry])
    text_proba = _align(text_raw, list(text_pipeline.named_steps["classifier"].classes_), raag_classes)

    rule_artifact = artifacts["raag_rules"]
    rule_ranker = rule_artifact["ranker"]
    rule_raw = rule_ranker.predict_proba([poetry])
    rule_proba = _align(rule_raw, list(rule_ranker.classes_), raag_classes)
    hybrid = 0.72 * text_proba + 0.28 * rule_proba
    hybrid /= hybrid.sum(axis=1, keepdims=True)

    taal_artifact = artifacts["taal_text"]
    taal_pipeline = taal_artifact["pipeline"]
    taal_classes = list(taal_artifact["classes"])
    context_text = f"{poetry}\n[FORM={form}] [TIME={time_hint}] [LANG={language}]"
    taal_raw = taal_pipeline.predict_proba([context_text])
    taal_proba = _align(taal_raw, list(taal_pipeline.named_steps["classifier"].classes_), taal_classes)

    return {
        "researchStatus": "internal-baseline-not-expert-validated",
        "raagTextBaseline": _rank(text_proba, raag_classes, top_k),
        "raagHybrid": _rank(hybrid, raag_classes, top_k),
        "taalBaseline": _rank(taal_proba, taal_classes, top_k),
        "modelVersions": {
            "raagText": text_artifact["version"],
            "raagRules": rule_artifact["version"],
            "taalText": taal_artifact["version"],
        },
        "warning": "Scores are model ranking values trained on a synthetic seed benchmark. They are not expert agreement probabilities.",
    }


def metrics() -> dict[str, object]:
    if not SUMMARY.exists():
        return {"status": "missing", "message": "Run python scripts/run_research_suite.py --rebuild-data"}
    return json.loads(SUMMARY.read_text(encoding="utf-8"))
