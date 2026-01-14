import pandas as pd
import numpy as np
import xgboost as xgb
import pickle
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

class TaxiDemandPredictor:
    def __init__(self):
        self.model = None
        self.feature_names = ['day_of_week', 'month', 'is_weekend', 'pickup_hour', 'PULocationID']

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

    def extract_date_features(self, df):
        """
        Extract features từ date_str: day_of_week, month, is_weekend
        """
        # Đảm bảo date_str là datetime
        # Xử lý các trường hợp: date object, string, hoặc datetime
        if df['date_str'].dtype == 'object':
            # Có thể là string hoặc date object
            df['date_str'] = pd.to_datetime(df['date_str'])
        elif not pd.api.types.is_datetime64_any_dtype(df['date_str']):
            # Nếu không phải datetime, convert
            df['date_str'] = pd.to_datetime(df['date_str'])
        
        # Extract features từ date
        df['day_of_week'] = df['date_str'].dt.dayofweek  # 0=Monday, 6=Sunday
        df['month'] = df['date_str'].dt.month  # 1-12
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)  # Saturday=5, Sunday=6
        
        return df

    def train(self, df):
        """
        Train model với features: date_str (extracted), pickup_hour, PULocationID
        Target: trip_count
        """
        print("\n🔧 Đang extract features từ date_str...")
        df = self.extract_date_features(df.copy())
        
        # Chọn features và target
        # Features: day_of_week, month, is_weekend, pickup_hour, PULocationID
        feature_cols = ['day_of_week', 'month', 'is_weekend', 'pickup_hour', 'PULocationID']
        
        # Kiểm tra columns có tồn tại không
        missing_cols = [col for col in feature_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Thiếu columns: {missing_cols}")
        
        X = df[feature_cols]
        y = df['trip_count']
        
        print(f"✓ Features sử dụng: {feature_cols}")
        print(f"✓ Số lượng samples: {len(X):,}")
        print(f"✓ Target: trip_count (min={y.min():.0f}, max={y.max():.0f}, mean={y.mean():.2f})")

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("\n🚀 Đang train XGBoost Model...")
        self.model = xgb.XGBRegressor(
            objective='reg:squarederror', 
            n_estimators=100,
            random_state=42
        )
        self.model.fit(X_train, y_train)
        
        # Đánh giá sơ bộ
        predictions = self.model.predict(X_test)
        mse = mean_squared_error(y_test, predictions)
        rmse = np.sqrt(mse)
        print(f"✓ Model RMSE: {rmse:.2f}")
        print(f"✓ Model MAE: {np.mean(np.abs(y_test - predictions)):.2f}")
        
        # Lưu feature names để API sử dụng
        self.feature_names = feature_cols
        
        return self.model

    def save_model(self, path="model.pkl"):
        """
        Lưu model và feature names
        """
        model_data = {
            'model': self.model,
            'feature_names': self.feature_names
        }
        with open(path, "wb") as f:
            pickle.dump(model_data, f)
        print(f"Model đã lưu tại: {path}")
        print(f"Features: {self.feature_names}")