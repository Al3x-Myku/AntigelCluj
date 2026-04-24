"""Offline GPU training — LSTM autoencoder for behavioral anomaly detection.

Requires PyTorch. Trains on login feature sequences, exports to ONNX.
Run: python -m backend.ml.train_anomaly
"""

import os
import sys
import numpy as np
import logging

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.info("PyTorch not installed — GPU training unavailable")


class LoginAutoencoder(nn.Module if HAS_TORCH else object):
    """LSTM Autoencoder for login behavior sequences."""

    def __init__(self, input_dim=8, hidden_dim=32, latent_dim=16, n_layers=2):
        if not HAS_TORCH:
            return
        super().__init__()
        self.encoder = nn.LSTM(input_dim, hidden_dim, n_layers, batch_first=True)
        self.enc_fc = nn.Linear(hidden_dim, latent_dim)
        self.dec_fc = nn.Linear(latent_dim, hidden_dim)
        self.decoder = nn.LSTM(hidden_dim, input_dim, n_layers, batch_first=True)

    def forward(self, x):
        # Encode
        enc_out, _ = self.encoder(x)
        latent = self.enc_fc(enc_out[:, -1, :])
        # Decode
        dec_input = self.dec_fc(latent).unsqueeze(1).repeat(1, x.size(1), 1)
        dec_out, _ = self.decoder(dec_input)
        return dec_out


def train(data_path: str = None, epochs: int = 50, batch_size: int = 32, lr: float = 1e-3):
    """Train the autoencoder on login data."""
    if not HAS_TORCH:
        print("❌ PyTorch not installed. Install with: pip install torch")
        return

    # Load data from DB
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from backend.database import SessionLocal
    from backend.models.login_event import LoginEvent

    db = SessionLocal()
    events = db.query(LoginEvent).filter(LoginEvent.is_anomalous == False).all()
    db.close()

    if len(events) < 20:
        print(f"❌ Need at least 20 normal events, have {len(events)}")
        return

    # Build feature matrix
    X = np.array([e.feature_vector() for e in events], dtype=np.float32)

    # Normalize
    mean = X.mean(axis=0)
    std = X.std(axis=0) + 1e-8
    X_norm = (X - mean) / std

    # Reshape to sequences (batch, seq_len=1, features)
    X_tensor = torch.FloatTensor(X_norm).unsqueeze(1)

    dataset = TensorDataset(X_tensor, X_tensor)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Setup
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🖥 Training on: {device}")

    model = LoginAutoencoder().to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    # Train
    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for batch_x, batch_y in loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            optimizer.zero_grad()
            output = model(batch_x)
            loss = criterion(output, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        if (epoch + 1) % 10 == 0:
            print(f"Epoch [{epoch + 1}/{epochs}] Loss: {total_loss / len(loader):.6f}")

    # Export to ONNX
    model.eval()
    dummy = torch.randn(1, 1, 8).to(device)
    onnx_path = os.path.join(os.path.dirname(__file__), "login_autoencoder.onnx")

    torch.onnx.export(
        model, dummy, onnx_path,
        input_names=["input"], output_names=["output"],
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
    )

    # Save normalization params
    np.savez(
        os.path.join(os.path.dirname(__file__), "norm_params.npz"),
        mean=mean, std=std,
    )

    print(f"✅ Model exported to {onnx_path}")
    print(f"✅ Normalization params saved")


if __name__ == "__main__":
    train()
