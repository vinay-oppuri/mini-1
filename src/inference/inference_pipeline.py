import joblib
import numpy as np
from tensorflow.keras.models import load_model
from pathlib import Path


class InferenceResult:
    def __init__(
        self,
        anomaly_score,
        is_anomaly,
        threshold,
        raw_max_error,
        event_scores,
        window_size,
        padding_applied,
    ):
        self.anomaly_score = float(anomaly_score)
        self.is_anomaly = bool(is_anomaly)
        self.threshold = float(threshold)
        self.raw_max_error = float(raw_max_error)
        self.event_scores = event_scores
        self.window_size = int(window_size)
        self.padding_applied = bool(padding_applied)


class InferencePipeline:

    def __init__(self):
        model_dir = Path("models")

        # load saved preprocessing tools
        self.vectorizer = joblib.load(model_dir / "vectorizer.pkl")
        self.svd = joblib.load(model_dir / "svd.pkl")
        self.scaler = joblib.load(model_dir / "scaler.pkl")

        # load trained LSTM model
        model_path = self._find_first_existing(model_dir, [
            "lstm.keras",
            "lstm_model.h5",
            "lstm_autoencoder.keras",
        ])
        self.model = load_model(model_path)

        # anomaly threshold
        threshold_path = self._find_first_existing(model_dir, [
            "threshold.npy",
            "anomaly_threshold.npy",
        ])
        self.threshold = float(np.load(threshold_path))

        # sequence length expected by LSTM
        self.window_size = int(self.model.input_shape[1])


    def score(self, logs):

        if len(logs) == 0:
            return InferenceResult(
                anomaly_score=0.0,
                is_anomaly=False,
                threshold=self.threshold,
                raw_max_error=0.0,
                event_scores=[],
                window_size=self.window_size,
                padding_applied=False,
            )

        # convert logs to numerical vectors
        vectors = self.vectorizer.transform(logs)

        # dimensionality reduction
        reduced = self.svd.transform(vectors)

        # normalize features
        scaled = self.scaler.transform(reduced)

        features = np.array(scaled, dtype=np.float32)

        # build sequence for LSTM
        sequence, padding_applied = self._build_sequence(features)
        sequence = np.expand_dims(sequence, axis=0)

        # reconstruction by autoencoder
        reconstructed = self.model.predict(sequence, verbose=0)

        # reconstruction error
        error = float(np.mean((sequence - reconstructed) ** 2))

        # anomaly score
        safe_threshold = self.threshold if self.threshold > 0 else 1e-8
        anomaly_score = min(error / safe_threshold, 1.0)

        is_anomaly = error > self.threshold
        event_scores = [float(anomaly_score)] * len(logs)

        return InferenceResult(
            anomaly_score=anomaly_score,
            is_anomaly=is_anomaly,
            threshold=self.threshold,
            raw_max_error=error,
            event_scores=event_scores,
            window_size=self.window_size,
            padding_applied=padding_applied,
        )

    def _build_sequence(self, features):
        total = len(features)

        if total >= self.window_size:
            return features[:self.window_size], False

        # if fewer events than window size, pad with last event
        missing = self.window_size - total
        padding = np.repeat(features[-1:], missing, axis=0)
        sequence = np.vstack([features, padding])
        return sequence, True

    def _find_first_existing(self, folder, names):
        for name in names:
            path = folder / name
            if path.exists():
                return path
        raise FileNotFoundError(f"Missing model artifact in {folder}: {names}")
