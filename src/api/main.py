from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import redis
import pickle
import pandas as pd
import os
from pathlib import Path
from dotenv import load_dotenv
import requests

# Load biến môi trường
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

app = FastAPI(
    title="NYC Taxi Demand Prediction API",
    description="""
    API để dự đoán nhu cầu taxi tại New York City dựa trên:
    - **Zone (PULocationID)**: Khu vực đón khách
    - **Hour**: Giờ trong ngày (0-23)
    - **Date**: Ngày dự đoán (YYYY-MM-DD)
    
    ## Hướng dẫn sử dụng:
    
    1. **Tìm Zone ID**: Sử dụng endpoint `/zones` để tìm zone name và zone ID tương ứng
    2. **Dự đoán**: Sử dụng endpoint `/predict` với zone ID, hour và date
    
    ## Ví dụ:
    - Tìm zones ở Manhattan: `GET /zones?borough=Manhattan`
    - Tìm zone theo tên: `GET /zones?search=Central`
    - Dự đoán nhu cầu: `GET /predict?zone=42&hour=18&date=2025-01-15`
    """,
    version="1.0.0"
)

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

# Load Taxi Zone Lookup Table
TAXI_ZONE_LOOKUP_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
zone_lookup = {}  # Dictionary: LocationID -> {Zone, Borough, service_zone}

def load_zone_lookup():
    """Tải và load taxi zone lookup table từ URL"""
    global zone_lookup
    try:
        print(f"📥 Đang tải taxi zone lookup từ: {TAXI_ZONE_LOOKUP_URL}")
        response = requests.get(TAXI_ZONE_LOOKUP_URL, timeout=10)
        response.raise_for_status()
        
        # Đọc CSV từ response
        from io import StringIO
        df = pd.read_csv(StringIO(response.text))
        
        # Tạo dictionary lookup
        for _, row in df.iterrows():
            location_id = int(row['LocationID'])
            # Xử lý NaN values - convert thành string hoặc "Unknown"
            zone_name = str(row['Zone']) if pd.notna(row['Zone']) else 'Unknown'
            borough = str(row['Borough']) if pd.notna(row['Borough']) else 'Unknown'
            service_zone = str(row['service_zone']) if pd.notna(row['service_zone']) else 'Unknown'
            
            zone_lookup[location_id] = {
                'zone_name': zone_name,
                'borough': borough,
                'service_zone': service_zone
            }
        
        print(f"✓ Đã load {len(zone_lookup)} zones vào lookup table")
        return zone_lookup
    except Exception as e:
        print(f"⚠ Cảnh báo: Không thể tải zone lookup table: {e}")
        print("  API vẫn hoạt động nhưng không có thông tin zone name")
        return {}

# Load zone lookup khi khởi động
load_zone_lookup()

# Pydantic Models cho Response Documentation
class ZoneInfo(BaseModel):
    """Thông tin về một taxi zone"""
    location_id: int = Field(..., description="ID của zone (PULocationID)", example=42)
    zone_name: str = Field(..., description="Tên của zone", example="Central Harlem North")
    borough: str = Field(..., description="Quận/Borough", example="Manhattan")
    service_zone: str = Field(..., description="Loại service zone", example="Boro Zone")

class ZonesResponse(BaseModel):
    """Response khi list zones"""
    total: int = Field(..., description="Tổng số zones tìm được")
    zones: List[ZoneInfo] = Field(..., description="Danh sách zones")

class PredictionResponse(BaseModel):
    """Response khi dự đoán nhu cầu taxi"""
    source: str = Field(..., description="Nguồn dữ liệu: 'cache_redis' hoặc 'model_inference'", example="model_inference")
    zone: int = Field(..., description="Zone ID (PULocationID)", example=42)
    zone_name: str = Field(..., description="Tên zone", example="Central Harlem North")
    borough: str = Field(..., description="Quận/Borough", example="Manhattan")
    service_zone: str = Field(..., description="Loại service zone", example="Boro Zone")
    hour: int = Field(..., description="Giờ trong ngày (0-23)", example=18)
    date: str = Field(..., description="Ngày (YYYY-MM-DD)", example="2025-01-15")
    day_of_week: int = Field(..., description="Thứ trong tuần (0=Monday, 6=Sunday)", example=2)
    month: int = Field(..., description="Tháng (1-12)", example=1)
    is_weekend: bool = Field(..., description="Có phải cuối tuần không", example=False)
    predicted_demand: float = Field(..., description="Số lượng chuyến taxi dự đoán", example=125.5)

# Load Model lúc khởi động app
MODEL_PATH = Path(__file__).parent.parent.parent / "model" / "nyc_taxi_xgboost.pkl"
model = None
model_feature_names = None

