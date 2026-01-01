import sys
import os
sys.path.append(os.getcwd())
from src.modeling.main import TaxiDemandPredictor

def main():
    # Cấu hình kết nối MinIO cho Pandas (dùng thư viện s3fs/pyarrow ngầm)
    minio_options = {
        "key": "admin",
        "secret": "password123",
        "client_kwargs": {"endpoint_url": "http://100.122.52.41:9000"}
    }
    
    # Đường dẫn file đã xử lý bởi Spark
    data_path = "s3://nyc-taxi-driver/processed/taxi_demand_features" 

    predictor = TaxiDemandPredictor()
    
    # 1. Load Data
    print("Đang tải dữ liệu từ MinIO...")
    df = predictor.load_data(data_path, minio_options)
    
    # 2. Train
    predictor.train(df)
    
    # 3. Save Model (Lưu tại local để API load cho nhanh)
    predictor.save_model("nyc_taxi_xgboost.pkl")

if __name__ == "__main__":
    main()