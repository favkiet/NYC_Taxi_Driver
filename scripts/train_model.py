import sys
import os
from pathlib import Path
from dotenv import load_dotenv

sys.path.append(os.getcwd())

# Load biến môi trường từ file .env
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from src.modeling.main import TaxiDemandPredictor

def main():
    # Cấu hình kết nối MinIO từ file .env
    MAC_IP = os.getenv("SPARK_MASTER_IP")
    MINIO_PORT = os.getenv("MINIO_PORT")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
    
    minio_options = {
        "key": MINIO_ACCESS_KEY,
        "secret": MINIO_SECRET_KEY,
        "client_kwargs": {"endpoint_url": f"http://{MAC_IP}:{MINIO_PORT}"}
    }
    
    # Đường dẫn files đã xử lý
    batch_path = "s3://nyc-taxi-driver/processed/taxi_demand_features"
    streaming_path = "s3://nyc-taxi-driver/streaming/demand_aggregated"

    predictor = TaxiDemandPredictor()
    
    # 1. Load Data từ cả batch và streaming
    
    print("🔄 Đọc từ cả batch và streaming data...")
    df = predictor.load_data_multiple_sources(batch_path, streaming_path, minio_options)
    
    # 2. Train
    predictor.train(df)
    
    # 3. Save Model (Lưu tại local để API load cho nhanh)
    model_dir = Path(__file__).parent.parent / "model"
    model_dir.mkdir(exist_ok=True)
    model_path = model_dir / "nyc_taxi_xgboost.pkl"
    
    predictor.save_model(str(model_path))
    print(f"✓ Model đã được lưu tại: {model_path}")

if __name__ == "__main__":
    main()