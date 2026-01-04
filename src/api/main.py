from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import redis
import pickle
import pandas as pd
import os
from pathlib import Path
from dotenv import load_dotenv

# Load biến môi trường
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

app = FastAPI(title="NYC Taxi Demand Prediction API")

# Kết nối Redis từ .env
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    r.ping()  # Test connection
    print(f"✓ Đã kết nối Redis tại {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    print(f"⚠ Cảnh báo: Không thể kết nối Redis: {e}")
    r = None

# Load Model lúc khởi động app
MODEL_PATH = Path(__file__).parent.parent.parent / "model" / "nyc_taxi_xgboost.pkl"
model = None

try:
    if MODEL_PATH.exists():
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
        print(f"✓ Đã load model từ: {MODEL_PATH}")
    else:
        print(f"⚠ Cảnh báo: Model không tồn tại tại {MODEL_PATH}")
        print("  Vui lòng chạy: python scripts/train_model.py")
except Exception as e:
    print(f"⚠ Lỗi khi load model: {e}")

@app.get("/")
def home():
    return {
        "message": "NYC Taxi Demand Prediction API",
        "status": "running",
        "model_loaded": model is not None,
        "redis_connected": r is not None if r else False
    }

@app.get("/predict")
def predict_demand(zone: int, hour: int, month: int = None, day_of_week: int = None):
    """
    Dự đoán nhu cầu taxi dựa vào Zone, Hour, Month, Day of Week
    
    Parameters:
    - zone: The taxi zone ID (PULocationID)
    - hour: The hour of the day (0-23)
    - month: The month of the year (1-12) - optional
    - day_of_week: The day of the week (0=Monday, 6=Sunday) - optional
    """
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model chưa được load. Vui lòng train model trước: python scripts/train_model.py"
        )
    
    # 1. Kiểm tra Cache (Redis)
    cache_key = f"demand:{zone}:{hour}:{month or 'any'}:{day_of_week or 'any'}"
    cached_val = None
    
    if r:
        try:
            cached_val = r.get(cache_key)
        except Exception as e:
            print(f"⚠ Lỗi khi đọc từ Redis: {e}")
    
    if cached_val:
        return {
            "source": "cache_redis",
            "zone": zone,
            "hour": hour,
            "month": month,
            "day_of_week": day_of_week,
            "predicted_demand": float(cached_val)
        }

    # 2. Nếu không có cache, chạy Model
    # Model hiện tại chỉ dùng pickup_hour và PULocationID
    input_df = pd.DataFrame([[hour, zone]], columns=['pickup_hour', 'PULocationID'])
    prediction = float(model.predict(input_df)[0])

    # 3. Lưu vào Cache (Hết hạn sau 10 phút)
    if r:
        try:
            r.set(cache_key, prediction, ex=600)
        except Exception as e:
            print(f"⚠ Lỗi khi ghi vào Redis: {e}")

    return {
        "source": "model_inference",
        "zone": zone,
        "hour": hour,
        "month": month,
        "day_of_week": day_of_week,
        "predicted_demand": round(prediction, 2)
    }