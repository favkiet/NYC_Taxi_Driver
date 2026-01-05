"""
Kafka Streaming - Gửi dữ liệu vào Kafka và xử lý real-time
"""
import os
import sys
import json
import time
import threading
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from kafka import KafkaProducer
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, hour, to_timestamp
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType

# Load biến môi trường
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

###############################################
# Parameters & Arguments
###############################################
KAFKA_HOST = os.getenv("KAFKA_HOST", "localhost")
KAFKA_PORT = os.getenv("KAFKA_PORT", "9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "nyc-taxi-trips")
KAFKA_BOOTSTRAP_SERVERS = f"{KAFKA_HOST}:{KAFKA_PORT}"

SPARK_MASTER_IP = os.getenv("SPARK_MASTER_IP", "localhost")
SPARK_MASTER_PORT = os.getenv("SPARK_MASTER_PORT", "7077")
SPARK_EXECUTOR_MEMORY = os.getenv("SPARK_EXECUTOR_MEMORY", "2g")

MINIO_PORT = os.getenv("MINIO_PORT", "9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")
MINIO_ENDPOINT = f"http://{SPARK_MASTER_IP}:{MINIO_PORT}"

BUCKET_NAME = "nyc-taxi-driver"
PARQUET_PATH = os.getenv("PRODUCER_PARQUET_PATH", "data/raw/2025/yellow_tripdata_2024-12.parquet")
LIMIT_ROWS = 10000
###############################################


###############################################
# Producer - Gửi dữ liệu vào Kafka
###############################################
def ensure_topic_exists():
    """
    Đảm bảo topic tồn tại bằng cách gửi 1 message test
    """
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            retries=3
        )
        # Gửi 1 message test để tạo topic (nếu auto-create enabled)
        producer.send(KAFKA_TOPIC, value={"test": "init"}).get(timeout=10)
        producer.flush()
        producer.close()
        print(f"✓ Topic '{KAFKA_TOPIC}' đã sẵn sàng\n")
        return True
    except Exception as e:
        print(f"⚠ Không thể tạo topic: {e}")
        print("  (Topic sẽ được tạo tự động khi gửi message đầu tiên)\n")
        return False

def send_micro_batches():
    """
    Gửi dữ liệu vào Kafka theo micro-batch (chạy trong thread riêng)
    """
    print(f"\n{'='*60}")
    print("📤 GỬI DỮ LIỆU VÀO KAFKA (Micro-batch)")
    print(f"{'='*60}")
    print(f"File: {PARQUET_PATH}")
    print(f"Giới hạn: {LIMIT_ROWS:,} rows")
    print(f"Topic: {KAFKA_TOPIC}")
    print(f"📦 Micro-batch: 100 records/batch, mỗi 5 giây\n")
    
    if not os.path.exists(PARQUET_PATH):
        print(f"✗ File không tồn tại: {PARQUET_PATH}")
        return
    
    try:
        # Khởi tạo producer
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: str(k).encode('utf-8') if k else None,
            acks='all',
            retries=3
        )
        
        # Đọc parquet
        df = pd.read_parquet(PARQUET_PATH).head(LIMIT_ROWS)
        print(f"✓ Đã đọc {len(df):,} records từ parquet\n")
        
        batch_size = 100
        total_batches = (len(df) + batch_size - 1) // batch_size
        
        # Đợi 2 giây để streaming sẵn sàng
        print("⏳ Đợi 2 giây để streaming sẵn sàng...\n")
        time.sleep(2)
        
        # Gửi từng micro-batch
        for batch_num in range(0, len(df), batch_size):
            end_idx = min(batch_num + batch_size, len(df))
            batch_df = df.iloc[batch_num:end_idx]
            batch_id = batch_num // batch_size
            
            # Gửi từng record trong batch
            for _, record in batch_df.iterrows():
                trip_data = {
                    'PULocationID': record.get('PULocationID'),
                    'DOLocationID': record.get('DOLocationID'),
                    'trip_distance': record.get('trip_distance'),
                    'pickup_datetime': str(record.get('tpep_pickup_datetime', '')),
                    'dropoff_datetime': str(record.get('tpep_dropoff_datetime', '')),
                    'passenger_count': record.get('passenger_count', 1),
                    'total_amount': record.get('total_amount', 0)
                }
                
                # Lọc None values
                trip_data = {k: v for k, v in trip_data.items() if v is not None}
                
                key = trip_data.get('PULocationID')
                producer.send(KAFKA_TOPIC, key=key, value=trip_data)
            
            # Flush batch
            producer.flush()
            print(f"📤 Batch #{batch_id}: Đã gửi {len(batch_df)} records (tổng: {end_idx}/{len(df)})")
            
            # Đợi 5 giây trước khi gửi batch tiếp theo (trừ batch cuối)
            if end_idx < len(df):
                time.sleep(5)
        
        producer.close()
        print(f"\n✅ Hoàn thành: Đã gửi {len(df):,} records trong {total_batches} batches\n")
        
    except Exception as e:
        print(f"✗ Lỗi khi gửi dữ liệu: {e}")
###############################################


###############################################
# PySpark
###############################################
def create_spark_session():
    """
    Create the Spark Session with suitable configs
    """
    try:
        spark = SparkSession.builder \
            .config("spark.executor.memory", SPARK_EXECUTOR_MEMORY) \
            .config("spark.jars.packages", 
                    "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.7," +
                    "org.apache.hadoop:hadoop-aws:3.3.4," +
                    "com.amazonaws:aws-java-sdk-bundle:1.12.540") \
            .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
            .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
            .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
            .config("spark.hadoop.fs.s3a.path.style.access", "true") \
            .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
            .config("spark.sql.shuffle.partitions", "10") \
            .appName("NYC_Taxi_Kafka_Streaming") \
            .master(f"spark://{SPARK_MASTER_IP}:{SPARK_MASTER_PORT}") \
            .config("spark.driver.host", SPARK_MASTER_IP) \
            .getOrCreate()
        
        spark.sparkContext.setLogLevel("WARN")
        print("✓ Spark session successfully created!")
        return spark
        
    except Exception as e:
        print(f"✗ Couldn't create the spark session due to exception: {e}")
        raise


