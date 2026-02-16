from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from security.log_parser import LogParser
from detection.feature_extraction import FeatureExtractor
from detection.anomoly_models.isolation_forest import IsolationForestDetector
from detection.scoring import AnalomyScorer
from detection.thresholds import ThresholdManager


def main() -> None:
    log_path = PROJECT_ROOT / "data" / "raw_logs" / "app" / "sample_logs.json"

    print("Parsing logs...")
    parser = LogParser()
    logs = parser.parse_files(str(log_path))
    print(f"Loaded {len(logs)} logs")

    if not logs:
        print("No valid logs found. Exiting.")
        return

    print("Extracting features...")
    extractor = FeatureExtractor()
    X = extractor.extract_features(logs)
    print(f"Extracted features with shape: {X.shape}")

    print("Training Isolation Forest model...")
    detector = IsolationForestDetector()
    detector.train(X)
    print("Model trained successfully.")

    labels, scores = detector.predict(X)

    print("Scoring anomalies...")
    scorer = AnalomyScorer()
    confidence = scorer.compute_confidence(scores)
    print("Anomaly scoring completed.")

    threshold_manager = ThresholdManager(threshold=0.85)
    anomalies = threshold_manager.apply(confidence)

    print("\n-----------------Detected anomalies:---------------------\n")
    for i, is_anomaly in enumerate(anomalies):
        if is_anomaly:
            event = {
                "type": "anomaly_detected",
                "label": int(labels[i]),
                "confidence": float(confidence[i]),
                "source": "log_detector",
                "log": logs[i],
            }
            print(event)


if __name__ == "__main__":
    main()
