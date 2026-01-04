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