# NYC Taxi Demand Prediction

This project aims to predict taxi demand in New York City based on historical trip data. It includes data processing, exploratory analysis, and a web API to serve predictions.

## Project Structure

```
.
├── data/
│   ├── processed/
│   └── raw/
│       └── 2025/
├── model/
│   └── nyc_taxi_xgboost.pkl
├── notebooks/
│   └── exploratory_data_analysis.ipynb
├── scripts/
│   ├── data_processing.py      # Spark ETL pipeline để xử lý dữ liệu từ MinIO
│   ├── explore_data.py         # Script khám phá dữ liệu
│   └── train_model.py          # Train XGBoost model từ dữ liệu đã xử lý
├── src/
│   ├── api/
│   │   └── main.py             # FastAPI application để serve predictions
│   ├── data_processing/
│   │   └── main.py             # TaxiDataProcessor class cho Spark ETL
│   └── modeling/
│       └── main.py             # TaxiDemandPredictor class cho model training
├── docker-compose.yml          # Docker Compose config cho MinIO và Redis
├── requirements.txt            # Python dependencies
└── README.md
```

- **`data/`**: Contains raw and processed taxi trip data (stored in MinIO).
- **`model/`**: Contains trained XGBoost model files.
- **`notebooks/`**: Jupyter notebook for exploratory data analysis.
- **`scripts/`**: Standalone scripts for different tasks like data processing and model training.
- **`src/`**: Source code for the main application, including the API and data processing modules.
- **`requirements.txt`**: A list of Python dependencies for this project.

## Getting Started

### Prerequisites

- Python 3.8+
- Docker và Docker Compose (để chạy MinIO và Redis)
- Apache Spark (để xử lý dữ liệu phân tán)
- Java 8 hoặc 11 (cho Spark)
- An environment with the dependencies installed.

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/NYC_Driver.git
    cd NYC_Driver
    ```

2.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Khởi động MinIO và Redis bằng Docker Compose:
    ```bash
    # Khởi động services
    docker compose up -d
    
    # Kiểm tra services đang chạy
    docker compose ps
    
    # Xem logs
    docker compose logs -f
    ```
    
    **Truy cập MinIO Console:**
    - URL: `http://localhost:9001`
    - Username: `admin`
    - Password: `password123`
    
    **Tạo bucket trên MinIO:**
    - Đăng nhập vào MinIO Console
    - Tạo bucket tên: `nyc-taxi-driver`
    - Upload dữ liệu raw vào folder:
      - `raw/2025/*.parquet`
    
    **Redis:**
    - Redis chạy trên port `6378` (mapped từ container port 6379)
    - Host: `localhost` (hoặc IP của máy chạy Docker)

4.  Cấu hình IP Address và các thông tin kết nối:
    ```bash
    # Copy file .env.example thành .env
    cp .env.example .env
    
    # Chỉnh sửa file .env và điền IP address của máy chạy Spark Master và MinIO
    # Ví dụ: SPARK_MASTER_IP=100.xxx.xxx.xxx hoặc localhost nếu chạy trên cùng máy
    ```
    
    **Lưu ý:** File `.env` không được commit lên git. Mỗi người cần tạo file `.env` riêng với IP address của máy mình.

5.  Tải các JAR files cần thiết cho S3A/MinIO:
    ```bash
    mkdir jars
    cd jars
    curl -O https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.540/aws-java-sdk-bundle-1.12.540.jar
    curl -O https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar
    ```
    
    **Lưu ý:** 
    - Các JAR files này cần được đặt trong thư mục `jars/` ở project root.
    - Script `data_processing.py` sẽ tự động load các JAR files này khi khởi tạo SparkSession.
    - Nếu chạy Spark trên cluster, cần copy các JAR files này vào thư mục `jars/` của Spark trên tất cả nodes (master và workers).

### Starting Spark

Sau khi cài đặt Spark và cấu hình các JAR files, bạn cần khởi động Spark Master và Worker:

1. **Khởi động Spark Master:**
   ```bash
   $SPARK_HOME/sbin/start-master.sh
   ```
   
   Sau khi khởi động, Spark Master sẽ chạy tại `http://localhost:8080` (hoặc IP của máy master). Lưu ý địa chỉ Spark Master URL (ví dụ: `spark://mac-master:7077`).

2. **Dừng Spark Master:**
   ```bash
   $SPARK_HOME/sbin/stop-master.sh
   ```

3. **Khởi động Spark Worker:**
   ```bash
   $SPARK_HOME/sbin/start-worker.sh spark://mac-master:7077
   ```
   
   **Lưu ý:** Thay `mac-master` bằng hostname hoặc IP address của máy chạy Spark Master. Port `7077` là port mặc định của Spark Master.

4. **Kiểm tra trạng thái:**
   - Truy cập Spark Master Web UI tại `http://localhost:8080` (hoặc IP của máy master)
   - Kiểm tra các workers đã kết nối thành công

