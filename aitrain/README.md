# 🧠 PhishGuard Colab Training Hub

This folder contains the training script (`train_colab_t4.ipynb`) to train your own Anomaly Detection model for PhishGuard on Google Colab using a T4 GPU.

## Why synthetic data?
The PhishGuard behavioral autoencoder requires a very specific 8-dimensional feature set:
1. `Hour of Day`
2. `Day of Week`
3. `Failures (Last Hour)`
4. `IP Novelty` (Binary)
5. `Device Novelty` (Binary)
6. `Geo-Distance km` (Impossible travel calculation)
7. `Time Since Last Login hrs`
8. `Typing Speed ms` (Biometric cadence)

Because real-world public datasets (like LANL Auth or CERT Insider Threat) do not typically provide biometric measurements like `Typing Speed` or exact `Geo-Distance` along with basic logon records, this notebook generates a highly realistic synthetic dataset scaled to **100,000 normal login events**. This produces a highly robust and generic behavioral baseline exactly formatted for the `LoginAutoencoder`.

## How to train
1. Go to [Google Colab](https://colab.research.google.com/).
2. Click **File > Upload Notebook** and select `train_colab_t4.ipynb` from this folder.
3. Once open, ensure your Hardware Accelerator is set to **T4 GPU** (`Runtime > Change runtime type`).
4. Click **Runtime > Run All**.
5. The notebook will automatically generate 100k events, train the LSTM Autoencoder for 30 epochs, and prompt you to download 2 files:
   - `login_autoencoder.onnx`
   - `norm_params.npz`

## How to use the trained model
Once downloaded, copy both files and paste them into the `backend/ml/` directory of the AntigelCluj project, replacing the existing ones:
```bash
# Example paths (adjust based on your download directory)
cp ~/Downloads/login_autoencoder.onnx ~/hackathoncluj/AntigelCluj/backend/ml/
cp ~/Downloads/norm_params.npz ~/hackathoncluj/AntigelCluj/backend/ml/
```

Then, set the environment variable in your `.env` file to trigger the ONNX path instead of MCD:
```env
ANOMALY_ENGINE=onnx
```

Start the backend server:
```bash
python -m backend.main
```
Your PhishGuard instance will now use your newly trained PyTorch/ONNX autoencoder for real-time anomaly detection!
