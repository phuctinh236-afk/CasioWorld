# ============================================
# Tạo file combine.py để gộp cả hai app
# ============================================
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from server import app as game_app   # Import app từ server.py
from ai import app as ai_app         # Import app từ ai.py
from flask import Flask

# Tạo app chính
combined = Flask(__name__)

# Gắn hai app con vào các đường dẫn riêng
combined.wsgi_app = DispatcherMiddleware(
    combined.wsgi_app,
    {
        '/game': game_app,  # Truy cập game tại /game
        '/ai': ai_app,      # Truy cập AI VIP tại /ai
    }
)

# ============================================
# Cấu hình Render:
# Start Command: gunicorn combine:combined
# ============================================
