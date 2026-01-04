# Luồng Chạy Code Dự Án NYC Taxi Demand Prediction

## Tổng Quan Dự Án

Dự án dự đoán nhu cầu taxi tại New York City sử dụng:
- **Apache Spark** (PySpark) cho xử lý dữ liệu phân tán
- **MinIO** cho lưu trữ dữ liệu (tương tự S3)
- **XGBoost** cho mô hình machine learning
- **FastAPI** cho API service
- **Redis** cho caching

---

## Luồng Chạy Code Chi Tiết

### Bước 1: Chuẩn Bị Môi Trường

#### 1.1. Cài đặt Dependencies
```bash
pip install -r requirements.txt
```

#### 1.2. Cấu hình Environment Variables
Tạo file `.env` từ `.env.example` và cấu hình:
```bash
SPARK_MASTER_IP=localhost  # hoặc IP máy chạy Spark Master (ví dụ: 192.168.1.100)
SPARK_MASTER_PORT=7077
MINIO_PORT=9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=password123
REDIS_HOST=localhost
REDIS_PORT=6379
```

**Lưu ý cho setup Master-Worker:**
- Nếu bạn có setup **mac-master** và **mac-worker**:
  - `SPARK_MASTER_IP` phải là IP của máy **mac-master**
  - Đảm bảo máy **mac-worker** có thể kết nối đến IP này
  - Đảm bảo firewall không chặn port 7077 (Spark Master) và port 9000 (MinIO)

#### 1.3. Kiểm Tra Cấu Hình
Trước khi chạy, kiểm tra cấu hình Spark và môi trường:
```bash
python scripts/check_spark_setup.py
```

Script này sẽ kiểm tra:
- Java installation và JAVA_HOME
- Spark installation và SPARK_HOME
- File .env và các biến môi trường
- Kết nối mạng đến Spark Master
- Kết nối mạng đến MinIO
- IP của máy hiện tại

#### 1.4. Khởi động Services

**Trên máy Master (mac-master):**

1. **Khởi động Spark Master:**
   ```bash
   $SPARK_HOME/sbin/start-master.sh
   ```
   Spark Master UI sẽ có tại: `http://<SPARK_MASTER_IP>:8080`

2. **Khởi động MinIO và Redis bằng Docker Compose (Khuyến nghị):**
   ```bash
   # Khởi động cả MinIO và Redis
   docker-compose up -d
   
   # Xem logs
   docker-compose logs -f
   
   # Dừng services
   docker-compose down
   
   # Dừng và xóa volumes (xóa dữ liệu)
   docker-compose down -v
   ```
   
   **Hoặc khởi động từng service riêng:**
   ```bash
   # Chỉ khởi động MinIO
   docker-compose up -d minio
   
   # Chỉ khởi động Redis
   docker-compose up -d redis
   ```
   
   **Thông tin truy cập:**
   - MinIO API: `http://<SPARK_MASTER_IP>:9000`
   - MinIO Console: `http://<SPARK_MASTER_IP>:9001`
     - Username: `admin`
     - Password: `password123`
   - Redis: `redis://<SPARK_MASTER_IP>:6379`

3. **Tạo bucket trên MinIO:**
   - Truy cập MinIO Console tại `http://<SPARK_MASTER_IP>:9001`
   - Đăng nhập với username: `admin`, password: `password123`
   - Tạo bucket tên: `nyc-taxi-driver`
   - Upload dữ liệu raw vào:
     - `raw/2025/*.parquet`
     - `raw_win/2024/*.parquet`

**Trên máy Worker (mac-worker):**

1. **Khởi động Spark Worker:**
   ```bash
   $SPARK_HOME/sbin/start-worker.sh spark://<SPARK_MASTER_IP>:7077
   ```
   Worker sẽ tự động kết nối đến Master

2. **Kiểm tra Worker đã kết nối:**
   - Truy cập Spark Master UI: `http://<SPARK_MASTER_IP>:8080`
   - Xem trong tab "Workers" có worker nào đã kết nối chưa

**Lưu ý về Docker Compose:**
- File `docker-compose.yml` đã được cấu hình sẵn với MinIO và Redis
- Dữ liệu được lưu trong Docker volumes (persistent)
- Nếu muốn thay đổi cấu hình, tạo file `docker-compose.override.yml` (không commit lên git)

---

### Bước 2: Xử Lý Dữ Liệu (ETL Pipeline)

**File chạy:** `scripts/data_processing.py`

**Mục đích:** Đọc dữ liệu raw từ MinIO, làm sạch, feature engineering, và tổng hợp nhu cầu taxi.

**Luồng xử lý:**

