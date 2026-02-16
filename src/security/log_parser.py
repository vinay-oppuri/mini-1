import json
from typing import List, Dict



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

        with open(filePath, "r", encoding="utf-8") as f:
            raw_data = f.read().strip()

        if not raw_data:
            return logs

        try:
            parsed = json.loads(raw_data)
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, dict):
            if self._validate(parsed):
                logs.append(self._normalize(parsed))
            return logs

        if isinstance(parsed, list):
            for log in parsed:
                if isinstance(log, dict) and self._validate(log):
                    logs.append(self._normalize(log))
            return logs

        for line in raw_data.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                log = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(log, dict) and self._validate(log):
                logs.append(self._normalize(log))

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
