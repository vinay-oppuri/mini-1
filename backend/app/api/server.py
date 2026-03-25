from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.core.contracts import ContractError
from app.services.analyzer import AnalyzerService


app = FastAPI(
    title="Cloud Log Anomaly Detection API",
    version="1.0.0",
)

service = AnalyzerService()


class AnalyzeRequest(BaseModel):
    logs: list[dict[str, Any] | str]
    source: str = "api"
    unknown_ratio_threshold: float = Field(default=0.30, ge=0.0, le=1.0)


class BatchItem(BaseModel):
    source: str = "api-batch-item"
    logs: list[dict[str, Any] | str]


class BatchAnalyzeRequest(BaseModel):
    items: list[BatchItem]
    unknown_ratio_threshold: float = Field(default=0.30, ge=0.0, le=1.0)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model_mode": "heuristic-fallback" if service.detector.using_fallback else "transformer",
        "threshold": service.detector.threshold,
        "max_seq_len": service.detector.max_seq_len,
        "vocab_size": service.detector.vocab_size,
    }


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    try:
        return service.analyze(
            logs=request.logs,
            source=request.source,
            unknown_ratio_threshold=request.unknown_ratio_threshold,
        )
    except (ContractError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - runtime guard
        raise HTTPException(status_code=500, detail=f"Internal error: {error}") from error


def _parse_upload(filename: str, payload: bytes) -> list[dict[str, Any] | str]:
    suffix = Path(filename).suffix.lower()
    text = payload.decode("utf-8", errors="replace")

    if suffix == ".json":
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise ContractError("Uploaded JSON must be a list.")
        return parsed

    if suffix == ".ndjson":
        items = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ContractError(
                    f"Invalid NDJSON line {line_no}: {error}"
                ) from error
        return items

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines


@app.post("/analyze/file")
async def analyze_file(
    file: UploadFile = File(...),
    source: str | None = None,
    unknown_ratio_threshold: float = 0.30,
) -> dict[str, Any]:
    try:
        payload = await file.read()
        logs = _parse_upload(file.filename or "uploaded.log", payload)
        return service.analyze(
            logs=logs,
            source=source or Path(file.filename or "uploaded").stem,
            unknown_ratio_threshold=unknown_ratio_threshold,
        )
    except (ContractError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - runtime guard
        raise HTTPException(status_code=500, detail=f"Internal error: {error}") from error


@app.post("/analyze/batch")
def analyze_batch(request: BatchAnalyzeRequest) -> dict[str, Any]:
    try:
        results = []
        for item in request.items:
            result = service.analyze(
                logs=item.logs,
                source=item.source,
                unknown_ratio_threshold=request.unknown_ratio_threshold,
            )
            results.append(
                {
                    "source": item.source,
                    "status": result.get("decision", {}).get("status"),
                    "anomaly_score": result.get("analysis", {}).get("anomaly_score"),
                    "supported": result.get("compatibility", {}).get("is_supported"),
                }
            )
        return {"count": len(results), "results": results}
    except (ContractError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - runtime guard
        raise HTTPException(status_code=500, detail=f"Internal error: {error}") from error


def run() -> None:
    import uvicorn

    host = os.getenv("ANOMALY_API_HOST", "0.0.0.0")
    port = int(os.getenv("ANOMALY_API_PORT", "8000"))
    uvicorn.run("app.api.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
