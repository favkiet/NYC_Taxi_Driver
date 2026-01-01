import sys
import os
# Thêm đường dẫn root vào system path
sys.path.append(os.getcwd())

from pyspark.sql import SparkSession
from src.data_processing.main import TaxiDataProcessor

def main():
    # CẤU HÌNH MINIO
    MAC_IP = "100.122.52.41" 
    
    spark = SparkSession.builder \
        .appName("NYC_Taxi_Distributed_ETL") \
        .master(f"spark://{MAC_IP}:7077") \
        .config("spark.driver.host", MAC_IP) \
        .config("spark.executor.memory", "2g") \
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.540") \
        .config("spark.hadoop.fs.s3a.endpoint", f"http://{MAC_IP}:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "admin") \
        .config("spark.hadoop.fs.s3a.secret.key", "password123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .getOrCreate()

    processor = TaxiDataProcessor(spark)

    # 1. Đọc dữ liệu từ 2 nguồn (Mac Folder và Win Folder)
    # raw: chứa data 2025 (từ Mac), raw_win: chứa data 2024 (từ Win)
    raw_df = processor.read_from_minio("nyc-taxi-driver", ["raw", "raw_win"])

    # 2. Xử lý
    processed_df = processor.clean_and_engineer(raw_df)

    # 3. Tổng hợp nhu cầu
    demand_df = processor.aggregate_demand(processed_df)

    # 4. Lưu kết quả đã xử lý xuống MinIO (Processed) để dùng train model
    output_path = "s3a://nyc-taxi-driver/processed/taxi_demand_features"
    print(f"Đang lưu kết quả xuống: {output_path}")
    
    # Lưu dưới dạng Parquet (đã nén), coalesce(1) để gom về 1 file cho dễ đọc bằng Pandas sau này
    demand_df.coalesce(1).write.mode("overwrite").parquet(output_path)
    
    spark.stop()

if __name__ == "__main__":
    main()