from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List


OUTPUT_PATH = Path("data/raw_logs/app/cloud_workload_logs.json")

SERVICES = ["auth-service", "api-gateway", "k8s-pod-a", "ml-trainer"]
USERS = ["alice", "bob", "carol", "dave", "admin"]
INTERNAL_IPS = [f"10.0.1.{i}" for i in range(10, 50)]
EXTERNAL_IPS = [f"203.0.113.{i}" for i in range(10, 90)]


def generate_cloud_logs(total_logs: int = 120, seed: int = 7) -> List[Dict[str, str]]:
    random.seed(seed)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    logs: List[Dict[str, str]] = []

    for idx in range(total_logs):
        ts = now + timedelta(seconds=idx)
        service = random.choice(SERVICES)
        user = random.choice(USERS)
        ip = random.choice(INTERNAL_IPS)

        if idx % 35 == 0:
            # DDoS burst on API gateway
            for burst in range(8):
                logs.append(
                    {
                        "timestamp": (ts + timedelta(milliseconds=burst * 150)).isoformat(),
                        "level": "WARN",
                        "service": "api-gateway",
                        "message": (
                            f"Too many requests from {random.choice(EXTERNAL_IPS)} "
                            f"status=503 rps={random.randint(900, 1600)}"
                        ),
                    }
                )
            continue

        if idx % 27 == 0:
            # Brute-force streak
            for attempt in range(5):
                logs.append(
                    {
                        "timestamp": (ts + timedelta(seconds=attempt)).isoformat(),
                        "level": "ERROR",
                        "service": "auth-service",
                        "message": f"Login failed for user {user} from IP {random.choice(EXTERNAL_IPS)}",
                    }
                )
            continue

        if idx % 41 == 0:
            # Data exfil style event
            logs.append(
                {
                    "timestamp": ts.isoformat(),
                    "level": "ERROR",
                    "service": "ml-trainer",
                    "message": (
                        f"Suspicious outbound transfer 1.4GB from pod to {random.choice(EXTERNAL_IPS)}"
                    ),
                }
            )
            continue

        if idx % 33 == 0:
            # Port scan style event
            port = random.choice([22, 23, 80, 443, 3306, 5432, 8080, 27017])
            logs.append(
                {
                    "timestamp": ts.isoformat(),
                    "level": "WARN",
                    "service": "k8s-pod-a",
                    "message": f"Port scan probe from {random.choice(EXTERNAL_IPS)} to port {port}",
                }
            )
            continue

        logs.append(
            {
                "timestamp": ts.isoformat(),
                "level": "INFO",
                "service": service,
                "message": f"User {user} accessed workload from {ip}",
            }
        )

    return logs


def main() -> None:
    logs = generate_cloud_logs(total_logs=120)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(logs, file, indent=2)
    print(f"Generated {len(logs)} cloud logs at {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

