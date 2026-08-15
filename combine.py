from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from server import app as game_app
from ai import app as ai_app

combined = Flask(__name__)

combined.wsgi_app = DispatcherMiddleware(
    game_app,      # /  → game (server.py)
    {
        '/ai': ai_app  # /ai → AI VIP (ai.py)
    }
)