try:
    if MODEL_PATH.exists():
        with open(MODEL_PATH, "rb") as f:
            model_data = pickle.load(f)
            # Kiểm tra xem là dict (mới) hay model trực tiếp (cũ)
            if isinstance(model_data, dict):
                model = model_data['model']
                model_feature_names = model_data.get('feature_names', ['day_of_week', 'month', 'is_weekend', 'pickup_hour', 'PULocationID'])
            else:
                # Backward compatibility với model cũ
                model = model_data
                model_feature_names = ['pickup_hour', 'PULocationID']
        print(f"✓ Đã load model từ: {MODEL_PATH}")
        print(f"✓ Features: {model_feature_names}")
    else:
        print(f"⚠ Cảnh báo: Model không tồn tại tại {MODEL_PATH}")
        print("  Vui lòng chạy: python scripts/train_model.py")
except Exception as e:
    print(f"⚠ Lỗi khi load model: {e}")

def get_zone_info(location_id: int):
    """Lấy thông tin zone từ LocationID"""
    if location_id in zone_lookup:
        return zone_lookup[location_id]
    return {
        'zone_name': 'Unknown',
        'borough': 'Unknown',
        'service_zone': 'Unknown'
    }

@app.get("/", tags=["Status"])
def home():
    """
    Kiểm tra trạng thái API và các services
    """
    return {
        "message": "NYC Taxi Demand Prediction API",
        "status": "running",
        "model_loaded": model is not None,
        "redis_connected": r is not None if r else False,
        "zones_loaded": len(zone_lookup) > 0,
        "total_zones": len(zone_lookup)
    }

