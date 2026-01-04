import os
import requests
from pathlib import Path
from dotenv import load_dotenv
import boto3

# Load biến môi trường
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

def download_green_taxi_data():
    """Download Green Taxi data từ tháng 1-10 năm 2025 về local, sau đó upload lên MinIO"""
    
    MAC_IP = os.getenv("SPARK_MASTER_IP")
    MINIO_PORT = os.getenv("MINIO_PORT")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
    
    minio_endpoint = f"http://{MAC_IP}:{MINIO_PORT}"
    bucket_name = "nyc-taxi-driver"
    
    # Tạo thư mục local để lưu file
    project_root = Path(__file__).parent.parent
    local_dir = project_root / "data" / "raw" / "2025"
    local_dir.mkdir(parents=True, exist_ok=True)
    
    # Kết nối MinIO
    s3_client = boto3.client(
        's3',
        endpoint_url=minio_endpoint,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY
    )
    
    base_url = "https://d37ci6vzurychx.cloudfront.net/trip-data"
    months = range(1, 11)  # Tháng 1-10
    
    for month in months:
        month_str = f"{month:02d}"
        filename = f"green_tripdata_2025-{month_str}.parquet"
        url = f"{base_url}/{filename}"
        local_path = local_dir / filename
        s3_key = f"raw/green/2025/{filename}"
        
        # Download về local
        if local_path.exists():
            print(f"⏭ File đã tồn tại local: {filename}")
        else:
            print(f"📥 Đang download: {filename}")
            try:
                response = requests.get(url, stream=True)
                response.raise_for_status()
                
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"✓ Đã download: {local_path}")
            except requests.exceptions.RequestException as e:
                print(f"✗ Lỗi download {filename}: {e}")
                continue
        
        # Upload lên MinIO
        print(f"📤 Đang upload: {filename}")
        try:
            s3_client.upload_file(
                str(local_path),
                bucket_name,
                s3_key
            )
            print(f"✓ Đã upload: {s3_key}")
        except Exception as e:
            print(f"✗ Lỗi upload {filename}: {e}")
    
    print("Hoàn thành download và upload Green Taxi data!")

if __name__ == "__main__":
    download_green_taxi_data()

