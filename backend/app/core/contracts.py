from __future__ import annotations

from typing import Any


REQUIRED_LOG_KEYS = ("timestamp", "level", "service", "message")


class ContractError(ValueError):
    """Raised when user-provided logs do not match the input contract."""


def validate_logs_contract(logs: list[Any]) -> list[Any]:
    if not isinstance(logs, list):
        raise ContractError("Input logs must be a list of log entries.")
    if not logs:
        raise ContractError("Input logs are empty.")

    validated: list[Any] = []
    for index, entry in enumerate(logs):
        if isinstance(entry, str):
            text = entry.strip()
            if not text:
                raise ContractError(f"Log line at index {index} is empty.")
            validated.append(text)
            continue

        if not isinstance(entry, dict):
            raise ContractError(
                f"Log entry at index {index} must be either a string or an object."
            )

        missing = [key for key in REQUIRED_LOG_KEYS if key not in entry]
        if missing:
            raise ContractError(
                f"Log entry at index {index} is missing required fields: {', '.join(missing)}"
            )

        for key in REQUIRED_LOG_KEYS:
            value = entry.get(key)
            if value is None or str(value).strip() == "":
                raise ContractError(
                    f"Log entry at index {index} has an empty required field: {key}"
                )

        validated.append(entry)

    return validated

