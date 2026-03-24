## AI-Driven Multi-Agent Log Anomaly Detection for Cloud Workloads

This project implements the full workflow:

1. `LogMonitoringAgent` reads raw cloud logs.
2. `DrainParser` converts logs to templates (`Error block <*> failed`) and event IDs (`E1`, `E2`, ...).
3. `SequenceBuilder` converts event IDs into model-ready event sequences.
4. `TransformerAnomalyDetector` returns anomaly score (0.0 to 1.0).
5. `PolicyAgent` applies response rules.
6. `ResponseAgent` simulates actions.
7. `CoordinatorAgent` orchestrates all agents, including human-in-the-loop for high-risk cases.

### Project Structure

```text
project/
├── agents/
├── data/
│   ├── raw_logs/
│   └── parsed_logs/
├── model/
├── parser/
├── utils/
└── main.py
```

### Run

```bash
python main.py
```

Or with a custom log file:

```bash
python main.py --logs data/raw_logs/app/cloud_workload_logs.json
```

Detailed run output is saved to `data/parsed_logs/last_run_output.json`.

If `torch` is not available in your current Python interpreter, the system will still run with a heuristic fallback detector.  
For full transformer inference with the provided checkpoint, run with your project venv Python (for example on Windows: `.venv\Scripts\python.exe main.py`).
