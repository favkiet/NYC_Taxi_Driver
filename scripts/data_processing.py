import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

# Thêm đường dẫn root vào system path
sys.path.append(os.getcwd())

# Load biến môi trường từ file .env
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from pyspark.sql import SparkSession
from src.data_processing.main import TaxiDataProcessor

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
def ensure_bucket_exists(bucket_name: str, endpoint: str, access_key: str, secret_key: str):
    """Kiểm tra và tạo bucket nếu chưa tồn tại"""
    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key
    )
    
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' đã tồn tại")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            s3_client.create_bucket(Bucket=bucket_name)
            print(f"Đã tạo bucket '{bucket_name}'")
        else:
            raise

def main():
    # CẤU HÌNH TỪ FILE ENV
    MAC_IP = os.getenv("SPARK_MASTER_IP")
    SPARK_MASTER_PORT = os.getenv("SPARK_MASTER_PORT")
    SPARK_EXECUTOR_MEMORY = os.getenv("SPARK_EXECUTOR_MEMORY")
    MINIO_PORT = os.getenv("MINIO_PORT")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
    
    # Kiểm tra và tạo bucket trước khi khởi tạo Spark
    bucket_name = "nyc-taxi-driver"
    minio_endpoint = f"http://{MAC_IP}:{MINIO_PORT}"
    ensure_bucket_exists(bucket_name, minio_endpoint, MINIO_ACCESS_KEY, MINIO_SECRET_KEY)
    
    spark = SparkSession.builder \
        .appName("NYC_Taxi_Distributed_ETL") \
        .master(f"spark://{MAC_IP}:{SPARK_MASTER_PORT}") \
        .config(
            "spark.jars",
            f"{PROJECT_ROOT}/jars/hadoop-aws-3.3.4.jar,"
            f"{PROJECT_ROOT}/jars/aws-java-sdk-bundle-1.12.540.jar"
        ) \
        .config("spark.driver.host", MAC_IP) \
        .config("spark.executor.memory", SPARK_EXECUTOR_MEMORY) \
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.540") \
        .config("spark.hadoop.fs.s3a.endpoint", minio_endpoint) \
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .getOrCreate()

    processor = TaxiDataProcessor(spark)

    # 1. Đọc dữ liệu từ 2 nguồn (Mac Folder và Win Folder)
    # raw: chứa data 2025 (từ Mac), raw_win: chứa data 2024 (từ Win)
    raw_df = processor.read_from_minio("nyc-taxi-driver", ["raw"])

    # 2. Xử lý
    processed_df = processor.clean_and_engineer(raw_df)

    # 3. Tổng hợp nhu cầu
    demand_df = processor.aggregate_demand(processed_df)

    # 4. Lưu kết quả đã xử lý xuống MinIO (Processed) để dùng train model
    print(f"\n{'='*60}")
    print("💾 BƯỚC 4: LƯU KẾT QUẢ XUỐNG MINIO")
    print(f"{'='*60}")
    output_path = "s3a://nyc-taxi-driver/processed/taxi_demand_features"
    print(f"Đường dẫn output: {output_path}")
    print("Format: Parquet (nén)")
    print("Mode: overwrite")
    print("Partitions: 1 (coalesce để dễ đọc bằng Pandas)")
    
    final_count = demand_df.count()
    print(f"\nĐang lưu {final_count:,} records...")
    
    demand_df.coalesce(1).write.mode("overwrite").parquet(output_path)
    
    print("✓ Đã lưu thành công!")
    print("\n{'='*60}")
    print("✅ HOÀN THÀNH ETL PIPELINE")
    print("{'='*60}\n")
    
    spark.stop()

if __name__ == "__main__":
    main()