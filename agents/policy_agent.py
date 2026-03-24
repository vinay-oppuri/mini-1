from __future__ import annotations

from typing import Any


class PolicyAgent:
    """Applies policy rules based on model score, context, and critical workload status."""

    CRITICAL_SERVICES = {"auth-service", "identity-service", "payment-service"}

    def decide(self, context: dict[str, Any]) -> dict[str, Any]:
        score = float(context["analysis"]["anomaly_score"])
        service = context["cloud_metrics"].get("top_service", "unknown")
        attack_type = context["llm_explanation"].get("attack_type", "Unknown")
        is_critical = service in self.CRITICAL_SERVICES

        actions: list[str] = []
        if score > 0.8:
            actions.extend(["send_alert", "block_source"])
        elif score > 0.6:
            actions.extend(["send_alert", "monitor"])
        else:
            actions.append("monitor")

        if is_critical and score > 0.8:
            actions = [action for action in actions if action != "block_source"]
            actions.append("require_human_approval")

        lower_attack = attack_type.lower()
        if "brute" in lower_attack and score > 0.7:
            actions.append("enforce_mfa")
        if "ddos" in lower_attack or "burst" in lower_attack:
            actions.append("enable_rate_limit")
        if "exfiltration" in lower_attack and score > 0.75:
            actions.append("isolate_workload")

        deduped_actions = list(dict.fromkeys(actions))
        severity = self._severity(score)
        requires_human = "require_human_approval" in deduped_actions or severity == "critical"

        context["policy"] = {
            "severity": severity,
            "score": score,
            "top_service": service,
            "critical_service": is_critical,
            "attack_type": attack_type,
            "allowed_actions": deduped_actions,
            "requires_human_approval": requires_human,
        }
        return context

    @staticmethod
    def _severity(score: float) -> str:
        if score > 0.9:
            return "critical"
        if score > 0.8:
            return "high"
        if score > 0.6:
            return "medium"
        return "low"