1. **Khởi tạo Spark Session**
   - Kết nối đến Spark Master
   - Cấu hình kết nối MinIO (S3A)

2. **Đọc Dữ Liệu Raw từ MinIO**
   - Đọc từ 2 folder:
     - `s3a://nyc-taxi-driver/raw/2025/*.parquet` (dữ liệu 2025 từ Mac)
     - `s3a://nyc-taxi-driver/raw_win/2024/*.parquet` (dữ liệu 2024 từ Windows)
   - Merge schema tự động nếu có khác biệt

3. **Làm Sạch Dữ Liệu (Clean)**
   - Lọc bỏ records có `lpep_pickup_datetime` null
   - Lọc bỏ `trip_distance <= 0`
   - Lọc bỏ `PULocationID` null

4. **Feature Engineering**
   - Trích xuất `pickup_hour` (0-23)
   - Trích xuất `pickup_day` (1=Sunday, 7=Saturday)
   - Trích xuất `pickup_month` (1-12)
   - Tạo `date_str` (date format)

5. **Tổng Hợp Nhu Cầu (Aggregation)**
   - Group by: `date_str`, `pickup_hour`, `PULocationID`
   - Tính `trip_count` (số lượng chuyến) và `avg_distance` (tổng khoảng cách)

6. **Lưu Kết Quả**
   - Lưu xuống MinIO: `s3a://nyc-taxi-driver/processed/taxi_demand_features`
   - Format: Parquet (nén)
   - Coalesce về 1 file để dễ đọc bằng Pandas

**Chạy script:**
```bash
python scripts/data_processing.py
```

**Output:** Dữ liệu đã xử lý tại `s3://nyc-taxi-driver/processed/taxi_demand_features`

---

### Bước 3: Phân Tích Khám Phá Dữ Liệu (EDA)

**File chạy:** `notebooks/exploratory_data_analysis.ipynb`

**Mục đích:** Phân tích và trực quan hóa dữ liệu để hiểu patterns.

**Các bước trong notebook:**

1. **Đọc dữ liệu đã xử lý từ MinIO**
   ```python
   df = pd.read_parquet("s3://nyc-taxi-driver/processed/taxi_demand_features")
   ```

2. **Biểu đồ đường: Nhu cầu theo giờ**
   - Tổng hợp `trip_count` theo `pickup_hour`
   - Vẽ line chart bằng Plotly

3. **Bản đồ nhiệt (Heatmap)**
   - Tải GeoJSON của NYC Taxi Zones
   - Tổng hợp nhu cầu theo `PULocationID`
   - Vẽ Choropleth map bằng Folium

**Chạy notebook:**
```bash
jupyter notebook notebooks/exploratory_data_analysis.ipynb
```

---

### Bước 4: Train Model

**File chạy:** `scripts/train_model.py`

**Mục đích:** Huấn luyện mô hình XGBoost để dự đoán nhu cầu taxi.

**Luồng xử lý:**

1. **Load Dữ Liệu từ MinIO**
   - Đọc file Parquet đã xử lý từ `s3://nyc-taxi-driver/processed/taxi_demand_features`
   - Sử dụng `storage_options` để kết nối MinIO

2. **Chuẩn Bị Features & Target**
   - Features: `pickup_hour`, `PULocationID`
   - Target: `trip_count`

3. **Train/Test Split**
   - 80% train, 20% test
   - Random state = 42

4. **Train XGBoost Model**
   - Model: `XGBRegressor`
   - Objective: `reg:squarederror`
   - N_estimators: 100

5. **Đánh Giá Model**
   - Tính RMSE trên test set

6. **Lưu Model**
   - Lưu model tại local: `nyc_taxi_xgboost.pkl`
   - Format: Pickle

**Chạy script:**
```bash
python scripts/train_model.py
```

**Output:** Model file `nyc_taxi_xgboost.pkl` tại thư mục root

---

### Bước 5: Chạy API Service

**File chạy:** `src/api/main.py`

**Mục đích:** Cung cấp API để dự đoán nhu cầu taxi real-time với caching.

**Luồng hoạt động:**

1. **Khởi Động API**
   - Load model từ `nyc_taxi_xgboost.pkl`
   - Kết nối Redis để caching

2. **API Endpoints:**

   **GET `/`**
   - Trả về message: "Taxi Demand Service is Running"

   **POST `/predict`**
   - **Input:**
     - `hour`: Giờ trong ngày (0-23)
     - `location_id`: ID khu vực (PULocationID)
   - **Xử lý:**
     1. Kiểm tra cache Redis với key: `demand:{location_id}:{hour}`
     2. Nếu có cache → trả về kết quả từ cache
     3. Nếu không có cache:
        - Chạy model prediction
        - Lưu vào Redis (TTL: 600 giây = 10 phút)
        - Trả về kết quả
   - **Output:**
     ```json
     {
       "source": "cache_redis" hoặc "model_inference",
       "location_id": 42,
       "hour": 18,
       "predicted_demand": 123.45
     }
     ```

