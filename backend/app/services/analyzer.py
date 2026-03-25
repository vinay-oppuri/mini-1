from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.coordinator import CoordinatorAgent
from app.core.compatibility import build_compatibility_report
from app.core.contracts import validate_logs_contract
from app.core.loader import load_logs_from_path


class AnalyzerService:
    """Production wrapper over the multi-agent pipeline with compatibility checks."""

    def __init__(
        self,
        model_path: str = "model/model.pt",
        metadata_path: str = "model/model_metadata.json",
        parsed_output_path: str = "data/parsed_logs/latest_parsed_logs.json",
        default_unknown_ratio_threshold: float = 0.30,
    ) -> None:
        self.coordinator = CoordinatorAgent(
            model_path=model_path,
            metadata_path=metadata_path,
            parsed_output_path=parsed_output_path,
        )
        self.default_unknown_ratio_threshold = default_unknown_ratio_threshold

    @property
    def detector(self):
        return self.coordinator.analysis_agent.detector

    def analyze(
        self,
        logs: list[Any],
        source: str = "runtime-input",
        unknown_ratio_threshold: float | None = None,
    ) -> dict[str, Any]:
        validated_logs = validate_logs_contract(logs)
        result = self.coordinator.run(logs=validated_logs, source=source)

        threshold = (
            self.default_unknown_ratio_threshold
            if unknown_ratio_threshold is None
            else unknown_ratio_threshold
        )
        compatibility = build_compatibility_report(
            parsed_events=result.get("parsed_events", []),
            known_event_ids=set(self.detector.template_map.keys()),
            unknown_ratio_threshold=threshold,
        )
        result["compatibility"] = compatibility

        if not compatibility["is_supported"]:
            result["analysis"]["is_anomaly"] = None
            result["analysis"]["anomaly_score"] = None
            result["analysis"]["final_status"] = "unsupported_log_profile"
            result["policy"] = {
                "severity": "unsupported",
                "score": None,
                "top_service": result.get("cloud_metrics", {}).get("top_service", "unknown"),
                "critical_service": None,
                "attack_type": "Unknown",
                "allowed_actions": ["manual_review"],
                "requires_human_approval": True,
            }
            result["response"] = {
                "actions": [
                    "Log profile unsupported for current model. Manual review required."
                ],
                "executed_actions": ["manual_review"],
                "human_in_the_loop": True,
            }
            result["decision"] = {
                "status": "unsupported_log_profile",
                "severity": "unsupported",
                "final_action_count": 1,
            }

        result["model_card"] = {
            "model_mode": result.get("analysis", {}).get("model_mode", "unknown"),
            "model_threshold": self.detector.threshold,
            "max_seq_len": self.detector.max_seq_len,
            "vocab_size": self.detector.vocab_size,
        }

        return result

    def analyze_file(
        self,
        path: str | Path,
        source: str | None = None,
        unknown_ratio_threshold: float | None = None,
    ) -> dict[str, Any]:
        path_obj = Path(path)
        logs = load_logs_from_path(path_obj)
        source_name = source or path_obj.stem
        return self.analyze(
            logs=logs,
            source=source_name,
            unknown_ratio_threshold=unknown_ratio_threshold,
        )
