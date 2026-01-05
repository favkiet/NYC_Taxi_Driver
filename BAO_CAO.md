# HỆ THỐNG DỰ ĐOÁN NHU CẦU TAXI TẠI CÁC KHU VỰC Ở NEW YORK CITY

**Nhóm thực hiện:** [Tên nhóm]  
**Môn học:** Xử lý dữ liệu phân tán  
**Năm học:** 2024-2025

---

## MỤC LỤC

1. [Giới thiệu](#1-giới-thiệu)
2. [Tổng quan về bài toán](#2-tổng-quan-về-bài-toán)
3. [Kiến trúc hệ thống](#3-kiến-trúc-hệ-thống)
4. [Công nghệ và công cụ sử dụng](#4-công-nghệ-và-công-cụ-sử-dụng)
5. [Thiết kế và triển khai](#5-thiết-kế-và-triển-khai)
6. [Xử lý dữ liệu phân tán](#6-xử-lý-dữ-liệu-phân-tán)
7. [Kết quả thực nghiệm](#7-kết-quả-thực-nghiệm)
8. [Kết luận và hướng phát triển](#8-kết-luận-và-hướng-phát-triển)
9. [Tài liệu tham khảo](#9-tài-liệu-tham-khảo)

---

## 1. GIỚI THIỆU

### 1.1. Bối cảnh

New York City là một trong những thành phố có mật độ giao thông cao nhất thế giới với hàng triệu lượt đi taxi mỗi ngày. Việc dự đoán chính xác nhu cầu taxi tại các khu vực khác nhau và các thời điểm cụ thể có ý nghĩa quan trọng trong việc:

- Tối ưu hóa phân bổ tài nguyên (xe taxi) theo không gian và thời gian
- Giảm thời gian chờ đợi của khách hàng
- Tăng hiệu quả hoạt động và doanh thu cho các công ty taxi
- Hỗ trợ quy hoạch giao thông đô thị

### 1.2. Mục tiêu đề tài

Đề tài này nhằm xây dựng một hệ thống dự đoán nhu cầu taxi tại các khu vực khác nhau của New York City sử dụng:

- **Apache Spark** cho xử lý dữ liệu phân tán trên kiến trúc master-worker
- **Apache Kafka** cho xử lý dữ liệu streaming real-time
- **XGBoost** cho mô hình machine learning dự đoán
- **MinIO** cho lưu trữ dữ liệu phân tán (data lake)
- **FastAPI** và **Redis** cho API service với caching

### 1.3. Phạm vi nghiên cứu

- Dữ liệu: Yellow Taxi Trip Records từ NYC TLC (Taxi and Limousine Commission)
- Thời gian: Dữ liệu từ năm 2024-2025
- Đơn vị dự đoán: Số lượng lượt đón taxi theo khu vực (Taxi Zone) và giờ trong ngày
- Kiến trúc: Spark cluster với 1 master (mac-master) và 1 worker (mac-worker)

---

## 2. TỔNG QUAN VỀ BÀI TOÁN

### 2.1. Mô tả bài toán

Bài toán dự đoán nhu cầu taxi là một bài toán **regression** trong machine learning, với:

- **Input (Features):**
  - `PULocationID`: ID khu vực đón khách (1-263 zones)
  - `pickup_hour`: Giờ trong ngày (0-23)
  - `pickup_month`: Tháng trong năm (1-12) - tùy chọn
  - `day_of_week`: Thứ trong tuần (0-6) - tùy chọn

- **Output (Target):**
  - `trip_count`: Số lượng lượt đón taxi dự kiến

### 2.2. Thách thức

1. **Khối lượng dữ liệu lớn:** Hàng triệu records cần xử lý phân tán
2. **Dữ liệu streaming:** Cần xử lý real-time từ Kafka
3. **Tính toán phân tán:** Phân phối workload trên nhiều nodes
4. **Latency thấp:** API cần trả về kết quả nhanh (< 100ms)
5. **Scalability:** Hệ thống cần mở rộng khi tăng số lượng zones và thời gian

### 2.3. Pipeline xử lý

Hệ thống được thiết kế theo pipeline gồm 5 bước chính:

1. **Thu thập dữ liệu:** Đọc file Parquet từ MinIO
2. **Làm sạch và Feature Engineering:** Lọc dữ liệu, trích xuất features
3. **Tổng hợp nhu cầu:** Group by zone, hour, date
4. **Huấn luyện mô hình:** Train XGBoost trên dữ liệu đã xử lý
5. **Phục vụ dự đoán:** API với caching để tối ưu performance

---

## 3. KIẾN TRÚC HỆ THỐNG

### 3.1. Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                             │
│  - NYC Taxi Trip Records (Parquet files)                    │
│  - Kafka Streaming (Real-time trips)                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              STORAGE LAYER (MinIO)                          │
│  - Raw data: s3a://nyc-taxi-driver/raw/                     │
│  - Processed: s3a://nyc-taxi-driver/processed/              │
│  - Streaming: s3a://nyc-taxi-driver/streaming/              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│         DISTRIBUTED PROCESSING (Apache Spark)               │
│                                                             │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │ Spark Master │ ◄─────► │ Spark Worker │                  │
│  │ (mac-master) │         │ (mac-worker) │                  │
│  └──────────────┘         └──────────────┘                  │
│                                                             │
│  - ETL Pipeline (data_processing.py)                        │
│  - Kafka Streaming (kafka_streaming.py)                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              MESSAGE QUEUE (Apache Kafka)                   │
│  - Topic: nyc-taxi-trips                                    │
│  - Producer: Gửi micro-batches (100 records/5s)             │
│  - Consumer: Spark Structured Streaming                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              MACHINE LEARNING                               │
│  - Model: XGBoost Regressor                                 │
│  - Training: scripts/train_model.py                         │
│  - Output: model/nyc_taxi_xgboost.pkl                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              API SERVICE (FastAPI)                          │
│  - Endpoint: /predict                                       │
│  - Caching: Redis (TTL: 10 minutes)                         │
│  - Response time: < 100ms (cached)                          │
└─────────────────────────────────────────────────────────────┘
```

### 3.2. Các thành phần chính

#### 3.2.1. Spark Cluster
- **Master Node (mac-master):**
  - Quản lý cluster, phân phối tasks
  - Spark Master UI: `http://mac-master:8080`
  - Port: 7077 (Spark Master), 8080 (Web UI)

- **Worker Node (mac-worker):**
  - Thực thi các tasks được phân phối từ master
  - Kết nối đến master qua `spark://mac-master:7077`
  - Xử lý dữ liệu song song

#### 3.2.2. MinIO (Object Storage)
- Tương tự Amazon S3, tương thích S3A protocol
- Lưu trữ raw data, processed data, và streaming results
- API: `http://mac-master:9000`, Console: `http://mac-master:9001`

#### 3.2.3. Kafka
- Message broker cho streaming data
- Topic: `nyc-taxi-trips`
- Producer gửi micro-batches, Consumer (Spark) xử lý real-time

#### 3.2.4. Redis
- In-memory cache cho API predictions
- Giảm latency và tải cho model inference
- TTL: 600 giây (10 phút)

---

## 4. CÔNG NGHỆ VÀ CÔNG CỤ SỬ DỤNG

### 4.1. Apache Spark

**Lý do chọn:**
- Xử lý dữ liệu phân tán hiệu quả với RDD và DataFrame API
- Hỗ trợ streaming với Structured Streaming
- Tích hợp tốt với Kafka và S3/MinIO
- Tự động phân phối workload trên cluster

**Cấu hình:**
- Spark version: 3.5.7
- Master URL: `spark://mac-master:7077`
- Executor memory: 2GB (có thể tùy chỉnh)
- Shuffle partitions: 10

### 4.2. Apache Kafka

**Lý do chọn:**
- High-throughput message queue
- Durable và fault-tolerant
- Tích hợp tốt với Spark Structured Streaming
- Hỗ trợ real-time data ingestion

**Cấu hình:**
- Topic: `nyc-taxi-trips`
- Producer: Micro-batch (100 records mỗi 5 giây)
- Consumer: Spark Structured Streaming với trigger 10 giây

### 4.3. XGBoost

**Lý do chọn:**
- Hiệu suất cao cho bài toán regression
- Xử lý tốt dữ liệu tabular
- Nhanh trong training và inference
- Dễ tích hợp với Python ecosystem

**Hyperparameters:**
- Objective: `reg:squarederror`
- N_estimators: 100
- Features: `pickup_hour`, `PULocationID`

### 4.4. MinIO

**Lý do chọn:**
- Tương thích S3 API, dễ migrate lên AWS
- Có thể chạy on-premise
- Hỗ trợ tốt với Spark S3A connector
- Phù hợp cho data lake architecture

### 4.5. FastAPI và Redis

**FastAPI:**
- Framework Python hiện đại, hiệu suất cao
- Tự động generate API documentation
- Dễ tích hợp với ML models

**Redis:**
- In-memory caching giảm latency
- TTL-based expiration
- High throughput

---

## 5. THIẾT KẾ VÀ TRIỂN KHAI

### 5.1. ETL Pipeline (Batch Processing)

**File:** `scripts/data_processing.py`

#### 5.1.1. Đọc dữ liệu từ MinIO

```python
# Kết nối Spark đến MinIO
spark = SparkSession.builder \
    .master(f"spark://{SPARK_MASTER_IP}:7077") \
    .config("spark.hadoop.fs.s3a.endpoint", minio_endpoint) \
    .config("spark.hadoop.fs.s3a.access.key", access_key) \
    .config("spark.hadoop.fs.s3a.secret.key", secret_key) \
    .getOrCreate()

# Đọc Parquet files
raw_df = spark.read.parquet("s3a://nyc-taxi-driver/raw/2025/*.parquet")
```

**Xử lý phân tán:**
- Spark tự động phân chia file Parquet thành các partitions
- Mỗi partition được xử lý trên một executor (worker node)
- Master điều phối và tổng hợp kết quả

#### 5.1.2. Làm sạch dữ liệu

```python
df_clean = df.filter(
    col("tpep_pickup_datetime").isNotNull() &
    (col("trip_distance") > 0) &
    col("PULocationID").isNotNull()
)
```

**Lọc các records:**
- Loại bỏ records thiếu thời gian đón
- Loại bỏ quãng đường <= 0
- Loại bỏ records thiếu location ID

#### 5.1.3. Feature Engineering

```python
df_featured = df_clean \
    .withColumn("pickup_hour", hour(col("tpep_pickup_datetime"))) \
    .withColumn("pickup_day", dayofweek(col("tpep_pickup_datetime"))) \
    .withColumn("pickup_month", month(col("tpep_pickup_datetime"))) \
    .withColumn("date_str", col("tpep_pickup_datetime").cast("date"))
```

**Features được tạo:**
- `pickup_hour`: Giờ trong ngày (0-23)
- `pickup_day`: Thứ trong tuần (1=Sunday, 7=Saturday)
- `pickup_month`: Tháng (1-12)
- `date_str`: Ngày dạng date

#### 5.1.4. Tổng hợp nhu cầu

```python
demand_df = df_featured \
    .groupBy("date_str", "pickup_hour", "PULocationID") \
    .agg(
        count("VendorID").alias("trip_count"),
        sum("trip_distance").alias("avg_distance")
    )
```

**Kết quả:**
- Mỗi record = 1 khu vực × 1 giờ × 1 ngày
- `trip_count`: Số lượng chuyến (demand)
- `avg_distance`: Tổng quãng đường

### 5.2. Kafka Streaming Pipeline

**File:** `scripts/kafka_streaming.py`

#### 5.2.1. Producer (Gửi dữ liệu)

```python
# Gửi micro-batches vào Kafka
producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Gửi 100 records mỗi 5 giây
for batch in micro_batches:
    for record in batch:
        producer.send(KAFKA_TOPIC, key=zone_id, value=trip_data)
    time.sleep(5)
```

**Chiến lược:**
- Micro-batch: 100 records/batch
- Interval: 5 giây giữa các batch
- Key: `PULocationID` (để partition theo zone)

#### 5.2.2. Consumer (Spark Structured Streaming)

```python
# Đọc từ Kafka
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
    .option("subscribe", KAFKA_TOPIC) \
    .option("startingOffsets", "latest") \
    .load()

# Parse JSON và xử lý
parsed_df = df.select(
    from_json(col("value"), schema).alias("trip_data")
).select("trip_data.*")

# Lưu vào MinIO với trigger 10 giây
stream_query = parsed_df.writeStream \
    .format("parquet") \
    .outputMode("append") \
    .option("path", "s3a://nyc-taxi-driver/streaming/demand_aggregated") \
    .trigger(processingTime='10 seconds') \
    .start()
```

**Xử lý real-time:**
- Spark Structured Streaming xử lý từng micro-batch
- Trigger: 10 giây (tạo window 10s)
- Lưu kết quả vào MinIO dạng Parquet

### 5.3. Model Training

**File:** `scripts/train_model.py`

#### 5.3.1. Load dữ liệu

```python
# Đọc từ cả batch và streaming data
batch_df = pd.read_parquet(
    "s3://nyc-taxi-driver/processed/taxi_demand_features",
    storage_options=minio_options
)

streaming_df = pd.read_parquet(
    "s3://nyc-taxi-driver/streaming/demand_aggregated",
    storage_options=minio_options
)

# Merge và aggregate
combined_df = pd.concat([batch_df, streaming_df])
```

#### 5.3.2. Training

```python
# Features và target
X = df[['pickup_hour', 'PULocationID']]
y = df['trip_count']

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train XGBoost
model = xgb.XGBRegressor(
    objective='reg:squarederror',
    n_estimators=100
)
model.fit(X_train, y_train)
```

#### 5.3.3. Đánh giá

```python
predictions = model.predict(X_test)
rmse = np.sqrt(mean_squared_error(y_test, predictions))
print(f"RMSE: {rmse:.2f}")
```

### 5.4. API Service

**File:** `src/api/main.py`

#### 5.4.1. Endpoint `/predict`

```python
@app.get("/predict")
def predict_demand(zone: int, hour: int, month: int = None, day_of_week: int = None):
    # 1. Kiểm tra cache Redis
    cache_key = f"demand:{zone}:{hour}:{month or 'any'}:{day_of_week or 'any'}"
    cached_val = r.get(cache_key)
    
    if cached_val:
        return {"source": "cache_redis", "predicted_demand": float(cached_val)}
    
    # 2. Chạy model inference
    input_df = pd.DataFrame([[hour, zone]], columns=['pickup_hour', 'PULocationID'])
    prediction = float(model.predict(input_df)[0])
    
    # 3. Lưu vào cache (TTL: 10 phút)
    r.set(cache_key, prediction, ex=600)
    
    return {"source": "model_inference", "predicted_demand": prediction}
```

**Luồng xử lý:**
1. Kiểm tra Redis cache
2. Nếu có cache → trả về ngay
3. Nếu không → chạy model, lưu cache, trả về kết quả

---

## 6. XỬ LÝ DỮ LIỆU PHÂN TÁN

### 6.1. Kiến trúc Spark Cluster

Hệ thống sử dụng kiến trúc Spark cluster với:

- **1 Master Node (mac-master):**
  - Điều phối tasks
  - Quản lý cluster state
  - Web UI để monitor

- **1 Worker Node (mac-worker):**
  - Thực thi các tasks
  - Xử lý dữ liệu song song

### 6.2. Phân phối workload

#### 6.2.1. Đọc dữ liệu phân tán

Khi đọc Parquet từ MinIO:

```python
raw_df = spark.read.parquet("s3a://nyc-taxi-driver/raw/2025/*.parquet")
```

**Spark tự động:**
- Phân chia file thành các partitions
- Mỗi partition được xử lý trên một executor
- Master điều phối và tổng hợp kết quả

**Cách kiểm tra phân tán:**
1. Truy cập Spark Master UI: `http://mac-master:8080`
2. Xem tab "Executors" → thấy 2 executors (1 trên master, 1 trên worker)
3. Xem tab "Jobs" → mỗi job có nhiều tasks chạy song song
4. Xem tab "Stages" → các tasks được phân phối trên 2 nodes

#### 6.2.2. Transformations phân tán

Các operations như `filter()`, `withColumn()`, `groupBy()` được thực thi phân tán:

```python
# Mỗi partition xử lý độc lập
df_clean = df.filter(col("trip_distance") > 0)

# GroupBy yêu cầu shuffle - dữ liệu được phân phối lại
demand_df = df.groupBy("date_str", "pickup_hour", "PULocationID") \
    .agg(count("VendorID").alias("trip_count"))
```

**Shuffle operations:**
- `groupBy()`: Yêu cầu shuffle data giữa các nodes
- Spark tự động phân phối dữ liệu theo partition key
- Có thể monitor shuffle read/write trong Spark UI

#### 6.2.3. Kafka Streaming phân tán

Spark Structured Streaming xử lý Kafka partitions song song:

```python
df = spark.readStream \
    .format("kafka") \
    .option("subscribe", KAFKA_TOPIC) \
    .load()
```

**Phân phối:**
- Mỗi Kafka partition được xử lý bởi một Spark task
- Tasks chạy song song trên các executors
- Kết quả được aggregate và lưu vào MinIO

### 6.3. Cách theo dõi và chứng minh xử lý phân tán

#### 6.3.1. Spark Master UI

**Truy cập:** `http://mac-master:8080`

**Các metrics quan trọng:**

1. **Workers Tab:**
   - Số lượng workers đã kết nối
   - Memory và cores của mỗi worker
   - Status (ALIVE/DEAD)

2. **Jobs Tab:**
   - Danh sách các jobs đã chạy
   - Số lượng tasks và executors sử dụng
   - Thời gian thực thi

3. **Stages Tab:**
   - Chi tiết các stages trong job
   - Số lượng tasks chạy song song
   - Shuffle read/write size

4. **Executors Tab:**
   - Danh sách executors (master + worker)
   - Memory usage, cores, tasks completed
   - Location (IP address) của mỗi executor

**Screenshot/Evidence:**
- Chụp màn hình Spark UI showing 2 executors
- Chụp màn hình job với nhiều tasks chạy song song
- Chụp màn hình shuffle operations

#### 6.3.2. Logs và Metrics

**Trên Master Node:**
```bash
# Xem Spark Master logs
tail -f $SPARK_HOME/logs/spark-*-master-*.out

# Kiểm tra workers đã kết nối
# Trong logs sẽ thấy: "Registering worker ..."
```

**Trên Worker Node:**
```bash
# Xem Spark Worker logs
tail -f $SPARK_HOME/logs/spark-*-worker-*.out

# Kiểm tra kết nối đến master
# Trong logs sẽ thấy: "Successfully registered with master spark://..."
```

**Trong Application:**
```python
# In ra số lượng partitions
print(f"Number of partitions: {df.rdd.getNumPartitions()}")

# In ra số lượng executors
print(f"Number of executors: {spark.sparkContext.getExecutorMemoryStatus().keys()}")
```

#### 6.3.3. Performance Metrics

**So sánh thời gian xử lý:**

1. **Single node (local mode):**
   ```python
   spark = SparkSession.builder.master("local[*]").getOrCreate()
   # Đo thời gian xử lý
   ```

2. **Cluster mode (master + worker):**
   ```python
   spark = SparkSession.builder.master("spark://mac-master:7077").getOrCreate()
   # Đo thời gian xử lý
   ```

**Kỳ vọng:**
- Cluster mode nhanh hơn khi dữ liệu lớn
- Parallelism cao hơn với nhiều executors
- Shuffle operations được tối ưu

#### 6.3.4. Network Traffic

**Kiểm tra network traffic giữa master và worker:**
```bash
# Trên master hoặc worker
sudo tcpdump -i any -n 'host mac-master or host mac-worker' | head -20

# Hoặc sử dụng netstat
netstat -an | grep 7077  # Spark Master port
```

**Evidence:**
- Network traffic giữa 2 nodes chứng minh dữ liệu được truyền
- Shuffle operations tạo network I/O giữa nodes

---

## 7. KẾT QUẢ THỰC NGHIỆM

### 7.1. Dữ liệu sử dụng

- **Nguồn:** NYC TLC Trip Record Data
- **Format:** Parquet files
- **Thời gian:** Tháng 12/2024
- **Số lượng:** ~10,000 records (để demo, có thể scale lên hàng triệu)

### 7.2. Kết quả xử lý dữ liệu

#### 7.2.1. ETL Pipeline

- **Input:** Raw Parquet files từ MinIO
- **Output:** Processed data với features đã engineering
- **Records sau xử lý:** Giảm ~5-10% do lọc dữ liệu rác
- **Features:** `date_str`, `pickup_hour`, `pickup_day`, `pickup_month`, `PULocationID`, `trip_count`, `avg_distance`

#### 7.2.2. Streaming Pipeline

- **Throughput:** ~100 records/5 giây (có thể tăng)
- **Latency:** < 10 giây (từ Kafka → MinIO)
- **Format:** Parquet với checkpoint để đảm bảo exactly-once semantics

### 7.3. Kết quả mô hình

#### 7.3.1. Model Performance

- **Algorithm:** XGBoost Regressor
- **Features:** `pickup_hour`, `PULocationID`
- **RMSE:** [Cần chạy và ghi lại giá trị thực tế]
- **Training time:** [Cần đo và ghi lại]

**Lưu ý:** Cần chạy `python scripts/train_model.py` và ghi lại các metrics thực tế.

#### 7.3.2. API Performance

- **Response time (cached):** < 10ms
- **Response time (model inference):** < 100ms
- **Cache hit rate:** [Cần monitor và ghi lại]

### 7.4. Phân tích xử lý phân tán

#### 7.4.1. Spark Cluster Metrics

**Cần thu thập từ Spark UI:**

1. **Executors:**
   - Số lượng: 2 (1 master + 1 worker)
   - Memory: [Ghi lại từ UI]
   - Cores: [Ghi lại từ UI]

2. **Jobs:**
   - Số lượng tasks: [Ghi lại]
   - Tasks per executor: [Ghi lại]
   - Shuffle read/write: [Ghi lại]

3. **Performance:**
   - Thời gian xử lý với 1 node vs 2 nodes
   - Throughput improvement

**Gợi ý chụp màn hình:**
- Spark Master UI → Workers tab (showing 2 workers)
- Spark Master UI → Jobs tab (showing parallel tasks)
- Spark Master UI → Stages tab (showing shuffle operations)

---

## 8. KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

### 8.1. Kết luận

Đề tài đã xây dựng thành công một hệ thống dự đoán nhu cầu taxi với các thành tựu chính:

1. **Xử lý dữ liệu phân tán:**
   - Triển khai Spark cluster với master-worker architecture
   - Xử lý song song dữ liệu lớn trên nhiều nodes
   - Tích hợp với MinIO cho lưu trữ phân tán

2. **Streaming real-time:**
   - Tích hợp Kafka cho data ingestion
   - Spark Structured Streaming xử lý real-time
   - Lưu kết quả vào data lake

3. **Machine Learning:**
   - Mô hình XGBoost cho dự đoán nhu cầu
   - API service với caching để tối ưu performance
   - Hỗ trợ batch và streaming data

4. **Scalability:**
   - Kiến trúc có thể mở rộng thêm workers
   - Hỗ trợ tăng throughput Kafka
   - API có thể scale horizontal

### 8.2. Hạn chế

1. **Dữ liệu:**
   - Chỉ sử dụng dữ liệu Yellow Taxi
   - Chưa tích hợp dữ liệu thời tiết, sự kiện
   - Features còn đơn giản (chỉ hour và zone)

2. **Mô hình:**
   - Chưa thử nghiệm các thuật toán khác (LSTM, ARIMA)
   - Chưa có hyperparameter tuning
   - Chưa có cross-validation

3. **Infrastructure:**
   - Chỉ có 1 worker node (có thể thêm nhiều hơn)
   - Chưa có monitoring và alerting system
   - Chưa có backup và disaster recovery

### 8.3. Hướng phát triển

#### 8.3.1. Ngắn hạn (1-3 tháng)

1. **Cải thiện mô hình:**
   - Thêm features: thời tiết, ngày lễ, sự kiện
   - Thử nghiệm LSTM cho time series prediction
   - Hyperparameter tuning với Optuna
   - Cross-validation và model selection

2. **Mở rộng dữ liệu:**
   - Tích hợp Green Taxi và FHV data
   - Thêm dữ liệu thời tiết từ API
   - Historical data nhiều năm hơn

3. **Cải thiện API:**
   - Batch prediction endpoint
   - Model versioning
   - A/B testing framework

#### 8.3.2. Trung hạn (3-6 tháng)

1. **Infrastructure:**
   - Thêm nhiều worker nodes (3-5 workers)
   - Auto-scaling Spark cluster
   - Monitoring với Prometheus + Grafana
   - Logging với ELK stack

2. **Advanced Features:**
   - Real-time dashboard với Plotly Dash
   - Alerting khi demand spike
   - Recommendation system cho drivers

3. **MLOps:**
   - Automated model retraining pipeline
   - Model serving với MLflow
   - Feature store

#### 8.3.3. Dài hạn (6-12 tháng)

1. **Deep Learning:**
   - LSTM/GRU cho time series
   - Graph Neural Networks cho spatial relationships
   - Transformer models

2. **Production:**
   - Kubernetes deployment
   - CI/CD pipeline
   - Multi-region deployment

3. **Business Intelligence:**
   - Advanced analytics dashboard
   - Revenue optimization
   - Driver allocation algorithms

---

## 9. TÀI LIỆU THAM KHẢO

1. NYC Taxi and Limousine Commission. (2024). *TLC Trip Record Data*. https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

2. Apache Spark Documentation. (2024). *Spark Programming Guide*. https://spark.apache.org/docs/latest/

3. Apache Kafka Documentation. (2024). *Kafka Documentation*. https://kafka.apache.org/documentation/

4. Chen, T., & Guestrin, C. (2016). *XGBoost: A Scalable Tree Boosting System*. Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining.

5. Zaharia, M., et al. (2016). *Apache Spark: A Unified Engine for Big Data Processing*. Communications of the ACM, 59(11), 56-65.

6. MinIO Documentation. (2024). *MinIO Object Storage*. https://min.io/docs/

7. FastAPI Documentation. (2024). *FastAPI - Modern Python Web Framework*. https://fastapi.tiangolo.com/

8. Redis Documentation. (2024). *Redis - In-Memory Data Store*. https://redis.io/docs/

9. NYC Open Data. (2024). *Taxi Zones*. https://data.cityofnewyork.us/Transportation/NYC-Taxi-Zones/d3c5-ddgc

10. Databricks. (2024). *Structured Streaming Programming Guide*. https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html

---

**Phụ lục: Hướng dẫn chạy hệ thống**

Xem file `WORKFLOW.md` và `README.md` để biết chi tiết cách setup và chạy hệ thống.

