from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

import joblib
import numpy as np
from tensorflow.keras.models import load_model


@dataclass(frozen=True)
class InferenceResult:
    anomaly_score: float
    is_anomaly: bool
    threshold: float
    raw_max_error: float
    event_scores: List[float]
    sequence_scores: List[float]
    window_size: int
    padding_applied: bool


class InferencePipeline:
    """
    Inference-only anomaly pipeline:
    logs/templates -> vectorizer -> svd -> scaler -> sequences -> lstm -> score
    """

    def __init__(self, model_dir: Optional[str] = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        default_model_dir = project_root / "models"
        artifacts_dir = Path(model_dir) if model_dir else default_model_dir

        self.vectorizer = joblib.load(artifacts_dir / "vectorizer.pkl")
        self.svd = joblib.load(artifacts_dir / "svd.pkl")
        self.scaler = joblib.load(artifacts_dir / "scaler.pkl")
        self.model = load_model(self._resolve_model_path(artifacts_dir))
        self.threshold = float(np.load(self._resolve_threshold_path(artifacts_dir)))
        self.window_size = int(self.model.input_shape[1])

    def score(self, logs: Sequence[str]) -> InferenceResult:
        cleaned = [str(log).strip() for log in logs if str(log).strip()]
        if not cleaned:
            return InferenceResult(
                anomaly_score=0.0,
                is_anomaly=False,
                threshold=self.threshold,
                raw_max_error=0.0,
                event_scores=[],
                sequence_scores=[],
                window_size=self.window_size,
                padding_applied=False,
            )

        features = self._preprocess(cleaned)
        sequences, padding_applied, original_count = self._build_sequences(features)
        reconstructed = self.model.predict(sequences, verbose=0)
        sequence_errors = np.mean(np.square(sequences - reconstructed), axis=(1, 2))
        event_errors = self._map_sequence_errors_to_events(
            sequence_errors=sequence_errors,
            event_count=original_count,
            sequence_length=self.window_size,
        )

        raw_max_error = float(np.max(event_errors) if len(event_errors) else 0.0)
        normalized_event_scores = np.clip(event_errors / max(self.threshold, 1e-8), 0.0, 1.0)
        anomaly_score = float(np.max(normalized_event_scores) if len(normalized_event_scores) else 0.0)
        is_anomaly = raw_max_error > self.threshold

        normalized_sequence_scores = np.clip(
            sequence_errors / max(self.threshold, 1e-8),
            0.0,
            1.0,
        )

        return InferenceResult(
            anomaly_score=anomaly_score,
            is_anomaly=is_anomaly,
            threshold=self.threshold,
            raw_max_error=raw_max_error,
            event_scores=normalized_event_scores.tolist(),
            sequence_scores=normalized_sequence_scores.tolist(),
            window_size=self.window_size,
            padding_applied=padding_applied,
        )

    def _preprocess(self, logs: Sequence[str]) -> np.ndarray:
        transformed = self.vectorizer.transform(logs)
        reduced = self.svd.transform(transformed)
        scaled = self.scaler.transform(reduced)
        return np.asarray(scaled, dtype=np.float32)

    def _build_sequences(self, features: np.ndarray) -> tuple[np.ndarray, bool, int]:
        original_count = len(features)
        if original_count == 0:
            return np.empty((0, self.window_size, 0), dtype=np.float32), False, 0

        if original_count < self.window_size:
            pad_count = self.window_size - original_count
            padding = np.repeat(features[-1:, :], pad_count, axis=0)
            padded = np.vstack([features, padding])
            sequence = padded[np.newaxis, :, :]
            return np.asarray(sequence, dtype=np.float32), True, original_count

        sequences = np.array(
            [features[i : i + self.window_size] for i in range(original_count - self.window_size + 1)],
            dtype=np.float32,
        )
        return sequences, False, original_count

    def _map_sequence_errors_to_events(
        self,
        sequence_errors: np.ndarray,
        event_count: int,
        sequence_length: int,
    ) -> np.ndarray:
        if event_count == 0:
            return np.array([], dtype=np.float32)

        if len(sequence_errors) == 1 and event_count < sequence_length:
            return np.full(event_count, float(sequence_errors[0]), dtype=np.float32)

        event_errors = np.zeros(event_count, dtype=np.float32)
        counts = np.zeros(event_count, dtype=np.float32)

        for idx, error in enumerate(sequence_errors):
            start = idx
            end = min(idx + sequence_length, event_count)
            if start >= event_count:
                break
            event_errors[start:end] += float(error)
            counts[start:end] += 1.0

        counts[counts == 0] = 1.0
        return event_errors / counts

    def _resolve_model_path(self, model_dir: Path) -> Path:
        candidates = [
            model_dir / "lstm.keras",
            model_dir / "lstm_model.h5",
            model_dir / "lstm_autoencoder.keras",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[-1]

    def _resolve_threshold_path(self, model_dir: Path) -> Path:
        candidates = [
            model_dir / "threshold.npy",
            model_dir / "anomaly_threshold.npy",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