**Chạy API:**
```bash
uvicorn src.api.main:app --reload
```

**API sẽ chạy tại:** `http://127.0.0.1:8000`

**Test API:**
```bash
# Sử dụng curl
curl -X POST "http://127.0.0.1:8000/predict?hour=18&location_id=42"

# Hoặc dùng browser/Postman
http://127.0.0.1:8000/predict?hour=18&location_id=42
```

---

## Sơ Đồ Luồng Tổng Quan

```
┌─────────────────────────────────────────────────────────────┐
│                   1. CHUẨN BỊ MÔI TRƯỜNG                    │
│  - Cài đặt dependencies                                      │
│  - Cấu hình .env                                             │
│  - Khởi động Spark, MinIO, Redis                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│           2. DATA PROCESSING (scripts/data_processing.py)   │
│  Raw Data (MinIO) → Clean → Feature Engineering →          │
│  Aggregate Demand → Processed Data (MinIO)                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│    3. EXPLORATORY DATA ANALYSIS (notebooks/eda.ipynb)      │
│  Đọc Processed Data → Phân tích → Visualization            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│         4. TRAIN MODEL (scripts/train_model.py)             │
│  Load Processed Data → Train XGBoost → Save Model          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│           5. API SERVICE (src/api/main.py)                  │
│  Load Model → API Endpoints → Redis Cache → Predictions   │
└─────────────────────────────────────────────────────────────┘
```

---

## Thứ Tự Chạy Code

### Lần Đầu Tiên (Full Pipeline):
```bash
# 0. Khởi động services (MinIO và Redis)
docker-compose up -d

# 1. Xử lý dữ liệu
python scripts/data_processing.py

# 2. (Tùy chọn) Phân tích dữ liệu
jupyter notebook notebooks/exploratory_data_analysis.ipynb

# 3. Train model
python scripts/train_model.py

# 4. Chạy API
uvicorn src.api.main:app --reload
```

### Các Lần Sau:
- Nếu chỉ cần retrain model: Chạy bước 3 và 4
- Nếu có dữ liệu mới: Chạy lại từ bước 1
- Nếu chỉ test API: Chỉ cần bước 4 (đảm bảo đã có model file)

---

## Lưu Ý Quan Trọng

1. **Dữ liệu Raw phải được upload lên MinIO trước:**
   - Folder `raw/2025/` chứa file parquet 2025
   - Folder `raw_win/2024/` chứa file parquet 2024

2. **Model file phải tồn tại trước khi chạy API:**
   - File `nyc_taxi_xgboost.pkl` phải có trong thư mục root

3. **Các service phải chạy:**
   - Spark Master & Workers
   - MinIO
   - Redis (cho API caching)

4. **File .env:**
   - Mỗi người cần tạo file `.env` riêng với IP address phù hợp
   - Không commit file `.env` lên git

5. **Setup Master-Worker:**
   - Đảm bảo máy master và worker có thể giao tiếp qua mạng
   - Kiểm tra firewall không chặn các port: 7077 (Spark), 9000 (MinIO), 8080 (Spark UI)
   - Nếu gặp lỗi `TypeError: 'JavaPackage' object is not callable`:
     - Kiểm tra JAVA_HOME và SPARK_HOME đã được set đúng chưa
     - Chạy `python scripts/check_spark_setup.py` để kiểm tra
     - Đảm bảo Java version tương thích (Java 8 hoặc 11)
     - Thử chạy với local mode trước: thay `spark://...` bằng `local[*]` để test

6. **Troubleshooting:**
   - Nếu không kết nối được đến Spark Master: kiểm tra IP và port trong .env
   - Nếu không đọc được từ MinIO: kiểm tra credentials và endpoint URL
   - Nếu worker không kết nối: kiểm tra network và firewall rules

---

## Cấu Trúc Dữ Liệu

### Input (Raw Data):
- Parquet files từ NYC Taxi dataset
- Columns: `lpep_pickup_datetime`, `trip_distance`, `PULocationID`, etc.

### Processed Data:
- Columns: `date_str`, `pickup_hour`, `pickup_day`, `pickup_month`, `PULocationID`, `trip_count`, `avg_distance`

### Model Input:
- Features: `pickup_hour`, `PULocationID`
- Target: `trip_count`

