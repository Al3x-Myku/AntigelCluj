"""Anomaly detector — Mahalanobis distance via MinCovDet (sklearn MCD)."""

import os
import logging
import pickle
import numpy as np
from pathlib import Path
from scipy.stats import chi2
from sklearn.covariance import MinCovDet

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent / "ml" / "mcd_model.pkl"
N_FEATURES = 8
# Threshold: chi2 percentile at 97.5% with 8 degrees of freedom
THRESHOLD = chi2.ppf(0.975, df=N_FEATURES)

# Cached model
_model = None
_model_mean = None


def get_model():
    """Load or return cached MCD model."""
    global _model, _model_mean
    if _model is not None:
        return _model, _model_mean

    if MODEL_PATH.exists():
        with open(MODEL_PATH, "rb") as f:
            data = pickle.load(f)
            _model = data["model"]
            _model_mean = data["mean"]
            logger.info(f"Loaded MCD model from {MODEL_PATH}")
            return _model, _model_mean

    return None, None


def train_model(feature_vectors: list[list[float]]) -> dict:
    """
    Fit MinCovDet on feature vectors (normal login history).
    Returns training stats.
    """
    global _model, _model_mean

    X = np.array(feature_vectors, dtype=np.float64)

    if len(X) < N_FEATURES + 1:
        raise ValueError(f"Need at least {N_FEATURES + 1} samples, got {len(X)}")

    # Fit MCD
    mcd = MinCovDet(random_state=42)
    mcd.fit(X)

    _model = mcd
    _model_mean = mcd.location_

    # Save model
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": mcd, "mean": _model_mean}, f)

    # Compute distances on training data
    distances = mcd.mahalanobis(X)

    stats = {
        "n_samples": len(X),
        "n_features": N_FEATURES,
        "threshold": round(THRESHOLD, 4),
        "mean_distance": round(float(np.mean(distances)), 4),
        "max_distance": round(float(np.max(distances)), 4),
        "anomalies_in_training": int(np.sum(distances > THRESHOLD)),
        "model_path": str(MODEL_PATH),
    }
    logger.info(f"MCD model trained: {stats}")
    return stats


def score_event(feature_vector: list[float]) -> tuple[float, bool]:
    """
    Compute Mahalanobis distance for a single login event.
    Returns (distance, is_anomalous).
    """
    model, mean = get_model()

    if model is None:
        # No model trained yet — return neutral score
        logger.warning("No MCD model available — returning score 0.0")
        return 0.0, False

    X = np.array([feature_vector], dtype=np.float64)
    distance = float(model.mahalanobis(X)[0])
    is_anomalous = distance > THRESHOLD

    return round(distance, 4), is_anomalous


def score_batch(feature_vectors: list[list[float]]) -> list[tuple[float, bool]]:
    """Score multiple events at once."""
    model, mean = get_model()
    if model is None:
        return [(0.0, False)] * len(feature_vectors)

    X = np.array(feature_vectors, dtype=np.float64)
    distances = model.mahalanobis(X)

    return [(round(float(d), 4), bool(d > THRESHOLD)) for d in distances]


def get_threshold() -> float:
    """Return the current anomaly threshold."""
    return round(THRESHOLD, 4)
