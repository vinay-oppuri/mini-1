import json
from typing import List, Dict, Any



class LogParser:

    REQUIRED_FIELDS = [
        "timestamp",
        "user",
        "ip",
        "event_type",
        "resource",
        "status"
    ]

    def parse_files(self, filePath: str) -> List[Dict]:
        logs = []

        with open(filePath, "r") as f:
            for line in f:
                try:
                    log = json.loads(line.strip())

                    if self._validate(log):
                        logs.append(self._normalize(log))

                except json.JSONDecodeError:
                    continue

        return logs
    

    def _validate(self, log: Dict) -> bool:
        return all(field in log for field in self.REQUIRED_FIELDS)

    def _normalize(self, log: Dict) -> Dict:
        return {
            "timestamp": log["timestamp"],
            "user": str(log["user"]).lower(),
            "ip": log["ip"],
            "event_type": str(log["event_type"]).lower(),
            "resource": str(log["resource"]).lower(),
            "status": str(log["status"]).lower()
        }