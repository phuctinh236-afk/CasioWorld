from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from server import app as game_app
from ai import app as ai_app
from tool import app as tool_app

combined = Flask(__name__)

combined.wsgi_app = DispatcherMiddleware(
    game_app,              # /        → server.py (game)
    {
        '/ai': ai_app,     # /ai      → ai.py
        '/tool': tool_app  # /tool    → tool.py
    }
)

if __name__ == "__main__":
    combined.run(host="0.0.0.0", port=5000, debug=True)
