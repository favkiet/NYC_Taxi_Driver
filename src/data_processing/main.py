from pyspark.sql import SparkSession
from pyspark.sql.functions import col, hour, dayofweek, month, to_timestamp, count, sum as _sum

class TaxiDataProcessor:
    def __init__(self, spark: SparkSession):
        self.spark = spark

    def read_from_minio(self, bucket_name: str, folders: list):
        """
        Đọc dữ liệu từ nhiều folder khác nhau trên MinIO (raw và raw_win)
        """
        full_paths = [
            "s3a://nyc-taxi-driver/raw/2025/*.parquet",
            "s3a://nyc-taxi-driver/raw_win/2024/*.parquet"
        ]
        print(f"--- Đang đọc dữ liệu từ: {full_paths} ---")
        
        # option("mergeSchema", "true") để gộp schema nếu 2 file năm 2024 và 2025 lệch nhau xíu
        df = self.spark.read.option("mergeSchema", "true").parquet(*full_paths)
        return df

    def clean_and_engineer(self, df):
        """
        Bước 1 & 2: Làm sạch + Feature Engineering (Time & Zone)
        """
        # Giả sử tên cột thời gian đón là 'lpep_pickup_datetime' (Green Taxi)
        # Nếu Yellow Taxi thì là 'tpep_pickup_datetime'
        time_col = "lpep_pickup_datetime"
        
        # Lọc dữ liệu rác
        df_clean = df.filter(col(time_col).isNotNull()) \
                     .filter(col("trip_distance") > 0) \
                     .filter(col("PULocationID").isNotNull()) # Zone ID

        # Feature Engineering: Tách giờ, thứ, ngày tháng
        df_featured = df_clean.withColumn("pickup_hour", hour(col(time_col))) \
                              .withColumn("pickup_day", dayofweek(col(time_col))) \
                              .withColumn("pickup_month", month(col(time_col))) \
                              .withColumn("date_str", col(time_col).cast("date"))
        return df_featured

    def aggregate_demand(self, df):
        """
        Bước 3: Tổng hợp nhu cầu (Demand Aggregation)
        Output: Mỗi dòng là 1 Khu vực - 1 Khung giờ - Số lượng chuyến
        """
        df_agg = df.groupBy("date_str", "pickup_hour", "PULocationID") \
                   .agg(
                       count("VendorID").alias("trip_count"), # Số lượng xe đón (Demand)
                       _sum("trip_distance").alias("avg_distance")
                   )
        return df_agg