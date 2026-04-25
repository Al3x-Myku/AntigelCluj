import os
import sys
import time
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.covariance import EllipticEnvelope
from sklearn.metrics import classification_report, roc_auc_score

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train_lanl import generate_synthetic_lanl

def run_benchmark():
    print("Generating 10,000 synthetic login events...")
    df = generate_synthetic_lanl(10000)
    
    print("Feature engineering...")
    df['hour_of_day'] = (df['time'] // 3600) % 24
    df['day_of_week'] = (df['time'] // 86400) % 7
    df['failures_last_hour'] = 0.0 
    df['ip_is_new'] = (~df.duplicated(subset=['source_computer'])).astype(float)
    df['device_is_new'] = df['ip_is_new'] * 0.5
    df['geo_distance_km'] = np.random.uniform(0, 15, size=len(df))
    df.sort_values(by=['source_computer', 'time'], inplace=True)
    df['time_since_last_login_hrs'] = df.groupby('source_computer')['time'].diff().fillna(86400) / 3600
    df['time_since_last_login_hrs'] = df['time_since_last_login_hrs'].clip(upper=48.0)
    df['typing_speed_ms'] = np.random.normal(100, 20, size=len(df)).clip(min=30)
    
    features = ['hour_of_day', 'day_of_week', 'failures_last_hour', 'ip_is_new', 
                'device_is_new', 'geo_distance_km', 'time_since_last_login_hrs', 'typing_speed_ms']
    
    X = df[features].values
    
    # Generate labels: True if Fail (Anomalous)
    # Our synthetic generator injects 'Fail' heavily linked to correlated outliers (e.g. odd hours)
    y_true = (df['success'] == 'Fail').astype(int)
    
    print(f"Total anomalies: {sum(y_true)} out of {len(y_true)}")
    
    # 1. Isolation Forest
    print("\n--- Training Isolation Forest ---")
    start = time.time()
    iso = IsolationForest(contamination=0.05, random_state=42)
    iso.fit(X)
    iso_preds = iso.predict(X)
    iso_time = time.time() - start
    # Convert predictions (-1 anomaly, 1 normal) to (1 anomaly, 0 normal)
    iso_preds = [1 if p == -1 else 0 for p in iso_preds]
    iso_auc = roc_auc_score(y_true, [-s for s in iso.score_samples(X)])
    
    print(f"Time: {iso_time:.3f}s")
    print(f"AUC: {iso_auc:.4f}")
    
    # 2. Elliptic Envelope (Mahalanobis)
    print("\n--- Training Elliptic Envelope (Mahalanobis) ---")
    start = time.time()
    # Add noise to prevent singular matrix on synthetic zeros (failures_last_hour)
    noise = np.random.normal(0, 1e-5, X.shape)
    mcd = EllipticEnvelope(contamination=0.05, random_state=42, support_fraction=1.0)
    mcd.fit(X + noise)
    mcd_preds = mcd.predict(X)
    mcd_time = time.time() - start
    mcd_preds = [1 if p == -1 else 0 for p in mcd_preds]
    mcd_auc = roc_auc_score(y_true, mcd.mahalanobis(X))
    
    print(f"Time: {mcd_time:.3f}s")
    print(f"AUC: {mcd_auc:.4f}")
    
    print("\n--- CONCLUSION ---")
    if mcd_auc > iso_auc:
        print("✅ Mahalanobis Covariance outperforms Isolation Forest on this dataset!")
        print("Reason: Isolation Forest creates axis-parallel splits, missing oblique/diagonal linear covariances between features (like time of day relative to device metrics). Mahalanobis Distance captures precise multi-dimensional correlation gradients natively.")
    else:
        print("❌ Isolation Forest outperformed Mahalanobis.")

if __name__ == "__main__":
    run_benchmark()
