# Multi-Agent Workflow (Project Overview)

This project processes logs through a fixed sequence of agents:

`Input Logs -> LogAgent -> AnalysisAgent -> LLMExplanationAgent -> PolicyAgent -> ResponseAgent -> Output`

## 1) Entry Point (`main.py`)

- `main.py` loads logs from JSON file input.
- If loading fails and `--mock-on-error` is enabled, it uses built-in mock logs.
- It calls `Coordinator().run(logs=..., source=...)`.
- It prints either:
  - human-readable report, or
  - full JSON (`--json`).

## 2) Coordinator (`src/agents/coordinator.py`)

- `SecurityCoordinator.process(...)` runs the architecture pipeline in this exact order:
  1. `LogAgent.collect(...)`
  2. `AnalysisAgent.analyze(...)`
  3. `LLMExplanationAgent.explain(...)`
  4. `PolicyAgent.decide(...)`
  5. `ResponseAgent.respond(...)`
- `Coordinator` is a wrapper:
  - default mode: uses the above architecture.
  - legacy mode: supports event dispatch if custom agents are passed.

## 3) LogAgent (`src/agents/log_agent.py`)

Input:
- `logs` (strings or dict records)
- optional `cloud_metrics`

What it does:
- normalizes each log into a plain text line.
- computes basic cloud metrics:
  - `service`
  - `total_logs`
  - `failed_logs`
  - `error_rate`
  - `unique_source_ips`
  - `request_rate_per_sec`

Output keys added to context:
- `source`
- `raw_logs`
- `cloud_metrics`

## 4) AnalysisAgent (`src/agents/analysis_agent.py`)

Input:
- `raw_logs`

What it does:
- parses logs into templates using `DrainParser`.
- builds event IDs and template sequence.
- gets model anomaly score from `InferencePipeline`.
- computes heuristic anomaly score from suspicious patterns.
- combines both using `max(model_score, heuristic_score)`.

Output keys added:
- `parsed_events`
- `event_sequence`
- `templates`
- `analysis`:
  - `anomaly_score`
  - `is_anomaly` (`>= 0.8`)
  - model and scoring metadata

## 5) DrainParser (`src/log_parser/drain_parser.py`)

What it does:
- lowercases text and replaces variable tokens with `<*>`:
  - IPs
  - UUIDs
  - hex IDs
  - numbers
- maps each normalized template to stable event IDs (`E1`, `E2`, ...).

Why:
- reduces log variability so model/heuristics compare patterns instead of exact values.

## 6) InferencePipeline (`src/inference/inference_pipeline.py`)

Input:
- list of log templates

What it does:
- transforms templates:
  1. `vectorizer.pkl`
  2. `svd.pkl`
  3. `scaler.pkl`
- creates fixed-size sequences for the LSTM autoencoder.
- reconstructs via model (`lstm_autoencoder.keras`).
- computes reconstruction errors.
- normalizes errors by threshold (`threshold.npy`).

Output:
- `InferenceResult` with:
  - `anomaly_score`
  - `is_anomaly`
  - `threshold`
  - per-event and per-sequence scores
  - sequence metadata

## 7) LLMExplanationAgent (`src/agents/llm_explanation_agent.py`)

Input:
- `raw_logs`, `templates`, `event_sequence`, `analysis`, `cloud_metrics`

What it does:
- computes rule-based prior attack guess:
  - `Brute Force`, `DDoS`, `Port Scan`, `Data Exfiltration`, or `Unknown`.
- builds prompt and requests Gemini (`src/llm/gemini.py`).
- parses/normalizes JSON response.
- applies safe fallback if Gemini key/request fails.

Output key added:
- `llm_explanation`:
  - `attack_type`
  - `reason`
  - `recommended_action`

## 8) PolicyAgent (`src/agents/policy_agent.py`)

Input:
- `analysis.anomaly_score`
- `llm_explanation.attack_type`

What it does:
- maps score + attack type to allowed actions.
- sets severity:
  - `critical` if `score > 0.9`
  - `high` if `score > 0.8`
  - `medium` if `score > 0.6`
  - else `low`

Output key added:
- `policy`:
  - `severity`
  - `allowed_actions`
  - `score`
  - `attack_type`

## 9) ResponseAgent (`src/agents/response_agent.py`)

Input:
- `policy.allowed_actions`
- `cloud_metrics.service`
- `raw_logs` (for suspect IP extraction)

What it does:
- turns machine actions into readable action messages.

Output key added:
- `response`:
  - `actions` (human-readable)
  - `raw_actions`

## 10) Final Output Structure

After pipeline completion, the context contains:

- `source`
- `raw_logs`
- `cloud_metrics`
- `parsed_events`
- `event_sequence`
- `templates`
- `analysis`
- `llm_explanation`
- `policy`
- `response`

