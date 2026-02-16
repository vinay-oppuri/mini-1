from typing import List, Dict
from collections import Counter
import numpy as np



class FeatureExtractor:
    def extract_features(self, logs: List[Dict]) -> np.ndarray:
        features = []

        user_counts = Counter(log["user"] for log in logs)
        ip_counts = Counter(log["ip"] for log in logs)

        for log in logs:
            feature_vector = [
                user_counts[log["user"]],
                ip_counts[log["ip"]],
                1 if log["status"] == "failed" else 0,
                self._encode_event_type(log["event_type"])
            ]

            features.append(feature_vector)
        
        return np.array(features)
    

    def _encode_event_type(self, event_type: str) -> int:
        mapping = {
            "login" : 0,
            "logout" : 1,
            "file_access" : 2,
            "config_change" : 3
        }

        return mapping.get(event_type, 99)
