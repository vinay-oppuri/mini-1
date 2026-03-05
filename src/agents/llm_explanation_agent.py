import json

from llm.gemini import GeminiClient


class LLMExplanationAgent:
    def __init__(self):
        try:
            self.client = GeminiClient()
        except Exception:
            self.client = None

    def explain(self, context):
        logs = context["raw_logs"]
        score = context["analysis"]["anomaly_score"]

        attack_type = self.guess_attack(logs)

        prompt = f"""
You are a cybersecurity expert.

Logs:
{logs}

Anomaly score: {score}

What attack is this?

Return JSON:
{{
 "attack_type": "...",
 "reason": "...",
 "recommended_action": "..."
}}
"""

        if self.client:
            try:
                raw = self.client.generate(prompt)
                response = self.parse_json(raw)
            except Exception:
                response = None
        else:
            response = None

        if not isinstance(response, dict):
            response = {
                "attack_type": attack_type,
                "reason": "Gemini unavailable, rule-based guess used",
                "recommended_action": "Investigate logs",
            }

        if "attack_type" not in response:
            response["attack_type"] = attack_type
        if "reason" not in response:
            response["reason"] = "No reason returned by model."
        if "recommended_action" not in response:
            response["recommended_action"] = "Investigate logs"

        context["llm_explanation"] = response
        return context

    def parse_json(self, raw_text):
        if isinstance(raw_text, dict):
            return raw_text

        text = str(raw_text).strip()

        # remove markdown fences if model returns ```json ... ```
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(text)
        except Exception:
            return None

    def guess_attack(self, logs):
        text = " ".join(logs).lower()

        if "login failed" in text:
            return "Brute Force"

        if "too many requests" in text:
            return "DDoS"

        if "port scan" in text:
            return "Port Scan"

        if "outbound transfer" in text or "exfil" in text:
            return "Data Exfiltration"

        return "Unknown"
