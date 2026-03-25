from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.cli.benchmark import run_benchmark
from app.services.threshold import calibrate_threshold
from app.services.analyzer import AnalyzerService


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def _cmd_analyze(args: argparse.Namespace, service: AnalyzerService) -> int:
    result = service.analyze_file(
        path=args.logs,
        source=args.source,
        unknown_ratio_threshold=args.unknown_ratio_threshold,
    )
    if args.output:
        _save_json(Path(args.output), result)
        print(f"Saved analysis: {args.output}")
    else:
        print(json.dumps(result, indent=2))
    return 0


def _cmd_batch(args: argparse.Namespace, service: AnalyzerService) -> int:
    results = []
    for log_path in args.logs:
        result = service.analyze_file(
            path=log_path,
            source=Path(log_path).stem,
            unknown_ratio_threshold=args.unknown_ratio_threshold,
        )
        results.append(
            {
                "path": log_path,
                "status": result.get("decision", {}).get("status"),
                "anomaly_score": result.get("analysis", {}).get("anomaly_score"),
                "supported": result.get("compatibility", {}).get("is_supported"),
            }
        )

    payload = {"count": len(results), "results": results}
    if args.output:
        _save_json(Path(args.output), payload)
        print(f"Saved batch report: {args.output}")
    else:
        print(json.dumps(payload, indent=2))
    return 0


def _cmd_benchmark(args: argparse.Namespace, service: AnalyzerService) -> int:
    report = run_benchmark(service=service, manifest_path=args.manifest)
    if args.output:
        _save_json(Path(args.output), report)
        print(f"Saved benchmark report: {args.output}")
    else:
        print(json.dumps(report, indent=2))
    return 0


def _cmd_calibrate(args: argparse.Namespace, service: AnalyzerService) -> int:
    report = calibrate_threshold(
        service=service,
        normal_files=args.normal,
        anomaly_files=args.anomaly,
        metadata_path=args.metadata,
        output_metadata_path=args.output_metadata,
    )
    print(json.dumps(report, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anomaly-detector",
        description="Production CLI for cloud log anomaly detection",
    )

    parser.add_argument("--model", default="model/model.pt", help="Model checkpoint path")
    parser.add_argument(
        "--metadata",
        default="model/model_metadata.json",
        help="Model metadata path",
    )
    parser.add_argument(
        "--unknown-ratio-threshold",
        type=float,
        default=0.30,
        help="Maximum unknown event ratio before returning unsupported_log_profile",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Analyze one log file")
    analyze.add_argument("--logs", required=True, help="Path to input log file")
    analyze.add_argument("--source", default=None, help="Custom source label")
    analyze.add_argument("--output", default=None, help="Output JSON path")

    batch = sub.add_parser("batch", help="Analyze multiple log files")
    batch.add_argument("--logs", nargs="+", required=True, help="List of log files")
    batch.add_argument("--output", default=None, help="Output JSON path")

    benchmark = sub.add_parser("benchmark", help="Run benchmark suite from manifest")
    benchmark.add_argument(
        "--manifest",
        default="data/benchmarks/manifest.json",
        help="Benchmark manifest JSON path",
    )
    benchmark.add_argument("--output", default=None, help="Output JSON path")

    calibrate = sub.add_parser("calibrate-threshold", help="Calibrate model threshold")
    calibrate.add_argument("--normal", nargs="+", required=True, help="Normal log files")
    calibrate.add_argument("--anomaly", nargs="+", required=True, help="Anomaly log files")
    calibrate.add_argument(
        "--output-metadata",
        default=None,
        help="Where to write calibrated metadata (defaults to --metadata path)",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    service = AnalyzerService(
        model_path=args.model,
        metadata_path=args.metadata,
        default_unknown_ratio_threshold=args.unknown_ratio_threshold,
    )

    if args.command == "analyze":
        return _cmd_analyze(args, service)
    if args.command == "batch":
        return _cmd_batch(args, service)
    if args.command == "benchmark":
        return _cmd_benchmark(args, service)
    if args.command == "calibrate-threshold":
        return _cmd_calibrate(args, service)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
