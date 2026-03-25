from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.analyzer import AnalyzerService


def _metrics_from_scores(
    normal_scores: list[float],
    anomaly_scores: list[float],
    threshold: float,
) -> dict[str, float | int]:
    tp = sum(1 for score in anomaly_scores if score >= threshold)
    fn = len(anomaly_scores) - tp
    fp = sum(1 for score in normal_scores if score >= threshold)
    tn = len(normal_scores) - fp

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        (2 * precision * recall) / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else 0.0

    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
    }


def find_best_threshold(normal_scores: list[float], anomaly_scores: list[float]) -> tuple[float, dict[str, Any]]:
    if not normal_scores or not anomaly_scores:
        raise ValueError("Need at least one normal score and one anomaly score to calibrate.")

    candidate_thresholds = sorted(set(normal_scores + anomaly_scores))
    best_threshold = candidate_thresholds[0]
    best_metrics = _metrics_from_scores(normal_scores, anomaly_scores, best_threshold)

    for threshold in candidate_thresholds:
        metrics = _metrics_from_scores(normal_scores, anomaly_scores, threshold)
        if metrics["f1"] > best_metrics["f1"]:
            best_threshold = threshold
            best_metrics = metrics

    return best_threshold, best_metrics


def calibrate_threshold(
    service: AnalyzerService,
    normal_files: list[str],
    anomaly_files: list[str],
    metadata_path: str = "model/model_metadata.json",
    output_metadata_path: str | None = None,
) -> dict[str, Any]:
    normal_scores: list[float] = []
    anomaly_scores: list[float] = []

    normal_details: list[dict[str, Any]] = []
    anomaly_details: list[dict[str, Any]] = []

    for path in normal_files:
        result = service.analyze_file(path, source=Path(path).stem)
        score = result.get("analysis", {}).get("anomaly_score")
        normal_details.append(
            {
                "path": path,
                "score": score,
                "supported": result.get("compatibility", {}).get("is_supported", False),
            }
        )
        if isinstance(score, (float, int)):
            normal_scores.append(float(score))

    for path in anomaly_files:
        result = service.analyze_file(path, source=Path(path).stem)
        score = result.get("analysis", {}).get("anomaly_score")
        anomaly_details.append(
            {
                "path": path,
                "score": score,
                "supported": result.get("compatibility", {}).get("is_supported", False),
            }
        )
        if isinstance(score, (float, int)):
            anomaly_scores.append(float(score))

    best_threshold, metrics = find_best_threshold(normal_scores, anomaly_scores)

    metadata_file = Path(metadata_path)
    with metadata_file.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    old_threshold = float(metadata.get("threshold", 0.5))
    metadata["threshold"] = float(best_threshold)
    metadata["calibration"] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "old_threshold": old_threshold,
        "new_threshold": float(best_threshold),
        "metrics": metrics,
        "normal_files": normal_details,
        "anomaly_files": anomaly_details,
    }

    out_file = Path(output_metadata_path) if output_metadata_path else metadata_file
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2)

    return {
        "old_threshold": old_threshold,
        "new_threshold": float(best_threshold),
        "metrics": metrics,
        "output_metadata": str(out_file),
        "normal_files_used": len(normal_scores),
        "anomaly_files_used": len(anomaly_scores),
    }
