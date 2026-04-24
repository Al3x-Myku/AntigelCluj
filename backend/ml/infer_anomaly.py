"""ONNX inference module — drop-in replacement for sklearn MCD path."""

import os
import logging
import numpy as np

logger = logging.getLogger(__name__)

ONNX_PATH = os.path.join(os.path.dirname(__file__), "login_autoencoder.onnx")
NORM_PATH = os.path.join(os.path.dirname(__file__), "norm_params.npz")

_session = None
_mean = None
_std = None


def load_model():
    """Load the ONNX model and normalization parameters."""
    global _session, _mean, _std

    if _session is not None:
        return True

    if not os.path.exists(ONNX_PATH):
        logger.warning(f"ONNX model not found at {ONNX_PATH}")
        return False

    try:
        import onnxruntime as ort
        _session = ort.InferenceSession(ONNX_PATH)

        if os.path.exists(NORM_PATH):
            params = np.load(NORM_PATH)
            _mean = params["mean"]
            _std = params["std"]
        else:
            _mean = np.zeros(8)
            _std = np.ones(8)

        logger.info("ONNX model loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to load ONNX model: {e}")
        return False


def score_event(feature_vector: list[float]) -> tuple[float, bool]:
    """Score a single event using the ONNX autoencoder.
    Returns (reconstruction_error, is_anomalous).
    """
    if not load_model():
        return 0.0, False

    x = np.array(feature_vector, dtype=np.float32)
    x_norm = (x - _mean) / (_std + 1e-8)
    x_input = x_norm.reshape(1, 1, -1).astype(np.float32)

    output = _session.run(None, {"input": x_input})[0]
    reconstruction_error = float(np.mean((x_input - output) ** 2))

    # Threshold: empirically set at 0.5 MSE (tune based on validation)
    threshold = 0.5
    is_anomalous = reconstruction_error > threshold

    return round(reconstruction_error, 4), is_anomalous


def score_batch(feature_vectors: list[list[float]]) -> list[tuple[float, bool]]:
    """Score multiple events."""
    return [score_event(fv) for fv in feature_vectors]
