# NYC Taxi Demand Prediction

This project aims to predict taxi demand in New York City based on historical trip data. It includes data processing, exploratory analysis, and a web API to serve predictions.

## Project Structure

```
.
├── data/
│   ├── processed/
│   └── raw/
│       └── 2025/
├── notebooks/
│   └── exploratory_data_analysis.ipynb
├── scripts/
│   ├── data_processing.py
│   ├── explore_data.py
│   └── train_model.py
├── src/
│   ├── api/
│   │   └── main.py
│   ├── data_processing/
│   │   └── main.py
│   └── modeling/
│       └── main.py
├── requirements.txt
└── README.md
```

- **`data/`**: Contains raw and processed taxi trip data.
- **`notebooks/`**: Jupyter notebook for exploratory data analysis.
- **`scripts/`**: Standalone scripts for different tasks like data processing and model training.
- **`src/`**: Source code for the main application, including the API.
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
    docker-compose up -d
    
    # Kiểm tra services đang chạy
    docker-compose ps
    
    # Xem logs
    docker-compose logs -f
    ```
    
    **Truy cập MinIO Console:**
    - URL: `http://localhost:9001`
    - Username: `admin`
    - Password: `password123`
    
    **Tạo bucket trên MinIO:**
    - Đăng nhập vào MinIO Console
    - Tạo bucket tên: `nyc-taxi-driver`
    - Upload dữ liệu raw vào các folder:
      - `raw/2025/*.parquet`
      <!-- - `raw_win/2024/*.parquet` -->

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
    curl -O https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar
    curl -O https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar
    ```
    
    **Lưu ý:** Copy các JAR files này vào thư mục `jars/` của Spark trên tất cả nodes (master và workers).

### Data Processing

The `scripts/data_processing.py` script processes the raw parquet files from `data/raw/2025/` and saves the result in `data/processed/`.

To run the script:
```bash
python scripts/data_processing.py
```

### Exploratory Analysis

The `notebooks/exploratory_data_analysis.ipynb` notebook contains an analysis of the taxi trip data. To run it, you need to have a Jupyter environment.

### Model Training

The `scripts/train_model.py` script is a placeholder for the model training logic. This part of the project is not yet implemented.

### Model Training

Train the XGBoost model using the processed data:

```bash
python scripts/train_model.py
```

The trained model will be saved to `model/nyc_taxi_xgboost.pkl`.

**Note:** Make sure you have run the data processing script first to generate the processed data in MinIO.

### Running the API

The project includes a FastAPI application to serve the demand predictions.

**Prerequisites:**
- A trained model at `model/nyc_taxi_xgboost.pkl` (run `python scripts/train_model.py` first)
- Redis running (via Docker Compose or standalone)

To run the API server:
```bash
uvicorn src.api.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

#### API Endpoints

- **`GET /`**: Returns API status and information.
- **`GET /predict`**: Predicts taxi demand.
  - **Query Parameters:**
    - `zone` (required): The taxi zone ID (PULocationID).
    - `hour` (required): The hour of the day (0-23).
    - `month` (optional): The month of the year (1-12).
    - `day_of_week` (optional): The day of the week (0=Monday, 6=Sunday).
  - **Example:**
    ```
    http://127.0.0.1:8000/predict?zone=42&hour=18&month=10&day_of_week=3
    ```
  - **Response:**
    ```json
    {
      "source": "model_inference",
      "zone": 42,
      "hour": 18,
      "month": 10,
      "day_of_week": 3,
      "predicted_demand": 125.5
    }
    ```

**Note:** The API uses Redis for caching predictions (10-minute TTL) to improve performance.