### Data Processing

Script `scripts/data_processing.py` sử dụng Spark để xử lý dữ liệu Yellow Taxi từ MinIO:

1. **Đọc dữ liệu** từ `s3a://nyc-taxi-driver/raw/2025/*.parquet`
2. **Làm sạch dữ liệu**: Loại bỏ records thiếu thông tin, trip_distance <= 0
3. **Feature Engineering**: Tạo các features như `pickup_hour`, `pickup_day`, `pickup_month`, `date_str`
4. **Tổng hợp nhu cầu**: Group by `date_str`, `pickup_hour`, `PULocationID` để tính `trip_count` và `avg_distance`
5. **Lưu kết quả** vào `s3a://nyc-taxi-driver/processed/taxi_demand_features`

**Yêu cầu:**
- Spark Master và Worker đã được khởi động
- MinIO đã chạy và có bucket `nyc-taxi-driver` với dữ liệu raw
- File `.env` đã được cấu hình đúng

**Chạy script:**
```bash
python scripts/data_processing.py
```

### Exploratory Analysis

Notebook `notebooks/exploratory_data_analysis.ipynb` chứa phân tích khám phá dữ liệu taxi trip. Để chạy, bạn cần có môi trường Jupyter.

### Model Training

Script `scripts/train_model.py` train XGBoost model để dự đoán nhu cầu taxi:

1. **Đọc dữ liệu** từ cả batch (`processed/taxi_demand_features`) và streaming (`streaming/demand_aggregated`) trong MinIO
2. **Extract features** từ `date_str`: `day_of_week`, `month`, `is_weekend`
3. **Train XGBoost** với features: `day_of_week`, `month`, `is_weekend`, `pickup_hour`, `PULocationID`
4. **Target**: `trip_count` (số lượng chuyến taxi)
5. **Lưu model** tại `model/nyc_taxi_xgboost.pkl`

**Yêu cầu:**
- Đã chạy data processing script để có dữ liệu processed trong MinIO
- File `.env` đã được cấu hình đúng với MinIO credentials

**Chạy script:**
```bash
python scripts/train_model.py
```

Model được lưu tại `model/nyc_taxi_xgboost.pkl` và sẽ được API tự động load khi khởi động.

### Running the API

Dự án bao gồm một FastAPI application để serve predictions về nhu cầu taxi.

**Prerequisites:**
- Model đã được train tại `model/nyc_taxi_xgboost.pkl` (chạy `python scripts/train_model.py` trước)
- Redis đang chạy (qua Docker Compose hoặc standalone)
- File `.env` đã được cấu hình với `REDIS_HOST` và `REDIS_PORT` (mặc định: `localhost:6378`)

**Chạy API server:**
```bash
uvicorn src.api.main:app --reload
```

API sẽ có sẵn tại `http://127.0.0.1:8000`.

**API Documentation:**
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

#### API Endpoints

- **`GET /`**: Kiểm tra trạng thái API và các services (model, Redis, zones).

- **`GET /zones`**: Liệt kê tất cả taxi zones với khả năng lọc và tìm kiếm.
  - **Query Parameters:**
    - `borough` (optional): Lọc theo borough (Manhattan, Queens, Brooklyn, Bronx, Staten Island, EWR).
    - `search` (optional): Tìm kiếm theo tên zone (case-insensitive).
  - **Example:**
    ```
    GET /zones?borough=Manhattan
    GET /zones?search=Central
    ```

- **`GET /zones/{location_id}`**: Lấy thông tin chi tiết của một zone theo LocationID.
  - **Example:**
    ```
    GET /zones/42
    ```

- **`GET /predict`**: Dự đoán số lượng chuyến taxi tại một zone, giờ và ngày cụ thể.
  - **Query Parameters:**
    - `zone` (required): Zone ID (PULocationID). Sử dụng `/zones` để tìm Zone ID.
    - `hour` (required): Giờ trong ngày (0-23).
    - `date` (required): Ngày dự đoán (format: YYYY-MM-DD).
  - **Example:**
    ```
    GET /predict?zone=42&hour=18&date=2025-01-15
    ```
  - **Response:**
    ```json
    {
      "source": "model_inference",
      "zone": 42,
      "zone_name": "Central Harlem North",
      "borough": "Manhattan",
      "service_zone": "Boro Zone",
      "hour": 18,
      "date": "2025-01-15",
      "day_of_week": 2,
      "month": 1,
      "is_weekend": false,
      "predicted_demand": 125.5
    }
    ```

**Lưu ý:**
- API sử dụng Redis để cache predictions (TTL: 10 phút) để cải thiện hiệu suất.
- Model tự động extract features từ `date` (day_of_week, month, is_weekend).
- Zone information được load từ NYC Taxi Zone Lookup Table.