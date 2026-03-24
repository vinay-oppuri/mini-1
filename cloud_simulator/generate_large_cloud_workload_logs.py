from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


SERVICES = [
    "api-gateway",
    "auth-service",
    "billing-service",
    "inventory-service",
    "order-service",
    "worker-scheduler",
]

REGIONS = ["us-east-1", "us-west-2", "eu-west-1"]
USERS = ["alice", "bob", "carol", "dave", "maria", "nina", "omar", "admin"]
ENDPOINTS = [
    "/api/v1/orders",
    "/api/v1/products",
    "/api/v1/payments",
    "/api/v1/login",
    "/api/v1/checkout",
]


def _trace_id(i: int) -> str:
    return f"tr-{i:08d}"


def _request_id(i: int) -> str:
    return f"rq-{i:08d}"


def _make_entry(
    ts: datetime,
    level: str,
    service: str,
    message: str,
    region: str,
    host: str,
    trace_id: str,
    request_id: str,
) -> dict[str, str]:
    return {
        "timestamp": ts.isoformat(),
        "level": level,
        "service": service,
        "region": region,
        "host": host,
        "trace_id": trace_id,
        "request_id": request_id,
        "message": message,
    }


def generate_normal_logs(count: int, start: datetime) -> list[dict[str, str]]:
    # Seed templates so the dominant template becomes event E4 during parsing.
    logs: list[dict[str, str]] = [
        _make_entry(
            start,
            "INFO",
            "api-gateway",
            "Request completed method=GET endpoint=/api/v1/products status=200 latency_ms=42",
            "us-east-1",
            "api-node-12",
            _trace_id(0),
            _request_id(0),
        ),
        _make_entry(
            start + timedelta(seconds=1),
            "INFO",
            "auth-service",
            "User login succeeded user=alice source_ip=10.0.31.14 method=password",
            "us-east-1",
            "auth-node-03",
            _trace_id(1),
            _request_id(1),
        ),
        _make_entry(
            start + timedelta(seconds=2),
            "INFO",
            "billing-service",
            "Payment authorization completed provider=stripe amount_usd=129 order_id=483920",
            "us-east-1",
            "bill-node-07",
            _trace_id(2),
            _request_id(2),
        ),
    ]

    for i in range(3, count):
        ts = start + timedelta(seconds=i)
        region = random.choice(REGIONS)
        host = f"worker-node-{random.randint(10, 55)}"
        message = (
            "Queue heartbeat healthy queue=order-dispatch lag_ms="
            f"{random.randint(2, 14)} inflight_jobs={random.randint(20, 90)}"
        )
        logs.append(
            _make_entry(
                ts,
                "INFO",
                "worker-scheduler",
                message,
                region,
                host,
                _trace_id(i),
                _request_id(i),
            )
        )

    return logs


def generate_anomaly_logs(count: int, start: datetime) -> list[dict[str, str]]:
    logs: list[dict[str, str]] = []

    for i in range(count):
        ts = start + timedelta(seconds=i)
        region = random.choice(REGIONS)
        host = f"edge-node-{random.randint(1, 20)}"
        source_ip = f"203.0.113.{random.randint(10, 220)}"

        if i < int(count * 0.75) or i >= count - 220:
            # Dominant suspicious template to force anomaly behavior.
            message = (
                f"Login failed for user admin from IP {source_ip} "
                f"reason=invalid_password retry_count={random.randint(3, 9)}"
            )
            logs.append(
                _make_entry(
                    ts,
                    "ERROR",
                    "auth-service",
                    message,
                    region,
                    host,
                    _trace_id(i),
                    _request_id(i),
                )
            )
            continue

        # Additional correlated attack signals.
        if i % 3 == 0:
            message = (
                f"Too many requests from {source_ip} status=503 rps={random.randint(1400, 3800)} "
                f"endpoint=/api/v1/login"
            )
            service = "api-gateway"
            level = "WARN"
        elif i % 3 == 1:
            message = (
                f"Suspicious outbound transfer {random.randint(2, 8)}.4GB to {source_ip} "
                "destination_country=unknown"
            )
            service = "billing-service"
            level = "ERROR"
        else:
            message = (
                "Privilege escalation attempt detected principal=service-account-ci "
                "action=cluster-admin-bind"
            )
            service = "auth-service"
            level = "CRITICAL"

        logs.append(
            _make_entry(
                ts,
                level,
                service,
                message,
                region,
                host,
                _trace_id(i),
                _request_id(i),
            )
        )

    return logs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate large realistic cloud workload logs.")
    parser.add_argument("--count", type=int, default=2500, help="Number of entries per file")
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("data/raw_logs/app"),
        help="Output directory",
    )
    args = parser.parse_args()

    random.seed(42)
    args.outdir.mkdir(parents=True, exist_ok=True)

    start = datetime(2026, 3, 24, 8, 0, 0, tzinfo=timezone.utc)
    normal_logs = generate_normal_logs(args.count, start)
    anomaly_logs = generate_anomaly_logs(args.count, start + timedelta(hours=2))

    normal_path = args.outdir / "cloud_workload_large_normal.json"
    anomaly_path = args.outdir / "cloud_workload_large_anomaly.json"

    with normal_path.open("w", encoding="utf-8") as file:
        json.dump(normal_logs, file, indent=2)
    with anomaly_path.open("w", encoding="utf-8") as file:
        json.dump(anomaly_logs, file, indent=2)

    print(f"Generated normal log file: {normal_path} ({len(normal_logs)} entries)")
    print(f"Generated anomaly log file: {anomaly_path} ({len(anomaly_logs)} entries)")


if __name__ == "__main__":
    main()
