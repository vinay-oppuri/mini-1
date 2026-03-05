import json

import agents.analysis_agent as analysis_module
import agents.llm_explanation_agent as llm_module
from agents.coordinator import Coordinator


def _build_fake_pipeline(
    anomaly_score: float,
    threshold: float,
    raw_max_error: float,
    event_scores: list[float],
    sequence_scores: list[float],
    window_size: int = 20,
    padding_applied: bool = True,
):
    class _FakeInferenceResult:
        is_anomaly = True

    class _FakePipeline:
        def score(self, logs):
            _ = logs
            result = _FakeInferenceResult()
            result.anomaly_score = anomaly_score
            result.threshold = threshold
            result.raw_max_error = raw_max_error
            result.event_scores = event_scores
            result.sequence_scores = sequence_scores
            result.window_size = window_size
            result.padding_applied = padding_applied
            return result

    return _FakePipeline


def _build_fake_gemini(response_payload: dict[str, str]):
    class _FakeGeminiClient:
        def __init__(self, model="gemini-2.5-flash"):
            self.model = model

        def generate(self, prompt: str) -> str:
            _ = prompt
            return json.dumps(response_payload)

    return _FakeGeminiClient


def test_multi_agent_flow_with_mocks(monkeypatch):
    fake_pipeline = _build_fake_pipeline(
        anomaly_score=0.92,
        threshold=0.5,
        raw_max_error=0.7,
        event_scores=[0.92, 0.91],
        sequence_scores=[0.92],
    )
    fake_gemini = _build_fake_gemini(
        {
            "attack_type": "Brute Force",
            "reason": "Repeated login failures were observed.",
            "recommended_action": "Block source IP and enforce MFA.",
        }
    )

    monkeypatch.setattr(analysis_module, "InferencePipeline", fake_pipeline)
    monkeypatch.setattr(llm_module, "GeminiClient", fake_gemini)

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


def test_architecture_full_output_contract_with_mock_data(monkeypatch):
    fake_pipeline = _build_fake_pipeline(
        anomaly_score=0.96,
        threshold=0.5,
        raw_max_error=0.8,
        event_scores=[0.96, 0.95, 0.94],
        sequence_scores=[0.96],
    )
    fake_gemini = _build_fake_gemini(
        {
            "attack_type": "Brute Force",
            "reason": "Repeated login failures against admin account from one source IP.",
            "recommended_action": "Block source IP and enforce MFA for targeted users.",
        }
    )

    monkeypatch.setattr(analysis_module, "InferencePipeline", fake_pipeline)
    monkeypatch.setattr(llm_module, "GeminiClient", fake_gemini)

    logs = [
        "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
        "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
        "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
        "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
        "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
        "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
    ]

    coordinator = Coordinator()
    result = coordinator.run(
        logs=logs,
        source="mock-test",
        cloud_metrics={"service": "auth-service", "request_rate_per_sec": 12.4},
    )
    print("\nArchitecture output:\n" + json.dumps(result, indent=2))

    expected_top_level = {
        "source",
        "raw_logs",
        "cloud_metrics",
        "parsed_events",
        "event_sequence",
        "templates",
        "analysis",
        "llm_explanation",
        "policy",
        "response",
    }
    assert expected_top_level.issubset(result.keys())

    assert result["analysis"]["is_anomaly"] is True
    assert result["analysis"]["anomaly_score"] > 0.9
    assert result["llm_explanation"]["attack_type"] == "Brute Force"
    assert "Repeated login failures" in result["llm_explanation"]["reason"]
    assert result["policy"]["severity"] == "critical"
    assert result["policy"]["allowed_actions"] == ["send_alert", "block_ip", "enforce_mfa"]
    assert result["response"]["raw_actions"] == ["send_alert", "block_ip", "enforce_mfa"]
    assert "Alert sent to admin and SOC channel." in result["response"]["actions"]
    assert "IP 203.0.113.10 blocked for 10 minutes." in result["response"]["actions"]
    assert "MFA enforcement enabled for targeted account cohort." in result["response"]["actions"]
