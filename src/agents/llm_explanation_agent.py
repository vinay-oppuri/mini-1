from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Sequence

from llm.gemini import GeminiClient


_ATTACK_TYPES = {
    "Brute Force",
    "DDoS",
    "Port Scan",
    "Data Exfiltration",
    "Unknown",
}


class LLMExplanationAgent:
    """
    Uses Gemini for explanation/classification with robust JSON normalization.
    """

    def __init__(self) -> None:
        self._client_error: Optional[Exception] = None
        self.client: Optional[GeminiClient] = None
        try:
            self.client = GeminiClient()
        except Exception as exc:  # pragma: no cover - depends on local key config
            self._client_error = exc

    def explain(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logs = context.get("raw_logs", [])
        templates = context.get("templates", [])
        sequence = context.get("event_sequence", [])
        analysis = context.get("analysis", {})
        cloud_metrics = context.get("cloud_metrics", {})
        score = float(analysis.get("anomaly_score", 0.0))

        rule = self._rule_based_guess(logs=logs, templates=templates, score=score)

        prompt = self._build_prompt(
            logs=logs,
            templates=templates,
            sequence=sequence,
            cloud_metrics=cloud_metrics,
            anomaly_score=score,
            rule_guess=rule,
        )

        llm_result: Dict[str, Any]
        if self.client is None:
            llm_result = self._fallback_response(
                attack_type=rule["attack_type"],
                reason=f"Gemini unavailable: {self._client_error}. Rule evidence: {rule['reason']}",
            )
        else:
            try:
                raw = self.client.generate(prompt)
                llm_result = self._normalize_response(raw, rule)
            except Exception as exc:  # pragma: no cover - network/quota dependent
                llm_result = self._fallback_response(
                    attack_type=rule["attack_type"],
                    reason=f"Gemini request failed: {exc}. Rule evidence: {rule['reason']}",
                )

        context["llm_explanation"] = llm_result
        return context

    def _build_prompt(
        self,
        logs: Sequence[str],
        templates: Sequence[str],
        sequence: Sequence[str],
        cloud_metrics: Dict[str, Any],
        anomaly_score: float,
        rule_guess: Dict[str, str],
    ) -> str:
        log_excerpt = "\n".join(list(logs)[-20:])
        template_excerpt = "\n".join(list(templates)[-20:])
        sequence_excerpt = ", ".join(sequence[-30:])

        return f"""
You are a senior cloud security analyst.

You must analyze an anomaly and return VALID JSON only.

Input:
- anomaly_score: {anomaly_score:.4f}
- cloud_metrics: {json.dumps(cloud_metrics, ensure_ascii=True)}
- event_sequence: [{sequence_excerpt}]
- event_templates:
{template_excerpt}
- raw_logs:
{log_excerpt}

Rule-based prior:
- attack_type: {rule_guess["attack_type"]}
- reason: {rule_guess["reason"]}

Return JSON exactly:
{{
  "attack_type": "Brute Force|DDoS|Port Scan|Data Exfiltration|Unknown",
  "reason": "short concrete explanation tied to logs/metrics",
  "recommended_action": "specific containment action"
}}
""".strip()

    def _normalize_response(self, raw: str, rule_guess: Dict[str, str]) -> Dict[str, str]:
        parsed = self._parse_json_object(raw) or {}
        attack_type = str(parsed.get("attack_type", "")).strip()
        reason = str(parsed.get("reason", "")).strip()
        recommended_action = str(parsed.get("recommended_action", "")).strip()

        rule_type = rule_guess.get("attack_type", "Unknown")
        rule_confidence = rule_guess.get("confidence", "low")

        if attack_type not in _ATTACK_TYPES:
            attack_type = rule_type
        elif (
            rule_type in _ATTACK_TYPES
            and rule_type != "Unknown"
            and rule_confidence == "high"
            and attack_type != rule_type
        ):
            attack_type = rule_type
        if not reason:
            reason = rule_guess["reason"]
        elif rule_guess["reason"]:
            reason = f"{reason} Rule evidence: {rule_guess['reason']}"
        if not recommended_action:
            recommended_action = self._default_action(attack_type)

        return {
            "attack_type": attack_type,
            "reason": reason,
            "recommended_action": recommended_action,
        }

    def _rule_based_guess(
        self,
        logs: Sequence[str],
        templates: Sequence[str],
        score: float,
    ) -> Dict[str, str]:
        combined = "\n".join(list(logs) + list(templates)).lower()
        failed = len(re.findall(r"failed|invalid password|authentication failed|unauthorized", combined))
        ddos = len(re.findall(r"too many requests|traffic spike|flood|rate limit|status 503|status 429", combined))
        scan = len(re.findall(r"port|scan|probe|connection refused", combined))
        exfil = len(re.findall(r"exfil|outbound|bytes sent|upload|sensitive data", combined))

        pairs = [
            ("Brute Force", failed),
            ("DDoS", ddos),
            ("Port Scan", scan),
            ("Data Exfiltration", exfil),
        ]
        pairs.sort(key=lambda item: item[1], reverse=True)
        best_type, best_hits = pairs[0]

        if score < 0.6 and best_hits < 3:
            return {
            "attack_type": "Unknown",
            "confidence": "low",
            "reason": "Insufficient confidence and weak attack-specific indicators.",
        }

        if best_hits == 0:
            return {
                "attack_type": "Unknown",
                "confidence": "low",
                "reason": "No clear attack signatures in templates/log text.",
            }

        reasons = {
            "Brute Force": "Repeated authentication failures against account access.",
            "DDoS": "Traffic flood/rate-limit indicators suggest service saturation.",
            "Port Scan": "Multiple probing/port indicators suggest reconnaissance.",
            "Data Exfiltration": "Outbound transfer/exfiltration markers are present.",
        }
        confidence = "high" if best_hits >= 5 else "medium"
        return {
            "attack_type": best_type,
            "confidence": confidence,
            "reason": reasons[best_type],
        }

    def _parse_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"\s*```$", "", candidate)

        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", candidate)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    def _fallback_response(self, attack_type: str, reason: str) -> Dict[str, str]:
        safe_type = attack_type if attack_type in _ATTACK_TYPES else "Unknown"
        return {
            "attack_type": safe_type,
            "reason": reason,
            "recommended_action": self._default_action(safe_type),
        }

    def _default_action(self, attack_type: str) -> str:
        defaults = {
            "Brute Force": "Temporarily block offending IP and enforce MFA on targeted accounts.",
            "DDoS": "Apply rate limiting/WAF rules and scale DDoS mitigation controls.",
            "Port Scan": "Block scanner IP, tighten firewall policy, and audit exposed ports.",
            "Data Exfiltration": "Isolate workload, block outbound channel, and initiate incident response.",
            "Unknown": "Escalate to SOC, increase telemetry, and continue investigation.",
        }
        return defaults.get(attack_type, defaults["Unknown"])