@app.get("/zones", response_model=ZonesResponse, tags=["Zones"])
def list_zones(
    borough: Optional[str] = Query(None, description="Lọc theo borough (Manhattan, Queens, Brooklyn, Bronx, Staten Island, EWR)", example="Manhattan"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên zone (case-insensitive)", example="Central")
):
    """
    Liệt kê tất cả taxi zones với khả năng lọc và tìm kiếm.
    
    **Sử dụng endpoint này để tìm Zone ID tương ứng với Zone Name.**
    
    - **Borough**: Lọc theo quận (Manhattan, Queens, Brooklyn, Bronx, Staten Island, EWR)
    - **Search**: Tìm kiếm theo tên zone (không phân biệt hoa thường)
    
    **Ví dụ:**
    - Tất cả zones: `GET /zones`
    - Zones ở Manhattan: `GET /zones?borough=Manhattan`
    - Tìm kiếm "Central": `GET /zones?search=Central`
    """
    zones_list = []
    
    for location_id, info in zone_lookup.items():
        # Lọc theo borough nếu có
        if borough:
            # Xử lý an toàn: convert thành string, xử lý NaN
            try:
                borough_value = str(info['borough']) if not pd.isna(info['borough']) else ''
            except (TypeError, AttributeError):
                borough_value = ''
            
            if not borough_value or borough_value.lower() != borough.lower():
                continue
        
        # Tìm kiếm theo tên nếu có
        if search:
            # Xử lý an toàn: convert thành string, xử lý NaN
            try:
                zone_name_value = str(info['zone_name']) if not pd.isna(info['zone_name']) else ''
            except (TypeError, AttributeError):
                zone_name_value = ''
            
            if not zone_name_value or search.lower() not in zone_name_value.lower():
                continue
        
        zones_list.append(ZoneInfo(
            location_id=location_id,
            zone_name=info['zone_name'],
            borough=info['borough'],
            service_zone=info['service_zone']
        ))
    
    # Sắp xếp theo location_id
    zones_list = sorted(zones_list, key=lambda x: x.location_id)
    
    return ZonesResponse(
        total=len(zones_list),
        zones=zones_list
    )

@app.get("/zones/{location_id}", response_model=ZoneInfo, tags=["Zones"])
def get_zone_by_id(location_id: int):
    """
    Lấy thông tin chi tiết của một zone theo LocationID.
    
    **Sử dụng endpoint này để tra cứu thông tin zone khi biết Zone ID.**
    
    **Ví dụ:**
    - `GET /zones/42` - Lấy thông tin zone có ID = 42
    """
    zone_info = get_zone_info(location_id)
    
    if zone_info['zone_name'] == 'Unknown':
        raise HTTPException(
            status_code=404,
            detail=f"Zone với LocationID {location_id} không tồn tại. Sử dụng GET /zones để xem danh sách zones hợp lệ."
        )
    
    return ZoneInfo(
        location_id=location_id,
        zone_name=zone_info['zone_name'],
        borough=zone_info['borough'],
        service_zone=zone_info['service_zone']
    )

@app.get("/predict", response_model=PredictionResponse, tags=["Prediction"])
def predict_demand(
    zone: int = Query(..., description="Zone ID (PULocationID). Sử dụng GET /zones để tìm Zone ID", example=42, ge=1),
    hour: int = Query(..., description="Giờ trong ngày (0-23)", example=18, ge=0, le=23),
    date: str = Query(..., description="Ngày dự đoán (format: YYYY-MM-DD)", example="2025-01-15")
):
    """
    Dự đoán số lượng chuyến taxi (trip_count) tại một zone, giờ và ngày cụ thể.
    
    **Cách sử dụng:**
    1. Tìm Zone ID: Sử dụng `GET /zones` để tìm zone name và zone ID tương ứng
    2. Gọi API dự đoán: `GET /predict?zone={zone_id}&hour={hour}&date={date}`
    
    **Parameters:**
    - **zone**: Zone ID (PULocationID). Ví dụ: 42 = "Central Harlem North"
    - **hour**: Giờ trong ngày từ 0-23. Ví dụ: 18 = 6 PM
    - **date**: Ngày dự đoán theo format YYYY-MM-DD. Ví dụ: "2025-01-15"
    
    **Response:**
    - `predicted_demand`: Số lượng chuyến taxi dự đoán
    - `zone_name`, `borough`, `service_zone`: Thông tin zone tự động được thêm vào
    - `day_of_week`, `month`, `is_weekend`: Features được extract từ date
    
    **Ví dụ:**
    ```
    GET /predict?zone=42&hour=18&date=2025-01-15
    ```
    
    **Lưu ý:**
    - Kết quả được cache trong Redis 10 phút
    - Nếu zone không tồn tại, zone_name sẽ là "Unknown"
    """
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model chưa được load. Vui lòng train model trước: python scripts/train_model.py"
        )
    
    # Validate và parse date
    try:
        date_obj = pd.to_datetime(date)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Date format không hợp lệ. Sử dụng format YYYY-MM-DD (ví dụ: 2025-01-15). Lỗi: {str(e)}"
        )
    
    # Validate hour
    if not (0 <= hour <= 23):
        raise HTTPException(
            status_code=400,
            detail="Hour phải trong khoảng 0-23"
        )
    
    # Extract features từ date
    day_of_week = date_obj.dayofweek  # 0=Monday, 6=Sunday
    month = date_obj.month  # 1-12
    is_weekend = 1 if day_of_week >= 5 else 0  # Saturday=5, Sunday=6
    
    # 1. Kiểm tra Cache (Redis)
    cache_key = f"demand:{zone}:{hour}:{date}"
    cached_val = None
    
    if r:
        try:
            cached_val = r.get(cache_key)
        except Exception as e:
            print(f"⚠ Lỗi khi đọc từ Redis: {e}")
    
    # Lấy thông tin zone
    zone_info = get_zone_info(zone)
    
    if cached_val:
        return PredictionResponse(
            source="cache_redis",
            zone=zone,
            zone_name=zone_info['zone_name'],
            borough=zone_info['borough'],
            service_zone=zone_info['service_zone'],
            hour=hour,
            date=date,
            day_of_week=day_of_week,
            month=month,
            is_weekend=bool(is_weekend),
            predicted_demand=float(cached_val)
        )

    # 2. Nếu không có cache, chạy Model
    # Tạo input với đúng features theo thứ tự model đã train
    if model_feature_names and 'day_of_week' in model_feature_names:
        # Model mới với date features
        # Đảm bảo đúng thứ tự features
        input_dict = {}
        for feature in model_feature_names:
            if feature == 'day_of_week':
                input_dict[feature] = day_of_week
            elif feature == 'month':
                input_dict[feature] = month
            elif feature == 'is_weekend':
                input_dict[feature] = is_weekend
            elif feature == 'pickup_hour':
                input_dict[feature] = hour
            elif feature == 'PULocationID':
                input_dict[feature] = zone
        
        input_df = pd.DataFrame([input_dict])
    else:
        # Backward compatibility với model cũ (chỉ có hour và zone)
        input_data = [[hour, zone]]
        input_df = pd.DataFrame(input_data, columns=['pickup_hour', 'PULocationID'])
    
    prediction = float(model.predict(input_df)[0])

    # 3. Lưu vào Cache (Hết hạn sau 10 phút)
    if r:
        try:
            r.set(cache_key, prediction, ex=600)
        except Exception as e:
            print(f"⚠ Lỗi khi ghi vào Redis: {e}")

    return PredictionResponse(
        source="model_inference",
        zone=zone,
        zone_name=zone_info['zone_name'],
        borough=zone_info['borough'],
        service_zone=zone_info['service_zone'],
        hour=hour,
        date=date,
        day_of_week=day_of_week,
        month=month,
        is_weekend=bool(is_weekend),
        predicted_demand=round(prediction, 2)
    )