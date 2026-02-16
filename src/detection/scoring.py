import numpy as np


class AnalomyScorer:
    def compute_confidence(self, scores: np.ndarray) -> np.ndarray:
        min_score = np.min(scores)
        max_score = np.max(scores)

        normalized = (scores - min_score) / (max_score - min_score + 1e-8)

        confidence = 1 - normalized

        return confidence
