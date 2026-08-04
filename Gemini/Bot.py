import os
from dotenv import load_dotenv  # <-- Đây là đoạn "import thư viện dotenv"

# Đọc dữ liệu từ file .env nằm cùng thư mục
load_dotenv()

# Tự động lấy giá trị từ file .env bỏ vào biến
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Sau đó chạy code bình thường bên dưới...
