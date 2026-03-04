import json

import agents.analysis_agent as analysis_module
import agents.llm_explanation_agent as llm_module
from agents.coordinator import Coordinator


def test_multi_agent_flow_with_mocks(monkeypatch):
    class _FakeInferenceResult:
        anomaly_score = 0.92
        is_anomaly = True
        threshold = 0.5
        raw_max_error = 0.7
        event_scores = [0.92, 0.91]
        sequence_scores = [0.92]
        window_size = 20
        padding_applied = True

    class _FakePipeline:
        def score(self, logs):
            return _FakeInferenceResult()

    class _FakeGeminiClient:
        def __init__(self, model="gemini-2.5-flash"):
            self.model = model

        def generate(self, prompt: str) -> str:
            return json.dumps(
                {
                    "attack_type": "Brute Force",
                    "reason": "Repeated login failures were observed.",
                    "recommended_action": "Block source IP and enforce MFA.",
                }
            )

    monkeypatch.setattr(analysis_module, "InferencePipeline", _FakePipeline)
    monkeypatch.setattr(llm_module, "GeminiClient", _FakeGeminiClient)

    logs = [
        "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
        "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
        "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
        "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
        "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
    ]

    coordinator = Coordinator()
    result = coordinator.run(logs=logs, source="test")

    assert "analysis" in result
    assert "llm_explanation" in result
    assert "policy" in result
    assert "response" in result
    assert result["analysis"]["anomaly_score"] >= 0.9
    assert result["llm_explanation"]["attack_type"] == "Brute Force"
    assert result["policy"]["severity"] in {"high", "critical"}
    assert result["response"]["actions"]

