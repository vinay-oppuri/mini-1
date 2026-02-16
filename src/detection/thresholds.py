import numpy as np


class ThresholdManager:
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def apply(self, confidence_scores: np.ndarray):
        return confidence_scores >= self.threshold