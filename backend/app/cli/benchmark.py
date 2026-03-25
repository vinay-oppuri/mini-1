from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.analyzer import AnalyzerService


def _predicted_label(result: dict[str, Any]) -> str:
    decision_status = result.get("decision", {}).get("status")
    if decision_status == "unsupported_log_profile":
        return "unsupported"
    is_anomaly = result.get("analysis", {}).get("is_anomaly")
    if is_anomaly is True:
        return "anomaly"
    if is_anomaly is False:
        return "normal"
    return "unsupported"


def run_benchmark(
    service: AnalyzerService,
    manifest_path: str = "data/benchmarks/manifest.json",
) -> dict[str, Any]:
    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        raise FileNotFoundError(f"Benchmark manifest not found: {manifest_file}")

    with manifest_file.open("r", encoding="utf-8") as file:
        manifest = json.load(file)

    if not isinstance(manifest, list):
        raise ValueError("Benchmark manifest must be a list.")

    cases: list[dict[str, Any]] = []
    tp = tn = fp = fn = unsupported = 0

    for item in manifest:
        name = str(item["name"])
        path = str(item["path"])
        expected = str(item["expected"]).lower()

        result = service.analyze_file(path, source=name)
        predicted = _predicted_label(result)
        score = result.get("analysis", {}).get("anomaly_score")

        if predicted == "unsupported":
            unsupported += 1
        elif expected == "anomaly":
            if predicted == "anomaly":
                tp += 1
            else:
                fn += 1
        elif expected == "normal":
            if predicted == "normal":
                tn += 1
            else:
                fp += 1

        cases.append(
            {
                "name": name,
                "path": path,
                "expected": expected,
                "predicted": predicted,
                "score": score,
                "supported": result.get("compatibility", {}).get("is_supported", False),
                "pass": expected == predicted,
            }
        )

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    total_binary = tp + tn + fp + fn
    accuracy = (tp + tn) / total_binary if total_binary else 0.0

    return {
        "manifest": str(manifest_file),
        "summary": {
            "total_cases": len(cases),
            "binary_scored_cases": total_binary,
            "unsupported_cases": unsupported,
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
        "cases": cases,
    }
