"""Ranking, classification and calibration metrics."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Sequence

import numpy as np
from sklearn.metrics import f1_score


def reciprocal_rank(accepted: set[str], ranked: Sequence[str]) -> float:
    for index, label in enumerate(ranked, start=1):
        if label in accepted:
            return 1.0 / index
    return 0.0


def expected_calibration_error(confidences: Sequence[float], correct: Sequence[bool], bins: int = 10) -> tuple[float, list[dict[str, float | int]]]:
    conf = np.asarray(confidences, dtype=float)
    hits = np.asarray(correct, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    details: list[dict[str, float | int]] = []
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        mask = (conf >= lower) & (conf <= upper if index == bins - 1 else conf < upper)
        count = int(mask.sum())
        if not count:
            details.append({"lower": round(float(lower), 3), "upper": round(float(upper), 3), "count": 0, "confidence": 0.0, "accuracy": 0.0})
            continue
        avg_conf = float(conf[mask].mean())
        accuracy = float(hits[mask].mean())
        ece += (count / max(1, len(conf))) * abs(avg_conf - accuracy)
        details.append({"lower": round(float(lower), 3), "upper": round(float(upper), 3), "count": count, "confidence": round(avg_conf, 4), "accuracy": round(accuracy, 4)})
    return float(ece), details


def multiclass_brier(probabilities: np.ndarray, labels: Sequence[str], class_order: Sequence[str]) -> float:
    index = {label: i for i, label in enumerate(class_order)}
    truth = np.zeros_like(probabilities)
    for row, label in enumerate(labels):
        truth[row, index[label]] = 1.0
    return float(np.mean(np.sum((probabilities - truth) ** 2, axis=1)))


def evaluate_rankings(
    primary_labels: Sequence[str],
    accepted_sets: Sequence[set[str]],
    ranked_predictions: Sequence[Sequence[str]],
    probabilities: np.ndarray,
    class_order: Sequence[str],
    languages: Sequence[str],
) -> dict[str, object]:
    top1 = [ranked[0] for ranked in ranked_predictions]
    top1_hits = [prediction in accepted for prediction, accepted in zip(top1, accepted_sets)]
    top3_hits = [bool(set(ranked[:3]).intersection(accepted)) for ranked, accepted in zip(ranked_predictions, accepted_sets)]
    primary_top1 = [prediction == truth for prediction, truth in zip(top1, primary_labels)]
    primary_top3 = [truth in ranked[:3] for truth, ranked in zip(primary_labels, ranked_predictions)]
    mrr = [reciprocal_rank(accepted, ranked) for accepted, ranked in zip(accepted_sets, ranked_predictions)]
    confidences = [float(probabilities[row, class_order.index(top1[row])]) for row in range(len(top1))]
    ece, bins = expected_calibration_error(confidences, top1_hits)
    per_language: dict[str, dict[str, float | int]] = {}
    for language in sorted(set(languages)):
        indices = [i for i, item in enumerate(languages) if item == language]
        per_language[language] = {
            "items": len(indices),
            "top1Agreement": round(sum(top1_hits[i] for i in indices) / len(indices), 4),
            "top3Agreement": round(sum(top3_hits[i] for i in indices) / len(indices), 4),
            "mrr": round(sum(mrr[i] for i in indices) / len(indices), 4),
        }
    return {
        "items": len(primary_labels),
        "top1Agreement": round(float(np.mean(top1_hits)), 4),
        "top3Agreement": round(float(np.mean(top3_hits)), 4),
        "primaryTop1Accuracy": round(float(np.mean(primary_top1)), 4),
        "primaryTop3Recall": round(float(np.mean(primary_top3)), 4),
        "meanReciprocalRank": round(float(np.mean(mrr)), 4),
        "macroF1PrimaryLabel": round(float(f1_score(primary_labels, top1, average="macro", zero_division=0)), 4),
        "expectedCalibrationError": round(ece, 4),
        "multiclassBrier": round(multiclass_brier(probabilities, primary_labels, class_order), 4),
        "perLanguage": per_language,
        "calibrationBins": bins,
    }


def confusion_pairs(primary: Sequence[str], ranked: Sequence[Sequence[str]], accepted_sets: Sequence[set[str]], limit: int = 20) -> list[dict[str, object]]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for truth, prediction, accepted in zip(primary, ranked, accepted_sets):
        if prediction[0] not in accepted:
            counts[(truth, prediction[0])] += 1
    return [
        {"expectedPrimary": truth, "predicted": pred, "count": count}
        for (truth, pred), count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]
