from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.model.transformer import TransformerAnomalyDetector
from app.parser.drain_parser import DrainParser
from app.utils.sequence_builder import SequenceBuilder

try:
    from google import genai
except ImportError:  # pragma: no cover - optional dependency
    genai = None


class AnalysisAgent:
    """Parses logs, builds sequences, runs transformer inference, and explains findings."""

    def __init__(
        self,
        model_path: str = "model/model.pt",
        metadata_path: str = "model/model_metadata.json",
        parsed_output_path: str = "data/parsed_logs/latest_parsed_logs.json",
    ) -> None:
        self.sequence_builder = SequenceBuilder()
        self.detector = TransformerAnomalyDetector(
            model_path=model_path,
            metadata_path=metadata_path,
        )
        self.parsed_output_path = Path(parsed_output_path)

    def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        logs = context["raw_logs"]
        parser = DrainParser()
        parsed_events = parser.parse(logs)

        self.parsed_output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.parsed_output_path.open("w", encoding="utf-8") as file:
            json.dump(parsed_events, file, indent=2)

        sequence_data = self.sequence_builder.build(
            parsed_events=parsed_events,
            vocab_size=self.detector.vocab_size,
            template_map=self.detector.template_map,
            max_seq_len=self.detector.max_seq_len,
        )

        prediction = self.detector.predict(sequence_data["model_sequence"])
        explanation = self._build_explanation(logs, prediction["score"])

        context["parsed_events"] = parsed_events
        context["event_sequence"] = sequence_data["event_sequence"]
        context["analysis"] = {
            "anomaly_score": prediction["score"],
            "is_anomaly": prediction["is_anomaly"],
            "threshold": prediction["threshold"],
            "model_mode": prediction.get("model_mode", "transformer"),
            "window_size": self.detector.max_seq_len,
            "events_parsed": len(parsed_events),
        }
        context["llm_explanation"] = explanation
        return context

    def _build_explanation(self, logs: list[str], anomaly_score: float) -> dict[str, str]:
        llm_response = self._query_llm(logs, anomaly_score)
        if llm_response is not None:
            return llm_response

        text = " ".join(logs).lower()
        if "login failed" in text:
            attack_type = "Brute Force"
            reason = "Repeated login failures suggest credential stuffing or brute force attempts."
        elif "too many requests" in text:
            attack_type = "DDoS-like Burst"
            reason = "Request spikes indicate possible volumetric abuse or bot traffic."
        elif "outbound transfer" in text:
            attack_type = "Potential Data Exfiltration"
            reason = "Large outbound transfer activity can indicate suspicious data movement."
        elif "port scan" in text:
            attack_type = "Port Scan"
            reason = "Multiple scan-style probes suggest reconnaissance behavior."
        else:
            attack_type = "Unknown Pattern"
            reason = "Pattern does not match a known attack category; investigation recommended."

        return {
            "attack_type": attack_type,
            "reason": reason,
            "recommended_action": "Review the affected workload and investigate recent activity.",
            "source": "rule-based fallback",
        }

    def _query_llm(self, logs: list[str], anomaly_score: float) -> dict[str, str] | None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or genai is None:
            return None

        prompt = (
            "You are a cloud security analyst. "
            "Given the logs and anomaly score, return strict JSON with keys: "
            "attack_type, reason, recommended_action.\n\n"
            f"Anomaly score: {anomaly_score:.4f}\n"
            f"Logs:\n{json.dumps(logs[:40], indent=2)}"
        )

        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            raw = (response.text or "").strip()
            if raw.startswith("```"):
                raw = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None
            attack_type = str(data.get("attack_type", "")).strip()
            reason = str(data.get("reason", "")).strip()
            action = str(data.get("recommended_action", "")).strip()
            if not attack_type or not reason:
                return None
            return {
                "attack_type": attack_type,
                "reason": reason,
                "recommended_action": action or "Investigate suspicious sequence activity.",
                "source": "gemini",
            }
        except Exception:
            return None