def create_initial_dataframe(spark_session):
    """
    Reads the streaming data and creates the initial dataframe accordingly
    """
    try:
        df = spark_session \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
            .option("subscribe", KAFKA_TOPIC) \
            .option("startingOffsets", "latest") \
            .option("failOnDataLoss", "false") \
            .load()
        print("✓ Initial dataframe created successfully!")
        print("  - Reading from latest offset (chỉ đọc dữ liệu mới)")
        return df
    except Exception as e:
        print(f"✗ Initial dataframe could not be created due to exception: {e}")
        raise


def create_final_dataframe(df, spark_session):
    """
    Modifies the initial dataframe, and creates the final dataframe
    """
    # Schema cho dữ liệu taxi trip
    trip_schema = StructType([
        StructField("PULocationID", IntegerType(), True),
        StructField("DOLocationID", IntegerType(), True),
        StructField("trip_distance", DoubleType(), True),
        StructField("pickup_datetime", StringType(), True),
        StructField("dropoff_datetime", StringType(), True),
        StructField("passenger_count", IntegerType(), True),
        StructField("total_amount", DoubleType(), True)
    ])
    
    # Parse JSON messages
    parsed_df = df.selectExpr("CAST(value AS STRING) as json") \
        .select(from_json(col("json"), trip_schema).alias("trip_data")) \
        .select("trip_data.*")
    
    # Chuyển đổi datetime
    parsed_df = parsed_df \
        .withColumn("pickup_datetime", to_timestamp(col("pickup_datetime"), "yyyy-MM-dd HH:mm:ss")) \
        .withColumn("dropoff_datetime", to_timestamp(col("dropoff_datetime"), "yyyy-MM-dd HH:mm:ss"))
    
    # Lọc dữ liệu hợp lệ
    parsed_df = parsed_df.filter(
        col("PULocationID").isNotNull() &
        (col("trip_distance") > 0) &
        col("pickup_datetime").isNotNull()
    )
    
    # Feature engineering
    df_final = parsed_df \
        .withColumn("pickup_hour", hour(col("pickup_datetime"))) \
        .withColumn("date_str", col("pickup_datetime").cast("date"))
    
    print("✓ Final dataframe created successfully!")
    return df_final


def start_streaming(df):
    """
    Store data into Datalake (MinIO) with parquet format
    """
    output_path = f"s3a://{BUCKET_NAME}/streaming/demand_aggregated"
    checkpoint_location = f"s3a://{BUCKET_NAME}/streaming/checkpoint"
    
    print(f"\n💾 Lưu vào MinIO:")
    print(f"   Output: {output_path}")
    print(f"   Checkpoint: {checkpoint_location}")
    print("   (Nhấn Ctrl+C để dừng)...\n")
    
    print("Streaming is being started...")
    print("  - Trigger: 10 seconds (để thấy rõ từng batch)")
    stream_query = df.writeStream \
        .format("parquet") \
        .outputMode("append") \
        .option("path", output_path) \
        .option("checkpointLocation", checkpoint_location) \
        .trigger(processingTime='10 seconds') \
        .start()
    
    return stream_query.awaitTermination()
###############################################


###############################################
# Main
###############################################
if __name__ == '__main__':
    print("=" * 60)
    print("🚀 KAFKA STREAMING - PRODUCER + CONSUMER")
    print("=" * 60)
    
    try:
        # Bước 1: Đảm bảo topic tồn tại trước
        print("🔧 Kiểm tra và tạo topic...")
        ensure_topic_exists()
        time.sleep(2)  # Đợi topic được tạo hoàn toàn
        
        # Bước 2: Khởi động streaming
        print("🔄 Khởi động streaming...")
        spark = create_spark_session()
        df = create_initial_dataframe(spark)
        df_final = create_final_dataframe(df, spark)
        
        output_path = f"s3a://{BUCKET_NAME}/streaming/demand_aggregated"
        checkpoint_location = f"s3a://{BUCKET_NAME}/streaming/checkpoint"
        
        print(f"\n💾 Lưu vào MinIO:")
        print(f"   Output: {output_path}")
        print(f"   Checkpoint: {checkpoint_location}")
        print(f"   Trigger: 10 seconds (để thấy rõ từng batch)\n")
        
        # Bước 3: Bắt đầu streaming
        stream_query = df_final.writeStream \
            .format("parquet") \
            .outputMode("append") \
            .option("path", output_path) \
            .option("checkpointLocation", checkpoint_location) \
            .trigger(processingTime='10 seconds') \
            .start()
        
        print("✓ Streaming đã bắt đầu và sẵn sàng nhận dữ liệu\n")
        
        # Bước 4: Gửi micro-batch trong thread riêng (song song với streaming)
        producer_thread = threading.Thread(target=send_micro_batches, daemon=True)
        producer_thread.start()
        
        # Đợi streaming chạy (sẽ xử lý dữ liệu ngay khi có)
        print("⏳ Streaming đang chạy... (Nhấn Ctrl+C để dừng)\n")
        stream_query.awaitTermination()
        
    except KeyboardInterrupt:
        print("\n⚠ Đã dừng")
    except Exception as e:
        print(f"\n✗ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if 'spark' in locals():
            spark.stop()
            print("\n✓ Spark session đã dừng")
###############################################
