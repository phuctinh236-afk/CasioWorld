from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from server import app as game_app
from ai import app as ai_app

# Tạo app Flask gốc
combined = Flask(__name__)

# Gắn app game vào root (/) và app AI vào (/ai)
combined.wsgi_app = DispatcherMiddleware(
    game_app,  # Mặc định truy cập / sẽ vào app game
    {
        '/ai': ai_app  # Truy cập /ai sẽ vào app AI
    }
)

if __name__ == '__main__':
    combined.run(host='0.0.0.0', port=5000)
    
