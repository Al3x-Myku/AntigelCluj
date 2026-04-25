"""Anomaly detector — Isolation Forest."""

import os
import logging
import pickle
import numpy as np
from pathlib import Path
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent / "ml" / "iforest_model.pkl"
N_FEATURES = 8
# Decision function threshold invert: > 0.0 is anomalous
THRESHOLD = 0.0

# Cached model
_model = None

def get_model():
    """Load or return cached Isolation Forest model."""
    global _model
    if _model is not None:
        return _model, None

    if MODEL_PATH.exists():
        with open(MODEL_PATH, "rb") as f:
            data = pickle.load(f)
            _model = data["model"]
            logger.info(f"Loaded Isolation Forest model from {MODEL_PATH}")
            return _model, None

    return None, None


def train_model(feature_vectors: list[list[float]]) -> dict:
    """
    Fit IsolationForest on feature vectors (normal login history).
    Returns training stats.
    """
    global _model

    X = np.array(feature_vectors, dtype=np.float64)

    if len(X) < 10:
        raise ValueError(f"Need at least 10 samples, got {len(X)}")

    # Fit Isolation Forest. Contamination sets outline ratio.
    clf = IsolationForest(random_state=42, contamination=0.05)
    clf.fit(X)

    _model = clf

    # Save model
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": clf}, f)

    # Compute anomaly scores on training data
    # Invert decision function: higher is more anomalous
    raw_scores = clf.decision_function(X)
    distances = -1.0 * raw_scores

    stats = {
        "n_samples": len(X),
        "n_features": N_FEATURES,
        "threshold": round(THRESHOLD, 4),
        "mean_score": round(float(np.mean(distances)), 4),
        "max_score": round(float(np.max(distances)), 4),
        "anomalies_in_training": int(np.sum(distances > THRESHOLD)),
        "model_path": str(MODEL_PATH),
    }
    logger.info(f"Isolation Forest model trained: {stats}")
    return stats


def _scale_distance(distance: float) -> float:
    """Scale raw Isolation Forest distance [-0.5, 0.5] to a [0.0, 1.0] probability-like score via sigmoid."""
    import math
    # Factor 15 makes a distance of 0 -> 0.5, 0.1 -> 0.81, -0.1 -> 0.18
    # This stretches the small IF variations perfectly for the UI.
    return round(1.0 / (1.0 + math.exp(-15.0 * distance)), 4)


def score_event(feature_vector: list[float]) -> tuple[float, bool]:
    """
    Compute Anomaly Score for a single login event.
    Returns (score, is_anomalous).
    """
    model, _ = get_model()

    if model is None:
        # No model trained yet — return neutral score
        logger.warning("No Isolation Forest model available — returning score -1.0")
        return -1.0, False

    X = np.array([feature_vector], dtype=np.float64)
    # Invert decision function
    distance = float(-model.decision_function(X)[0])
    is_anomalous = distance > THRESHOLD

    return _scale_distance(distance), is_anomalous


def score_batch(feature_vectors: list[list[float]]) -> list[tuple[float, bool]]:
    """Score multiple events at once."""
    model, _ = get_model()
    if model is None:
        return [(-1.0, False)] * len(feature_vectors)

    X = np.array(feature_vectors, dtype=np.float64)
    distances = -model.decision_function(X)

    return [(_scale_distance(float(d)), bool(d > THRESHOLD)) for d in distances]


def get_threshold() -> float:
    """Return the current anomaly threshold scaled to probability."""
    return _scale_distance(THRESHOLD)
