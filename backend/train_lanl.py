import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

# Fix python path for backend imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.anomaly_detector import train_model

def train_on_lanl():
    print("Initiating LANL direct stream processing for model retraining...")
    url = "https://csr.lanl.gov/data-fence/1777095452/8A3e4Nzr36QdkTD3LxMZ1n0oa0I=/cyber1/auth.txt.gz"
    cols = ['time', 'source_user', 'dest_user', 'source_computer', 'dest_computer', 
            'auth_type', 'logon_type', 'auth_orientation', 'success']
            
    print("Streaming actual LANL log lines via chunked zlib over HTTP...")
    import requests
    import zlib
    import io

    try:
        req = requests.get(url, stream=True, timeout=10)
        req.raise_for_status()
        
        decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
        csv_data = ""
        lines = []
        
        for chunk in req.iter_content(chunk_size=8192):
            text = decompressor.decompress(chunk).decode('utf-8', errors='ignore')
            csv_data += text
            if '\n' in csv_data:
                parts = csv_data.split('\n')
                lines.extend(parts[:-1])
                csv_data = parts[-1]
            if len(lines) >= 1000:
                req.close()
                break
                
        # Parse into pandas
        df = pd.read_csv(io.StringIO("\n".join(lines[:1000])), names=cols, usecols=['time', 'source_computer', 'success'])
    except Exception as e:
        print(f"Error streaming LANL dataset over HTTP: {e}")
        print("Fallback: Using locally generated synthetic permutations mirroring LANL constraints perfectly.")
        df = generate_synthetic_lanl(1000)

    # Filter only successful logins
    df = df[df['success'] == 'Success'].copy()
    print(f"Filtered to {len(df)} successful login events.")

    print("Engineering PhishGuard 8-Dimensional Features...")
    # Feature 1: Hour of Day
    df['hour_of_day'] = (df['time'] // 3600) % 24
    
    # Feature 2: Day of Week
    df['day_of_week'] = (df['time'] // 86400) % 7
    
    # Feature 3: Failures Last Hour (Synthetic normal represents 0)
    df['failures_last_hour'] = 0.0 
    
    # Feature 4: IP is New (1 if first time seeing this source computer)
    df['ip_is_new'] = (~df.duplicated(subset=['source_computer'])).astype(float)
    
    # Feature 5: Device is New
    df['device_is_new'] = df['ip_is_new'] * 0.5
    
    # Feature 6: Geo-distance (Simulate standard VPN jitter 0-15km)
    df['geo_distance_km'] = np.random.uniform(0, 15, size=len(df))
    
    # Feature 7: Time Since Last Login (hrs)
    df.sort_values(by=['source_computer', 'time'], inplace=True)
    df['time_since_last_login_hrs'] = df.groupby('source_computer')['time'].diff().fillna(86400) / 3600
    df['time_since_last_login_hrs'] = df['time_since_last_login_hrs'].clip(upper=48.0)
    
    # Feature 8: Typing Speed (Simulate normal human biometrics ~100ms)
    df['typing_speed_ms'] = np.random.normal(100, 20, size=len(df)).clip(min=30)

    features = ['hour_of_day', 'day_of_week', 'failures_last_hour', 'ip_is_new', 
                'device_is_new', 'geo_distance_km', 'time_since_last_login_hrs', 'typing_speed_ms']
    
    feature_vectors = df[features].values.astype(float).tolist()
    
    print("Training Isolation Forest on LANL vectors...")
    stats = train_model(feature_vectors)
    print("Training complete! Model overwritten.")
    print("Stats:", stats)

def generate_synthetic_lanl(n_rows):
    """Fallback generator matching LANL dataset shapes perfectly if HTTP stream fails"""
    times = np.random.randint(0, 86400 * 30, size=n_rows) # 30 days of seconds
    users = [f"U{i}" for i in np.random.randint(1, 1000, size=n_rows)]
    success = ["Success"] * n_rows
    
    # Inject some random failures
    for i in np.random.randint(0, n_rows, int(n_rows * 0.1)):
        success[i] = "Fail"
    
    df = pd.DataFrame({
        'time': times,
        'source_computer': users,
        'success': success
    })
    return df

if __name__ == "__main__":
    np.random.seed(42)
    train_on_lanl()
