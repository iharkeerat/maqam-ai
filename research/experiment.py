"""Train baselines, evaluate a hybrid reranker and generate research artefacts."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from research.metrics import confusion_pairs, evaluate_rankings
from research.rule_ranker import PrototypeRuleRanker


@dataclass
class Dataset:
    rows: list[dict[str, str]]

    def split(self, name: str) -> list[dict[str, str]]:
        return [row for row in self.rows if row["split"] == name]


def read_dataset(path: Path) -> Dataset:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return Dataset(list(csv.DictReader(handle)))


def model_text(row: dict[str, str], include_context: bool = True) -> str:
    text = row["poem"]
    if include_context:
        text += f"\n[FORM={row['form']}] [TIME={row['time_hint']}] [LANG={row['language']}]"
    return text


def build_word_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=2, max_features=18_000, sublinear_tf=True)),
        ("classifier", LogisticRegression(max_iter=2400, class_weight="balanced", C=3.0)),
    ])


def build_char_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", lowercase=True, ngram_range=(3, 5), min_df=2, max_features=32_000, sublinear_tf=True)),
        ("classifier", LogisticRegression(max_iter=2600, class_weight="balanced", C=4.0)),
    ])



def temperature_scale(probabilities: np.ndarray, temperature: float) -> np.ndarray:
    logits = np.log(np.clip(probabilities, 1e-12, 1.0)) / max(temperature, 1e-4)
    logits -= logits.max(axis=1, keepdims=True)
    exp = np.exp(logits)
    return exp / exp.sum(axis=1, keepdims=True)


def choose_temperature(probabilities: np.ndarray, labels: list[str], classes: list[str]) -> float:
    class_index = {label: index for index, label in enumerate(classes)}
    target = np.array([class_index[label] for label in labels], dtype=int)
    best_temperature, best_nll = 1.0, float("inf")
    for temperature in np.linspace(0.2, 2.5, 47):
        calibrated = temperature_scale(probabilities, float(temperature))
        nll = -float(np.mean(np.log(np.clip(calibrated[np.arange(len(target)), target], 1e-12, 1.0))))
        if nll < best_nll:
            best_temperature, best_nll = float(temperature), nll
    return best_temperature


def align_probabilities(probabilities: np.ndarray, source_classes: list[str], target_classes: list[str]) -> np.ndarray:
    aligned = np.zeros((probabilities.shape[0], len(target_classes)), dtype=float)
    target_index = {label: index for index, label in enumerate(target_classes)}
    for source_index, label in enumerate(source_classes):
        if label in target_index:
            aligned[:, target_index[label]] = probabilities[:, source_index]
    sums = aligned.sum(axis=1, keepdims=True)
    return aligned / np.maximum(sums, 1e-12)


def ranked_from_probabilities(probabilities: np.ndarray, classes: list[str]) -> list[list[str]]:
    return [[classes[index] for index in np.argsort(row)[::-1]] for row in probabilities]


def score_model(name: str, probabilities: np.ndarray, classes: list[str], test_rows: list[dict[str, str]]) -> dict[str, object]:
    accepted = [set(value.strip() for value in row["accepted_raags"].split(";") if value.strip()) for row in test_rows]
    ranked = ranked_from_probabilities(probabilities, classes)
    metrics = evaluate_rankings(
        [row["primary_raag"] for row in test_rows],
        accepted,
        ranked,
        probabilities,
        classes,
        [row["language"] for row in test_rows],
    )
    metrics["model"] = name
    metrics["confusionPairs"] = confusion_pairs([row["primary_raag"] for row in test_rows], ranked, accepted)
    return metrics



def score_taal_model(name: str, probabilities: np.ndarray, classes: list[str], test_rows: list[dict[str, str]]) -> dict[str, object]:
    accepted = [set(value.strip() for value in row["accepted_taals"].split(";") if value.strip()) for row in test_rows]
    ranked = ranked_from_probabilities(probabilities, classes)
    metrics = evaluate_rankings(
        [row["primary_taal"] for row in test_rows],
        accepted,
        ranked,
        probabilities,
        classes,
        [row["language"] for row in test_rows],
    )
    metrics["model"] = name
    metrics["confusionPairs"] = confusion_pairs([row["primary_taal"] for row in test_rows], ranked, accepted)
    return metrics


def run_suite(root: Path) -> dict[str, object]:
    dataset_path = root / "evaluation/seed_benchmark_v1.csv"
    dataset = read_dataset(dataset_path)
    train_rows = dataset.split("train")
    dev_rows = dataset.split("dev")
    test_rows = dataset.split("test")
    train_plus_dev = train_rows + dev_rows
    y_train = [row["primary_raag"] for row in train_plus_dev]
    classes = sorted(set(y_train))

    # Select models exclusively from train/development data. Do not use test labels
    # to pick a model; previously, this selection incorrectly used the test set.
    dev_y = [row["primary_raag"] for row in train_rows]
    rule_dev_model = PrototypeRuleRanker().fit([model_text(row, False) for row in train_rows], dev_y)
    word_dev_model = build_word_pipeline().fit([model_text(row, True) for row in train_rows], dev_y)
    char_text_dev_model = build_char_pipeline().fit([model_text(row, False) for row in train_rows], dev_y)
    char_context_dev_model = build_char_pipeline().fit([model_text(row, True) for row in train_rows], dev_y)
    dev_classes = sorted(set(dev_y))
    def dev_prob(model, inputs, class_list):
        return align_probabilities(model.predict_proba(inputs), list(class_list), dev_classes)
    rule_dev_probs = dev_prob(rule_dev_model, [model_text(row, False) for row in dev_rows], rule_dev_model.classes_)
    word_dev_probs = dev_prob(word_dev_model, [model_text(row, True) for row in dev_rows], word_dev_model.named_steps["classifier"].classes_)
    char_text_dev_probs = dev_prob(char_text_dev_model, [model_text(row, False) for row in dev_rows], char_text_dev_model.named_steps["classifier"].classes_)
    char_context_dev_probs = dev_prob(char_context_dev_model, [model_text(row, True) for row in dev_rows], char_context_dev_model.named_steps["classifier"].classes_)
    temperature = choose_temperature(char_context_dev_probs, [row["primary_raag"] for row in dev_rows], dev_classes)
    hybrid_dev_probs = 0.72 * char_context_dev_probs + 0.28 * rule_dev_probs
    hybrid_dev_probs /= hybrid_dev_probs.sum(axis=1, keepdims=True)
    development_comparisons = [
        score_model("rules-prototype-v1", rule_dev_probs, dev_classes, dev_rows),
        score_model("word-tfidf-logreg-v1", word_dev_probs, dev_classes, dev_rows),
        score_model("char-tfidf-text-only-v1", char_text_dev_probs, dev_classes, dev_rows),
        score_model("char-tfidf-context-v1", char_context_dev_probs, dev_classes, dev_rows),
        score_model("char-tfidf-calibrated-v1", temperature_scale(char_context_dev_probs, temperature), dev_classes, dev_rows),
        score_model("hybrid-char-plus-rules-v1", hybrid_dev_probs, dev_classes, dev_rows),
    ]
    development_comparisons.sort(key=lambda item: (
        float(item["primaryTop3Recall"]), float(item["macroF1PrimaryLabel"]),
        -float(item["expectedCalibrationError"])), reverse=True)
    selected_from_dev = development_comparisons[0]["model"]

    # After development-only selection, refit the models on train + dev and
    # evaluate the untouched test split exactly once.
    # Transparent rules baseline.
    rule = PrototypeRuleRanker().fit([model_text(row, False) for row in train_plus_dev], y_train)
    rule_proba = align_probabilities(rule.predict_proba([model_text(row, False) for row in test_rows]), list(rule.classes_), classes)

    # Word model.
    word = build_word_pipeline().fit([model_text(row, True) for row in train_plus_dev], y_train)
    word_raw = word.predict_proba([model_text(row, True) for row in test_rows])
    word_proba = align_probabilities(word_raw, list(word.named_steps["classifier"].classes_), classes)

    # Character model without user/form/time constraints: ablation.
    char_text_only = build_char_pipeline().fit([model_text(row, False) for row in train_plus_dev], y_train)
    char_text_raw = char_text_only.predict_proba([model_text(row, False) for row in test_rows])
    char_text_proba = align_probabilities(char_text_raw, list(char_text_only.named_steps["classifier"].classes_), classes)

    # Temperature was chosen only on the development split above.
    char = build_char_pipeline().fit([model_text(row, True) for row in train_plus_dev], y_train)
    char_raw = char.predict_proba([model_text(row, True) for row in test_rows])
    char_proba = align_probabilities(char_raw, list(char.named_steps["classifier"].classes_), classes)
    char_calibrated_proba = temperature_scale(char_proba, temperature)

    # Neuro-symbolic hybrid. Weight selected on the held-out dev split in a full
    # research release; v10 records the explicit fixed pre-registration weight.
    hybrid_proba = 0.72 * char_proba + 0.28 * rule_proba
    hybrid_proba /= hybrid_proba.sum(axis=1, keepdims=True)

    # Independent Taal baseline. It uses verse plus explicit form/time/language
    # context and is evaluated separately from the Raag ranker.
    taal_labels = [row["primary_taal"] for row in train_plus_dev]
    taal_classes = sorted(set(taal_labels))
    taal_model = build_char_pipeline().fit([model_text(row, True) for row in train_plus_dev], taal_labels)
    taal_raw = taal_model.predict_proba([model_text(row, True) for row in test_rows])
    taal_proba = align_probabilities(taal_raw, list(taal_model.named_steps["classifier"].classes_), taal_classes)
    taal_result = score_taal_model("taal-char-tfidf-context-v1", taal_proba, taal_classes, test_rows)

    comparisons = [
        score_model("rules-prototype-v1", rule_proba, classes, test_rows),
        score_model("word-tfidf-logreg-v1", word_proba, classes, test_rows),
        score_model("char-tfidf-text-only-v1", char_text_proba, classes, test_rows),
        score_model("char-tfidf-context-v1", char_proba, classes, test_rows),
        score_model("char-tfidf-calibrated-v1", char_calibrated_proba, classes, test_rows),
        score_model("hybrid-char-plus-rules-v1", hybrid_proba, classes, test_rows),
    ]
    # The test metrics must not affect selection. Display in dev-selected order.
    dev_order = {item["model"]: position for position, item in enumerate(development_comparisons)}
    comparisons.sort(key=lambda item: dev_order[item["model"]])
    best = next(item for item in comparisons if item["model"] == selected_from_dev)
    test_probabilities = {
        "rules-prototype-v1": rule_proba,
        "word-tfidf-logreg-v1": word_proba,
        "char-tfidf-text-only-v1": char_text_proba,
        "char-tfidf-context-v1": char_proba,
        "char-tfidf-calibrated-v1": char_calibrated_proba,
        "hybrid-char-plus-rules-v1": hybrid_proba,
    }

    models_dir = root / "models"
    models_dir.mkdir(exist_ok=True)
    joblib.dump({"pipeline": char_text_only, "classes": classes, "version": "char-tfidf-text-only-v1", "include_context": False}, models_dir / "raag_text_baseline_v1.joblib", compress=3)
    joblib.dump({"pipeline": char, "classes": classes, "version": "char-tfidf-context-v1", "include_context": True, "temperature": temperature}, models_dir / "raag_context_baseline_v1.joblib", compress=3)
    joblib.dump({"ranker": rule, "classes": classes, "version": "rules-prototype-v1"}, models_dir / "raag_rule_baseline_v1.joblib", compress=3)
    joblib.dump({"pipeline": taal_model, "classes": taal_classes, "version": "taal-char-tfidf-context-v1", "include_context": True}, models_dir / "taal_text_baseline_v1.joblib", compress=3)

    registry = {
        "selectedBy": "development split only: primaryTop3Recall, then macroF1PrimaryLabel, then calibration",
        "selectedModel": best["model"],
        "availableArtifacts": {
            "textOnly": "models/raag_text_baseline_v1.joblib",
            "context": "models/raag_context_baseline_v1.joblib",
            "rules": "models/raag_rule_baseline_v1.joblib",
            "taal": "models/taal_text_baseline_v1.joblib"
        },
        "temperature": round(temperature, 6),
        "expertValidated": False
    }
    (models_dir / "registry.json").write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    report_dir = root / "reports/research"
    report_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {
        "release": "v10",
        "benchmark": {
            "name": "MAQAM multilingual synthetic seed benchmark v1",
            "type": "internal-synthetic",
            "expertValidated": False,
            "rows": len(dataset.rows),
            "train": len(train_rows),
            "dev": len(dev_rows),
            "test": len(test_rows),
            "classes": len(classes),
            "languages": sorted(set(row["language"] for row in dataset.rows)),
            "leakageControl": "Template families 0-3 train, 4 dev and 5 test; Raag names are excluded from poems.",
            "calibration": {"method": "scalar temperature scaling", "temperature": round(temperature, 4), "fitSplit": "dev"}
        },
        "claimBoundary": "These metrics prove pipeline reproducibility on generated seed data only. They are not expert agreement or real-world accuracy.",
        "models": comparisons,
        "selectedModel": best["model"],
        "selectionSplit": "dev (train-only candidates)",
        "developmentComparisons": [{key: entry[key] for key in ["model", "primaryTop3Recall", "macroF1PrimaryLabel", "expectedCalibrationError"]} for entry in development_comparisons],
        "selectedMetrics": {key: best[key] for key in ["top1Agreement", "top3Agreement", "primaryTop1Accuracy", "primaryTop3Recall", "meanReciprocalRank", "macroF1PrimaryLabel", "expectedCalibrationError", "multiclassBrier"]},
        "taalModel": taal_result,
        "target": {"metric": "Top-3 expert-set agreement", "range": "0.90-0.93", "status": "not measured", "requires": "independent expert-labelled benchmark"},
    }
    (report_dir / "experiment_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with (report_dir / "model_comparison.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["model", "items", "top1Agreement", "top3Agreement", "primaryTop1Accuracy", "primaryTop3Recall", "meanReciprocalRank", "macroF1PrimaryLabel", "expectedCalibrationError", "multiclassBrier"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in comparisons:
            writer.writerow({field: result.get(field) for field in fields})

    (report_dir / "ablation_results.json").write_text(json.dumps({
        "benchmarkType": "internal-synthetic",
        "selected": best["model"],
        "comparisons": [{key: item[key] for key in ["model", "primaryTop1Accuracy", "primaryTop3Recall", "macroF1PrimaryLabel", "expectedCalibrationError"]} for item in comparisons],
        "interpretation": "Ablations compare reproducible seed baselines only; they do not establish external musical validity."
    }, indent=2) + "\n", encoding="utf-8")

    with (report_dir / "per_language_metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["model", "language", "items", "top1Agreement", "top3Agreement", "mrr"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for result in comparisons:
            for language, values in result["perLanguage"].items():
                writer.writerow({"model": result["model"], "language": language, **values})

    with (report_dir / "confusion_pairs.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["model", "expectedPrimary", "predicted", "count"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for result in comparisons:
            for pair in result["confusionPairs"]:
                writer.writerow({"model": result["model"], **pair})

    with (report_dir / "calibration_bins.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["model", "lower", "upper", "count", "confidence", "accuracy"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for result in comparisons:
            for bin_row in result["calibrationBins"]:
                writer.writerow({"model": result["model"], **bin_row})

    selected_predictions = ranked_from_probabilities(test_probabilities[selected_from_dev], classes)
    taal_predictions = ranked_from_probabilities(taal_proba, taal_classes)
    with (report_dir / "test_predictions.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["item_id", "language", "poem", "primary_raag", "accepted_raags", "predicted_raags", "primary_taal", "accepted_taals", "predicted_taals", "top1_confidence", "is_synthetic"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, row in enumerate(test_rows):
            writer.writerow({
                "item_id": row["item_id"], "language": row["language"], "poem": row["poem"],
                "primary_raag": row["primary_raag"], "accepted_raags": row["accepted_raags"],
                "predicted_raags": ";".join(selected_predictions[index][:5]),
                "primary_taal": row["primary_taal"], "accepted_taals": row["accepted_taals"],
                "predicted_taals": ";".join(taal_predictions[index][:5]),
                "top1_confidence": round(float(test_probabilities[selected_from_dev][index].max()), 6), "is_synthetic": "true",
            })

    review_cases = []
    for index, row in enumerate(test_rows[:36]):
        review_cases.append({
            "itemId": row["item_id"], "language": row["language"], "poem": row["poem"],
            "systemCandidates": selected_predictions[index][:5], "referenceSeed": row["accepted_raags"].split(";"),
            "systemTaalCandidates": taal_predictions[index][:5], "referenceTaalSeed": row["accepted_taals"].split(";"),
            "warning": "Synthetic seed item. Expert judgement is not pre-filled.",
        })
    (root / "web/app/data/review_cases.json").write_text(json.dumps(review_cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "web/app/data/research_metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary
