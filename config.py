import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'mega_casino_world_vip_secret_key'
    # Các cấu hình database (SQLite/PostgreSQL) sẽ thêm ở đây sau
  
