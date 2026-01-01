from fastapi import FastAPI
import redis
import pickle
import pandas as pd
import json

app = FastAPI(title="NYC Taxi Demand Prediction API")

# Kết nối Redis (Giả sử Redis chạy trên Docker máy Mac hoặc Win)
# docker run -d -p 6379:6379 redis
r = redis.Redis(host='localhost', port=6379, db=0)

# Load Model lúc khởi động app
with open("nyc_taxi_xgboost.pkl", "rb") as f:
    model = pickle.load(f)

@app.get("/")
def home():
    return {"message": "Taxi Demand Service is Running"}

@app.post("/predict")
def predict_demand(hour: int, location_id: int):
    """
    Dự đoán nhu cầu taxi dựa vào Giờ và ID Khu vực
    """
    # 1. Kiểm tra Cache (Redis)
    cache_key = f"demand:{location_id}:{hour}"
    cached_val = r.get(cache_key)
    
    if cached_val:
        return {
            "source": "cache_redis",
            "location_id": location_id,
            "hour": hour,
            "predicted_demand": float(cached_val)
        }

    # 2. Nếu không có cache, chạy Model
    input_df = pd.DataFrame([[hour, location_id]], columns=['pickup_hour', 'PULocationID'])
    prediction = float(model.predict(input_df)[0])

    # 3. Lưu vào Cache (Hết hạn sau 10 phút)
    r.set(cache_key, prediction, ex=600)

    return {
        "source": "model_inference",
        "location_id": location_id,
        "hour": hour,
        "predicted_demand": prediction
    }