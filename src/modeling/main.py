import pandas as pd
import numpy as np
import xgboost as xgb
import pickle
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

class TaxiDemandPredictor:
    def __init__(self):
        self.model = None

    def load_data(self, s3_path, storage_options):
        """Đọc dữ liệu đã xử lý từ MinIO về Pandas"""
        # storage_options giúp Pandas đọc trực tiếp s3
        df = pd.read_parquet(s3_path, storage_options=storage_options)
        return df
    
    def load_data_multiple_sources(self, batch_path, streaming_path, storage_options):
        """
        Đọc và merge dữ liệu từ cả batch và streaming sources
        
        Args:
            batch_path: Đường dẫn batch data (s3://bucket/processed/taxi_demand_features)
            streaming_path: Đường dẫn streaming data (s3://bucket/streaming/demand_aggregated)
            storage_options: MinIO connection options
        """
        print("📥 Đang tải dữ liệu từ nhiều nguồn...")
        
        # Load batch data
        try:
            batch_df = pd.read_parquet(batch_path, storage_options=storage_options)
            print(f"✓ Batch data: {len(batch_df):,} records")
        except Exception as e:
            print(f"⚠ Không đọc được batch data: {e}")
            batch_df = pd.DataFrame()
        
        # Load streaming data
        try:
            streaming_df = pd.read_parquet(streaming_path, storage_options=storage_options)
            print(f"✓ Streaming data: {len(streaming_df):,} records")
            
            # Nếu streaming có window column, extract date_str từ window
            if 'window' in streaming_df.columns:
                # Window format: [2025-01-04 16:30:00, 2025-01-04 16:31:00)
                # Extract start time và convert to date
                streaming_df['date_str'] = pd.to_datetime(streaming_df['window'].str.split(',').str[0].str.strip('['))
                streaming_df['date_str'] = streaming_df['date_str'].dt.date
            
            # Nếu streaming data chưa có aggregation (thiếu trip_count, avg_distance)
            # Thì aggregate từ raw data
            if 'trip_count' not in streaming_df.columns or 'avg_distance' not in streaming_df.columns:
                print("  → Aggregating streaming data...")
                # Kiểm tra có đủ columns để aggregate không
                if all(col in streaming_df.columns for col in ['date_str', 'pickup_hour', 'PULocationID', 'trip_distance']):
                    # Aggregate: count trips và sum distance
                    streaming_df = streaming_df.groupby(['date_str', 'pickup_hour', 'PULocationID']).agg({
                        'trip_distance': ['count', 'sum']  # count = trip_count, sum = avg_distance
                    }).reset_index()
                    streaming_df.columns = ['date_str', 'pickup_hour', 'PULocationID', 'trip_count', 'avg_distance']
                    print(f"  ✓ Aggregated to {len(streaming_df):,} records")
                else:
                    print("⚠ Streaming data thiếu columns để aggregate, bỏ qua...")
                    streaming_df = pd.DataFrame()
            else:
                # Đảm bảo columns giống batch
                required_cols = ['date_str', 'pickup_hour', 'PULocationID', 'trip_count', 'avg_distance']
                if not all(col in streaming_df.columns for col in required_cols):
                    print("⚠ Streaming data thiếu columns, bỏ qua...")
                    streaming_df = pd.DataFrame()
        except Exception as e:
            print(f"⚠ Không đọc được streaming data: {e}")
            streaming_df = pd.DataFrame()
        
        # Merge 2 dataframes
        if not batch_df.empty and not streaming_df.empty:
            # Combine và remove duplicates (nếu có overlap)
            combined_df = pd.concat([batch_df, streaming_df], ignore_index=True)
            # Group by để aggregate nếu có duplicate (date_str, pickup_hour, PULocationID)
            combined_df = combined_df.groupby(['date_str', 'pickup_hour', 'PULocationID']).agg({
                'trip_count': 'sum',
                'avg_distance': 'sum'
            }).reset_index()
            print(f"✓ Combined data: {len(combined_df):,} records")
            return combined_df
        elif not batch_df.empty:
            return batch_df
        elif not streaming_df.empty:
            return streaming_df
        else:
            raise ValueError("Không có dữ liệu từ cả 2 nguồn!")

    def train(self, df):
        # Chọn features và target
        # Features: Giờ, Khu vực. Target: Số chuyến xe
        X = df[['pickup_hour', 'PULocationID']] 
        y = df['trip_count']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Đang train XGBoost Model...")
        self.model = xgb.XGBRegressor(objective='reg:squarederror', n_estimators=100)
        self.model.fit(X_train, y_train)
        
        # Đánh giá sơ bộ
        predictions = self.model.predict(X_test)
        mse = mean_squared_error(y_test, predictions)
        rmse = np.sqrt(mse)
        print(f"Model RMSE: {rmse:.2f}")
        return self.model

    def save_model(self, path="model.pkl"):
        with open(path, "wb") as f:
            pickle.dump(self.model, f)
        print(f"Model đã lưu tại: {path}")