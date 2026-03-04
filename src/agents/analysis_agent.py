from __future__ import annotations

from collections import Counter
from typing import Any, Dict

import numpy as np

from log_parser.drain_parser import DrainParser
from inference.inference_pipeline import InferencePipeline


class AnalysisAgent:
    """
    Builds event templates/sequences and computes anomaly score via LSTM pipeline.
    """

    def __init__(self) -> None:
        self.parser = DrainParser()
        self.pipeline = InferencePipeline()

    def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logs = context.get("raw_logs", [])
        parsed_events = self.parser.parse(logs)
        templates = [event.template for event in parsed_events]
        event_ids = [event.event_id for event in parsed_events]

        model_result = self.pipeline.score(templates)
        heuristic_score = self._heuristic_score(templates)

        final_score = float(max(model_result.anomaly_score, heuristic_score))
        final_score = float(np.clip(final_score, 0.0, 1.0))
        is_anomaly = final_score >= 0.8

        context["parsed_events"] = [
            {"raw": event.raw, "template": event.template, "event_id": event.event_id}
            for event in parsed_events
        ]
        context["event_sequence"] = event_ids
        context["templates"] = templates
        context["analysis"] = {
            "anomaly_score": final_score,
            "is_anomaly": is_anomaly,
            "model_score": model_result.anomaly_score,
            "heuristic_score": heuristic_score,
            "threshold": model_result.threshold,
            "raw_max_error": model_result.raw_max_error,
            "window_size": model_result.window_size,
            "padding_applied": model_result.padding_applied,
            "event_scores": model_result.event_scores,
        }
        return context

    def _heuristic_score(self, templates: list[str]) -> float:
        if not templates:
            return 0.0

        text = "\n".join(templates)
        repeated_template_count = Counter(templates).most_common(1)[0][1]
        repetition_ratio = repeated_template_count / max(len(templates), 1)

        failed_hits = sum(1 for line in templates if "failed" in line or "denied" in line)
        ddos_hits = sum(
            1
            for line in templates
            if any(token in line for token in ["too many requests", "traffic spike", "status <*>", "flood"])
        )
        port_hits = sum(
            1 for line in templates if any(token in line for token in ["port", "scan", "probe"])
        )
        exfil_hits = sum(
            1 for line in templates if any(token in line for token in ["outbound", "upload", "bytes sent", "exfil"])
        )

        score = 0.0
        score += min(0.35, repetition_ratio * 0.45)
        score += min(0.25, failed_hits * 0.05)
        score += min(0.35, ddos_hits * 0.1)
        score += min(0.25, port_hits * 0.08)
        score += min(0.25, exfil_hits * 0.1)

        # Promote clear attack signatures.
        if ddos_hits >= 4 or failed_hits >= 5 or port_hits >= 5 or exfil_hits >= 3:
            score = max(score, 0.9)

        if "unknown-service" in text and len(templates) < 3:
            score = min(score, 0.5)

        return float(np.clip(score, 0.0, 1.0))
