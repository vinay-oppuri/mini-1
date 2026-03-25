from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.contracts import ContractError, validate_logs_contract


def load_logs_from_path(path: Path) -> list[Any]:
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ContractError("JSON log file must contain a list.")
        return validate_logs_contract(data)

    if suffix == ".ndjson":
        entries: list[Any] = []
        with path.open("r", encoding="utf-8") as file:
            for line_no, line in enumerate(file, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise ContractError(
                        f"Invalid NDJSON at line {line_no}: {error}"
                    ) from error
        return validate_logs_contract(entries)

    with path.open("r", encoding="utf-8") as file:
        lines = [line.strip() for line in file if line.strip()]
    return validate_logs_contract(lines)
