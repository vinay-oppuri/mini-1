from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.agents.coordinator import CoordinatorAgent


DEFAULT_LOG_FILE = Path("data/raw_logs/app/cloud_workload_logs.json")
DEFAULT_OUTPUT_FILE = Path("data/parsed_logs/last_run_output.json")

def load_logs(path: Path) -> tuple[list[Any], str]:
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("JSON log file must be an array of entries")
        return data, "REAL DATA"

    with path.open("r", encoding="utf-8") as file:
        lines = [line.strip() for line in file if line.strip()]
    if not lines:
        raise ValueError("Text log file is empty")
    return lines, "REAL DATA"


def print_report(result: dict[str, Any], data_source: str) -> None:
    analysis = result["analysis"]
    llm = result["llm_explanation"]
    policy = result["policy"]
    response = result["response"]
    metrics = result["cloud_metrics"]

    print(f"\nData Source: {data_source}")

    print("\nAnomaly Status:")
    print("ANOMALY DETECTED!" if analysis["is_anomaly"] else "No critical anomaly")
    print(f"Anomaly Score: {analysis['anomaly_score']:.4f}")
    print(f"Model Mode: {analysis.get('model_mode', 'unknown')}")

    print("\nTop Service:")
    print(metrics["top_service"])

    print("\nLLM Explanation:")
    print(f"Type: {llm['attack_type']}")
    print(f"Reason: {llm['reason']}")

    print("\nPolicy Decision:")
    print(f"Severity: {policy['severity']}")
    print(f"Need Human Approval: {policy['requires_human_approval']}")

    print("\nResponse Actions:")
    if response["actions"]:
        for action in response["actions"]:
            print(f"- {action}")
    else:
        print("- No action required")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI-Driven Multi-Agent Log Anomaly Detection for Cloud Workloads"
    )
    parser.add_argument("--logs", type=Path, default=DEFAULT_LOG_FILE, help="Path to input logs")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Where to save coordinator output JSON",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    coordinator = CoordinatorAgent()
    try:
        logs, data_source = load_logs(args.logs)
        result = coordinator.run(logs=logs, source=args.logs.stem)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as file:
            json.dump(result, file, indent=2)

        print_report(result, data_source)
        print(f"\nSaved detailed result to: {args.output}")
    except Exception as error:
        print(f"Error: Could not process logs from {args.logs}: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
