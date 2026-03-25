## AI-Driven Multi-Agent Log Anomaly Detection Backend

This backend provides:
- Transformer-based log anomaly scoring
- Multi-agent decision pipeline (monitor, analysis, policy, response, coordinator)
- Production-ready interfaces (CLI + API)
- Compatibility checks for unseen log profiles
- Benchmark and threshold calibration commands

## Architecture

1. Log ingestion (`json`, `ndjson`, or `.log`)
2. Drain parsing -> templates + event IDs
3. Sequence building
4. Transformer inference -> anomaly score
5. Policy/risk decision
6. Action response simulation

## Input Contract

For structured logs (`.json` / `.ndjson`), each entry must include:
- `timestamp`
- `level`
- `service`
- `message`

Plain `.log` files are accepted as raw text lines.

## Project Structure

```text
backend/     -> production service layer, CLI, API
agents/      -> multi-agent pipeline
parser/      -> Drain parser and HDFS parser
model/       -> transformer model + artifacts
utils/       -> sequence/dataset utilities
data/        -> sample logs and benchmark assets
tests/       -> backend tests
```

## Quick Start

### 1. Sync environment

```bash
uv sync
```

### 2. Single-file analysis (CLI)

```bash
uv run anomaly-detector analyze --logs data/raw_logs/app/cloud_workload_logs.json --output data/parsed_logs/result.json
```

### 3. Batch analysis (CLI)

```bash
uv run anomaly-detector batch --logs data/raw_logs/app/cloud_workload_large_normal.json data/raw_logs/app/cloud_workload_large_anomaly.json
```

## Production API

### Run API server

```bash
uv run anomaly-api
```

### Health check

```bash
curl http://localhost:8000/health
```

### Analyze structured logs

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d "{\"source\":\"tenant-a\",\"logs\":[{\"timestamp\":\"2026-03-24T10:00:00Z\",\"level\":\"INFO\",\"service\":\"api-gateway\",\"message\":\"Request completed status=200\"}]}"
```

### Analyze by file upload

```bash
curl -X POST "http://localhost:8000/analyze/file?source=tenant-a" \
  -F "file=@data/raw_logs/app/cloud_workload_large_anomaly.json"
```

## Compatibility Guard

The service computes `unknown_event_ratio` from parsed templates.  
If unknown ratio exceeds threshold (default `0.30`), response status becomes:
- `unsupported_log_profile`

This prevents overconfident results on out-of-distribution logs.

## Benchmark Suite

```bash
uv run anomaly-detector benchmark --manifest data/benchmarks/manifest.json --output data/parsed_logs/benchmark_report.json
```

## Threshold Calibration

```bash
uv run anomaly-detector calibrate-threshold \
  --normal data/raw_logs/app/cloud_workload_large_normal.json \
  --anomaly data/raw_logs/app/cloud_workload_large_anomaly.json \
  --metadata model/model_metadata.json
```

## Docker

Build and run from `backend/`:

```bash
docker build -t cloud-anomaly-detector .
docker run --rm -p 8000:8000 cloud-anomaly-detector
```
