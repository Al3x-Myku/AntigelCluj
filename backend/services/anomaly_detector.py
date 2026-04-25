"""Anomaly detector — Mahalanobis Distance via Elliptic Envelope."""

import os
import logging
import pickle
import numpy as np
from pathlib import Path
from sklearn.covariance import EllipticEnvelope

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent / "ml" / "mahalanobis_model.pkl"
N_FEATURES = 8
# Threshold for anomaly score.
THRESHOLD = 0.0

# Cached model
_model = None


def get_model():
    """Load or return cached Elliptic Envelope model."""
    global _model
    if _model is not None:
        return _model, None

    if MODEL_PATH.exists():
        with open(MODEL_PATH, "rb") as f:
            data = pickle.load(f)
            _model = data["model"]
            logger.info(f"Loaded Mahalanobis model from {MODEL_PATH}")
            return _model, None

    return None, None


def train_model(feature_vectors: list[list[float]]) -> dict:
    """
    Fit Elliptic Envelope on feature vectors (normal login history).
    Returns training stats.
    """
    global _model

    X = np.array(feature_vectors, dtype=np.float64)

    if len(X) < 10:
        raise ValueError(f"Need at least 10 samples, got {len(X)}")

    # Fit Elliptic Envelope (Mahalanobis distance based)
    # Contamination sets the expected proportion of outliers
    clf = EllipticEnvelope(random_state=42, contamination=0.05, support_fraction=1.0)
    
    # Adding a small amount of noise to avoid singular covariance matrix in perfectly correlated synthetic data
    noise = np.random.normal(0, 1e-4, X.shape)
    clf.fit(X + noise)

    _model = clf

    # Save model
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": clf}, f)

    # Compute distances using Mahalanobis
    distances = clf.mahalanobis(X)

    stats = {
        "n_samples": len(X),
        "n_features": N_FEATURES,
        "mean_mahalanobis": round(float(np.mean(distances)), 4),
        "max_mahalanobis": round(float(np.max(distances)), 4),
        "model_path": str(MODEL_PATH),
    }
    logger.info(f"Mahalanobis model trained: {stats}")
    return stats


def _scale_distance(mahalanobis_dist: float) -> float:
    """Scale Mahalanobis distance to a [0.0, 1.0] probability-like anomaly score."""
    import math
    # Typical Mahalanobis distances might be 0, 10, 20...
    # We want to squish this so that large distances -> 1.0 (highly anomalous)
    # small distances -> 0.0 (normal).
    # Softmax/Sigmoid-like scaling.
    # An empirical rule: chi-square distributions suggest distances around N_FEATURES are normal.
    # So we want distances >> N_FEATURES to approach 1.0.
    
    # Shift center roughly around N_FEATURES
    centered_dist = mahalanobis_dist - N_FEATURES
    
    # Sigmoid function to squish to [0, 1]
    # Adjusting coefficient to make the curve visually pleasing between normal and anomalous
    score = 1.0 / (1.0 + math.exp(-0.25 * centered_dist))
    return round(score, 4)


def score_event(feature_vector: list[float]) -> tuple[float, bool]:
    """
    Compute Anomaly Score for a single login event.
    Returns (score, is_anomalous).
    """
    model, _ = get_model()

    if model is None:
        logger.warning("No Mahalanobis model available — returning score -1.0")
        return -1.0, False

    X = np.array([feature_vector], dtype=np.float64)
    dist = float(model.mahalanobis(X)[0])
    
    # A point is anomalous if the model's predict says -1
    pred = model.predict(X)[0]
    is_anomalous = pred == -1

    return _scale_distance(dist), is_anomalous


def score_batch(feature_vectors: list[list[float]]) -> list[tuple[float, bool]]:
    """Score multiple events at once."""
    model, _ = get_model()
    if model is None:
        return [(-1.0, False)] * len(feature_vectors)

    X = np.array(feature_vectors, dtype=np.float64)
    distances = model.mahalanobis(X)
    preds = model.predict(X)

    return [(_scale_distance(float(d)), bool(p == -1)) for d, p in zip(distances, preds)]


def get_threshold() -> float:
    """Return an approximate threshold scaled to probability."""
    # Based on our scale function, a Mahalanobis dist equal to N_FEATURES gives 0.5. 
    # Usually contamination boundary dictates the exact threshold, but for simplicity:
    return 0.8
