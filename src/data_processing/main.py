from pyspark.sql import SparkSession
from pyspark.sql.functions import col, hour, dayofweek, month, to_timestamp, count, sum as _sum, when, coalesce

class TaxiDataProcessor:
    def __init__(self, spark: SparkSession):
        self.spark = spark

    def read_from_minio(self, bucket_name: str, folders: list):
        """
        Đọc dữ liệu từ nhiều folder khác nhau trên MinIO (Yellow và Green Taxi)
        """
        full_paths = [
            "s3a://nyc-taxi-driver/raw/2025/*.parquet",  # Yellow Taxi
        ]
        print(f"\n{'='*60}")
        print("📥 BƯỚC 1: ĐỌC DỮ LIỆU TỪ MINIO")
        print(f"{'='*60}")
        print("Đang đọc dữ liệu từ:")
        for path in full_paths:
            print(f"  - {path}")
        
        # option("mergeSchema", "true") để gộp schema nếu 2 loại taxi lệch nhau
        df = self.spark.read.option("mergeSchema", "true").parquet(*full_paths)
        
        total_records = df.count()
        print(f"\n✓ Đã đọc thành công: {total_records:,} records")
        
        # Kiểm tra loại taxi
        has_yellow = "tpep_pickup_datetime" in df.columns
        has_green = "lpep_pickup_datetime" in df.columns
        
        if has_yellow and has_green:
            yellow_count = df.filter(col("tpep_pickup_datetime").isNotNull()).count()
            green_count = df.filter(col("lpep_pickup_datetime").isNotNull()).count()
            print(f"  - Yellow Taxi: {yellow_count:,} records")
            print(f"  - Green Taxi: {green_count:,} records")
        elif has_yellow:
            print("  - Chỉ có Yellow Taxi")
        elif has_green:
            print("  - Chỉ có Green Taxi")
        
        print(f"Schema có {len(df.columns)} cột")
        return df

    def clean_and_engineer(self, df):
        """
        Bước 1 & 2: Làm sạch + Feature Engineering (Time & Zone)
        Xử lý cả Yellow Taxi (tpep_pickup_datetime) và Green Taxi (lpep_pickup_datetime)
        """
        print("\n{'='*60}")
        print("🧹 BƯỚC 2: LÀM SẠCH VÀ FEATURE ENGINEERING")
        print(f"{'='*60}")
        
        initial_count = df.count()
        print(f"Records ban đầu: {initial_count:,}")
        
        # Tạo cột pickup_datetime thống nhất từ cả 2 loại taxi
        pickup_datetime = coalesce(
            col("tpep_pickup_datetime"),  # Yellow Taxi
            col("lpep_pickup_datetime")   # Green Taxi
        )
        
        # Lọc dữ liệu rác
        print("\nĐang lọc dữ liệu:")
        print("  - Loại bỏ records thiếu pickup_datetime")
        df_after_datetime = df.filter(pickup_datetime.isNotNull())
        print("  - Loại bỏ records có trip_distance <= 0")
        df_after_distance = df_after_datetime.filter(col("trip_distance") > 0)
        print("  - Loại bỏ records thiếu PULocationID")
        df_clean = df_after_distance.filter(col("PULocationID").isNotNull())
        
        cleaned_count = df_clean.count()
        removed_count = initial_count - cleaned_count
        print(f"\n✓ Sau khi làm sạch: {cleaned_count:,} records (đã loại bỏ {removed_count:,} records)")
        
        # Feature Engineering: Tách giờ, thứ, ngày tháng
        print(f"\nĐang tạo features:")
        print("  - pickup_datetime (thống nhất từ Yellow/Green)")
        print("  - pickup_hour, pickup_day, pickup_month")
        print("  - date_str")
        
        df_featured = df_clean.withColumn("pickup_datetime", pickup_datetime) \
                            .withColumn("pickup_hour", hour(pickup_datetime)) \
                            .withColumn("pickup_day", dayofweek(pickup_datetime)) \
                            .withColumn("pickup_month", month(pickup_datetime)) \
                            .withColumn("date_str", pickup_datetime.cast("date"))
        
        print("✓ Hoàn thành feature engineering")
        return df_featured

    def aggregate_demand(self, df):
        """
        Bước 3: Tổng hợp nhu cầu (Demand Aggregation)
        Output: Mỗi dòng là 1 Khu vực - 1 Khung giờ - Số lượng chuyến
        """
        print(f"\n{'='*60}")
        print("📊 BƯỚC 3: TỔNG HỢP NHU CẦU")
        print(f"{'='*60}")
        
        input_count = df.count()
        print(f"Records đầu vào: {input_count:,}")
        
        print("\nĐang tổng hợp theo:")
        print("  - date_str (ngày)")
        print("  - pickup_hour (giờ)")
        print("  - PULocationID (khu vực)")
        print(f"\nTính toán:")
        print("  - trip_count: số lượng chuyến")
        print("  - avg_distance: tổng quãng đường")
        
        df_agg = df.groupBy("date_str", "pickup_hour", "PULocationID") \
                    .agg(
                        count("VendorID").alias("trip_count"), # Số lượng xe đón (Demand)
                        _sum("trip_distance").alias("avg_distance")
                    )
        
        output_count = df_agg.count()
        print(f"\n✓ Sau khi tổng hợp: {output_count:,} records")
        print("  (Mỗi record = 1 khu vực x 1 khung giờ x 1 ngày)")
        
        return df_agg