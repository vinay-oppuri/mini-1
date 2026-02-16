import numpy as np
from sklearn.ensemble import IsolationForest

class IsolationForestDetector:
    def __init__(self, contamination: float = 0.05):
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42
        )
        self.trained = False

    
    def train(self, X: np.ndarray):
        self.model.fit(X)
        self.trained = True

    def predict(self, X: np.ndarray):
        if not self.trained:
            raise RuntimeError("Model must be trained before prediction.")
        
        labels = self.model.predict(X)
        scores = self.model.decision_function(X)

        return labels, scores
