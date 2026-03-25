from __future__ import annotations

import pytest

from app.core.contracts import ContractError, validate_logs_contract


def test_validate_logs_contract_accepts_valid_entries() -> None:
    logs = [
        {
            "timestamp": "2026-03-24T10:00:00Z",
            "level": "INFO",
            "service": "api-gateway",
            "message": "Request completed status=200",
        }
    ]
    validated = validate_logs_contract(logs)
    assert len(validated) == 1
    assert validated[0]["service"] == "api-gateway"


def test_validate_logs_contract_rejects_missing_required_fields() -> None:
    logs = [
        {
            "timestamp": "2026-03-24T10:00:00Z",
            "level": "INFO",
            "service": "api-gateway",
        }
    ]
    with pytest.raises(ContractError):
        validate_logs_contract(logs)
