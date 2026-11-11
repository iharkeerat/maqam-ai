"""Transparent symbolic/text prototype ranker used as a research baseline."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Sequence

import numpy as np


def tokens(text: str) -> list[str]:
    return re.findall(r"[\w\u0600-\u06ff\u0900-\u097f\u0a00-\u0a7f]+", text.casefold(), flags=re.UNICODE)


class PrototypeRuleRanker:
    """Ranks labels by overlap with transparent class token prototypes.

    This is intentionally simple and inspectable. It establishes a rules/lexicon
    baseline, not a claim of musicological adequacy.
    """

    def fit(self, texts: Sequence[str], labels: Sequence[str]) -> "PrototypeRuleRanker":
        document_frequency: Counter[str] = Counter()
        class_counts: dict[str, Counter[str]] = {}
        for text, label in zip(texts, labels):
            text_tokens = tokens(text)
            document_frequency.update(set(text_tokens))
            class_counts.setdefault(label, Counter()).update(text_tokens)
        total_docs = max(1, len(texts))
        self.classes_ = np.array(sorted(class_counts))
        self.prototypes_: dict[str, dict[str, float]] = {}
        for label, counts in class_counts.items():
            weighted = {
                token: (1 + math.log(count)) * math.log((1 + total_docs) / (1 + document_frequency[token]))
                for token, count in counts.items()
            }
            top = sorted(weighted.items(), key=lambda item: item[1], reverse=True)[:90]
            norm = math.sqrt(sum(value * value for _, value in top)) or 1.0
            self.prototypes_[label] = {token: value / norm for token, value in top}
        return self

    def predict_proba(self, texts: Sequence[str]) -> np.ndarray:
        scores = np.zeros((len(texts), len(self.classes_)), dtype=float)
        for row, text in enumerate(texts):
            counts = Counter(tokens(text))
            length = math.sqrt(sum(value * value for value in counts.values())) or 1.0
            for column, label in enumerate(self.classes_):
                score = sum((count / length) * self.prototypes_[str(label)].get(token, 0.0) for token, count in counts.items())
                scores[row, column] = max(0.0, score)
        # Softmax with modest temperature to avoid false certainty.
        scores = scores / 0.35
        scores -= scores.max(axis=1, keepdims=True)
        exp = np.exp(scores)
        return exp / np.maximum(exp.sum(axis=1, keepdims=True), 1e-12)
