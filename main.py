from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agents.coordinator import Coordinator  # noqa: E402


def load_logs(path: Path) -> List[Dict[str, Any] | str]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return [payload]
    raise ValueError(f"Unsupported log file format in {path}.")


def print_report(result: Dict[str, Any]) -> None:
    analysis = result.get("analysis", {})
    llm = result.get("llm_explanation", {})
    policy = result.get("policy", {})
    response = result.get("response", {})
    metrics = result.get("cloud_metrics", {})

    status = "ANOMALY DETECTED" if analysis.get("is_anomaly") else "NO CRITICAL ANOMALY"
    service = metrics.get("service", "unknown")
    score = float(analysis.get("anomaly_score", 0.0))

    print()
    print(status)
    print()
    print(f"Service: {service}")
    print(f"Score: {score:.2f}")
    print()
    print("Gemini Analysis:")
    print(f"Attack Type: {llm.get('attack_type', 'Unknown')}")
    print(f"Reason: {llm.get('reason', 'N/A')}")
    print()
    print("Action:")
    actions = response.get("actions", [])
    if not actions:
        print("- No action")
    else:
        for item in actions:
            print(f"- {item}")
    print()
    print(f"Severity: {policy.get('severity', 'unknown')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-Driven Multi-Agent Log Anomaly Detection")
    parser.add_argument(
        "--input",
        type=str,
        default="data/raw_logs/app/cloud_workload_logs.json",
        help="Path to JSON logs file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    log_path = (PROJECT_ROOT / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input)

    if not log_path.exists():
        raise FileNotFoundError(
            f"{log_path} not found. Generate sample logs with: uv run cloud_simulator/generate_logs.py"
        )

    logs = load_logs(log_path)
    coordinator = Coordinator()
    result = coordinator.run(logs=logs, source="cloud-workload")
    print_report(result)


if __name__ == "__main__":
    main()

