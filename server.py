# ============================================================
# TX68 GAME - server.py
# Game points / FC ảo — dùng CHUNG một balance
# (game + mini-game + admin + nạp/rút)
# ============================================================

from flask import Flask, request, jsonify, session, redirect, render_template, render_template_string
import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)

# Đổi SECRET_KEY khi đưa lên server thật.
app.secret_key = os.environ.get("SECRET_KEY", "tx68-dev-secret-change-me")

DB_PATH = os.environ.get("DB_PATH", "tx68.db")


# ============================================================
# DATABASE
# ============================================================

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            balance INTEGER NOT NULL DEFAULT 1000,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            game_name TEXT NOT NULL,
            bet_amount INTEGER NOT NULL DEFAULT 0,
            win_amount INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'info',
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()

    # Tạo / cập nhật tài khoản owner mặc định.
    owner_username = os.environ.get("OWNER_USERNAME", "pphuc8386")
    owner_password = os.environ.get("OWNER_PASSWORD", "Mmmmmm@6")

    # Nếu còn account cũ tên "owner" thì đổi sang tên mới
    old_owner = conn.execute(
        "SELECT id FROM users WHERE username = 'owner' AND role = 'owner'"
    ).fetchone()
    if old_owner:
        # Chỉ đổi nếu tên mới chưa tồn tại
        taken = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (owner_username,)
        ).fetchone()
        if not taken:
            conn.execute(
                "UPDATE users SET username = ?, password_hash = ? WHERE id = ?",
                (owner_username, hash_password(owner_password), old_owner["id"])
            )
            conn.commit()

    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?",
        (owner_username,)
    ).fetchone()

    if not existing:
        conn.execute(
            """
            INSERT INTO users
            (username, password_hash, role, balance, created_at)
            VALUES (?, ?, 'owner', 100000, ?)
            """,
            (
                owner_username,
                hash_password(owner_password),
                now(),
            )
        )
        conn.commit()
    else:
        # Cập nhật mật khẩu owner về đúng mật khẩu mới
        conn.execute(
            "UPDATE users SET password_hash = ?, role = 'owner' WHERE username = ?",
            (hash_password(owner_password), owner_username)
        )
        conn.commit()

    conn.close()


# ============================================================
# HELPERS
# ============================================================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def valid_username(username):
    if not username:
        return False
    if len(username) < 3 or len(username) > 32:
        return False
    return username.replace("_", "").isalnum()


def get_current_user():
    username = session.get("username")
    if not username:
        return None

    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, username, role, balance, created_at FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    conn.close()
    return user


def require_login_api():
    user = get_current_user()
    if not user:
        return None, (jsonify({"message": "Chưa đăng nhập"}), 401)
    return user, None


def admin_required_api():
    user = get_current_user()

    if not user:
        return None, (jsonify({"message": "Chưa đăng nhập"}), 401)

    if user["role"] not in ("owner", "admin"):
        return None, (jsonify({"message": "Không có quyền"}), 403)

    return user, None


def admin_required_page(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()

        if not user:
            return redirect("/admin/login")

        if user["role"] not in ("owner", "admin"):
            return """
            <!DOCTYPE html>
            <html lang="vi">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport"
                      content="width=device-width, initial-scale=1.0">
                <title>Không có quyền</title>
                <style>
                    body {
                        margin: 0;
                        background: #0b1120;
                        color: white;
                        font-family: Arial, sans-serif;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        min-height: 100vh;
                        text-align: center;
                    }
                    .box {
                        background: #172136;
                        padding: 35px;
                        border-radius: 12px;
                        width: 90%;
                        max-width: 400px;
                    }
                    a {
                        display: inline-block;
                        margin-top: 15px;
                        padding: 10px 20px;
                        background: #f3a838;
                        color: #000;
                        text-decoration: none;
                        border-radius: 6px;
                        font-weight: bold;
                    }
                </style>
            </head>
            <body>
                <div class="box">
                    <h2>🚫 Không có quyền truy cập</h2>
                    <p>Tài khoản này không phải Admin/Owner.</p>
                    <a href="/admin/login">Đăng nhập Admin</a>
                </div>
            </body>
            </html>
            """, 403

        return fn(*args, **kwargs)

    return wrapper


def add_log(username, game_name, bet_amount=0, win_amount=0, status="info"):
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO game_logs
        (username, game_name, bet_amount, win_amount, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            username,
            game_name,
            int(bet_amount),
            int(win_amount),
            status,
            now(),
        )
    )
    conn.commit()
    conn.close()


# ============================================================
# AUTH - REGISTER
# ============================================================

REGISTER_HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>TX68 - Đăng ký</title>
<style>
*{box-sizing:border-box;font-family:Arial,sans-serif}
body{
    margin:0;background:#0b1120;color:#fff;
    min-height:100vh;display:flex;
    align-items:center;justify-content:center;
}
.box{
    width:92%;max-width:420px;background:#131c2e;
    border:1px solid #263653;border-radius:14px;padding:25px;
}
h1{text-align:center;color:#f3a838}
input{
    width:100%;padding:12px;margin:7px 0;
    background:#0b1120;color:#fff;
    border:1px solid #334155;border-radius:7px;
}
button{
    width:100%;padding:12px;margin-top:10px;
    border:0;border-radius:7px;background:#f3a838;
    font-weight:bold;cursor:pointer;
}
a{color:#38bdf8}
.error{color:#fb7185;margin:10px 0}
</style>
</head>
<body>
<div class="box">
<h1>🎮 TX68</h1>
<h2>Đăng ký</h2>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
<form method="post">
<input name="username" placeholder="Tên tài khoản" required>
<input name="password" type="password" placeholder="Mật khẩu" required>
<input name="confirm" type="password" placeholder="Nhập lại mật khẩu" required>
<button type="submit">ĐĂNG KÝ</button>
</form>
<p>Đã có tài khoản? <a href="/login">Đăng nhập</a></p>
</div>
</body>
</html>
"""


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template_string(REGISTER_HTML, error=None)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm", "")

    if not valid_username(username):
        return render_template_string(
            REGISTER_HTML,
            error="Tên tài khoản 3-32 ký tự, chỉ gồm chữ/số/_."
        )

    if len(password) < 6:
        return render_template_string(
            REGISTER_HTML,
            error="Mật khẩu phải có ít nhất 6 ký tự."
        )

    if password != confirm:
        return render_template_string(
            REGISTER_HTML,
            error="Mật khẩu nhập lại không khớp."
        )

    conn = get_db_connection()

    try:
        conn.execute(
            """
            INSERT INTO users
            (username, password_hash, role, balance, created_at)
            VALUES (?, ?, 'user', 1000, ?)
            """,
            (
                username,
                hash_password(password),
                now(),
            )
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return render_template_string(
            REGISTER_HTML,
            error="Tên tài khoản đã tồn tại."
        )

    conn.close()

    return redirect("/login")


# ============================================================
# AUTH - LOGIN
# ============================================================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>TX68 - Đăng nhập</title>
<style>
*{box-sizing:border-box;font-family:Arial,sans-serif}
body{
    margin:0;background:#0b1120;color:#fff;
    min-height:100vh;display:flex;
    align-items:center;justify-content:center;
}
.box{
    width:92%;max-width:420px;background:#131c2e;
    border:1px solid #263653;border-radius:14px;padding:25px;
}
h1{text-align:center;color:#f3a838}
input{
    width:100%;padding:12px;margin:7px 0;
    background:#0b1120;color:#fff;
    border:1px solid #334155;border-radius:7px;
}
button{
    width:100%;padding:12px;margin-top:10px;
    border:0;border-radius:7px;background:#f3a838;
    font-weight:bold;cursor:pointer;
}
a{color:#38bdf8}
.error{color:#fb7185;margin:10px 0}
</style>
</head>
<body>
<div class="box">
<h1>🎮 TX68</h1>
<h2>Đăng nhập</h2>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
<form method="post">
<input name="username" placeholder="Tên tài khoản" required>
<input name="password" type="password" placeholder="Mật khẩu" required>
<button type="submit">ĐĂNG NHẬP</button>
</form>
<p>Chưa có tài khoản? <a href="/register">Đăng ký</a></p>
</div>
</body>
</html>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        try:
            return render_template("login.html", error=None)
        except Exception:
            return render_template_string(LOGIN_HTML, error=None)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    conn = get_db_connection()
    user = conn.execute(
        """
        SELECT id, username, password_hash, role
        FROM users
        WHERE username = ?
        """,
        (username,)
    ).fetchone()
    conn.close()

    if not user or user["password_hash"] != hash_password(password):
        try:
            return render_template("login.html", error="Sai tài khoản hoặc mật khẩu.")
        except Exception:
            return render_template_string(
                LOGIN_HTML,
                error="Sai tài khoản hoặc mật khẩu."
            )

    session.clear()
    session["username"] = user["username"]

    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ============================================================
# HOME
# ============================================================

HOME_HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>TX68 Game</title>
<style>
*{box-sizing:border-box;font-family:Arial,sans-serif}
body{margin:0;background:#0b1120;color:#fff}
.header{
    padding:15px 20px;background:#131c2e;
    border-bottom:1px solid #263653;
    display:flex;justify-content:space-between;gap:15px;
}
.logo{color:#f3a838;font-weight:bold;font-size:20px}
a{color:#38bdf8;text-decoration:none}
.container{max-width:1000px;margin:auto;padding:20px}
.card{
    background:#131c2e;border:1px solid #263653;
    border-radius:12px;padding:20px;margin-bottom:15px;
}
.balance{font-size:28px;color:#f3a838;font-weight:bold}
.games{
    display:grid;grid-template-columns:repeat(3,1fr);
    gap:15px;
}
.game{
    padding:25px;background:#172136;
    border:1px solid #263653;border-radius:10px;
    text-align:center;
}
.btn{
    display:inline-block;margin-top:12px;padding:9px 15px;
    background:#f3a838;color:#000;border-radius:7px;
    font-weight:bold;
}
@media(max-width:700px){.games{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="header">
<div class="logo">🎮 TX68 GAME</div>
<div>
👤 {{ user["username"] }}
|
<a href="/logout">Đăng xuất</a>
</div>
</div>
<div class="container">
<div class="card">
<h2>Xin chào {{ user["username"] }} 👋</h2>
<p>FC hiện tại:</p>
<div class="balance">🪙 {{ "{:,}".format(user["balance"]) }} FC</div>
</div>

<div class="card">
<h2>🎮 Khu trò chơi</h2>
<div class="games">
<div class="game">
<h3>🎯 Điểm số</h3>
<p>Trò chơi điểm ảo.</p>
<a class="btn" href="/game">Chơi</a>
</div>
<div class="game">
<h3>👤 Hồ sơ</h3>
<p>Xem tài khoản.</p>
<a class="btn" href="/profile">Hồ sơ</a>
</div>
{% if user["role"] in ("owner","admin") %}
<div class="game">
<h3>⚙️ Admin</h3>
<p>Quản lý người chơi.</p>
<a class="btn" href="/admin">Mở Admin</a>
</div>
{% endif %}
</div>
</div>
</div>
</body>
</html>
"""


@app.route("/")
def index():
    user = get_current_user()
    if not user:
        return redirect("/login")
    return render_template("index.html", user=user)


@app.route("/home")
def home():
    return redirect("/")


# ============================================================
# FULL GAMES (Mahjong, Super Ace, ...)
# Thay mini-game bằng các trang game đầy đủ trong templates/
# ============================================================

@app.route("/mahjong")
def mahjong():
    user = get_current_user()
    if not user:
        return redirect("/login")
    return render_template(
        "mahjong.html",
        user=user,
        balance=user["balance"] if user else 0,
    )


@app.route("/mahjong-ways-2")
@app.route("/mahjong_ways_2")
def mahjong_ways_2():
    user = get_current_user()
    if not user:
        return redirect("/login")
    return render_template(
        "mahjong_ways_2.html",
        user=user,
        balance=user["balance"] if user else 0,
    )


@app.route("/super-ace")
@app.route("/super_ace")
def super_ace():
    user = get_current_user()
    if not user:
        return redirect("/login")
    return render_template(
        "super_ace.html",
        user=user,
        balance=user["balance"] if user else 0,
    )


@app.route("/play")
@app.route("/play_game")
def play_game():
    """Cac game khac trong index tro ve day — mo Mahjong Ways."""
    user = get_current_user()
    if not user:
        return redirect("/login")
    return render_template(
        "mahjong.html",
        user=user,
        balance=user["balance"] if user else 0,
    )


@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    user = get_current_user()
    if not user:
        return redirect("/login")

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        try:
            amount = int(float(request.form.get("amount") or 0))
        except (TypeError, ValueError):
            amount = 0

        if amount <= 0:
            return render_template(
                "deposit.html",
                user=user,
                error="Số tiền không hợp lệ."
            )

        # Giới hạn demo
        if amount > 50_000_000:
            return render_template(
                "deposit.html",
                user=user,
                error="Mỗi lần tối đa 50.000.000."
            )

        conn = get_db_connection()
        row = conn.execute(
            "SELECT balance FROM users WHERE id = ?",
            (user["id"],)
        ).fetchone()

        if not row:
            conn.close()
            return redirect("/login")

        old_balance = int(row["balance"] or 0)

        if action == "deposit":
            new_balance = old_balance + amount
            conn.execute(
                "UPDATE users SET balance = ? WHERE id = ?",
                (new_balance, user["id"])
            )
            conn.commit()
            conn.close()
            add_log(
                user["username"],
                "NẠP TIỀN",
                bet_amount=0,
                win_amount=amount,
                status="deposit"
            )
            user = get_current_user()
            return render_template(
                "deposit.html",
                user=user,
                success=f"Nạp thành công +{amount:,}. Số dư: {new_balance:,}"
            )

        if action == "withdraw":
            if amount > old_balance:
                conn.close()
                return render_template(
                    "deposit.html",
                    user=user,
                    error=f"Không đủ số dư. Hiện có: {old_balance:,}"
                )
            new_balance = old_balance - amount
            conn.execute(
                "UPDATE users SET balance = ? WHERE id = ?",
                (new_balance, user["id"])
            )
            conn.commit()
            conn.close()
            add_log(
                user["username"],
                "RÚT TIỀN",
                bet_amount=amount,
                win_amount=0,
                status="withdraw"
            )
            user = get_current_user()
            return render_template(
                "deposit.html",
                user=user,
                success=f"Rút thành công -{amount:,}. Số dư: {new_balance:,}"
            )

        conn.close()
        return render_template(
            "deposit.html",
            user=user,
            error="Hành động không hợp lệ."
        )

    return render_template("deposit.html", user=user)


@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():
    # Dùng chung trang & logic với /deposit
    return deposit()


@app.route("/promotions")
def promotions():
    user = get_current_user()
    if not user:
        return redirect("/login")
    return render_template("promotions.html", user=user)


@app.route("/cskh")
def cskh():
    user = get_current_user()
    if not user:
        return redirect("/login")
    return render_template("cskh.html", user=user)


@app.route("/vip")
def vip():
    user = get_current_user()
    if not user:
        return redirect("/login")
    return render_template("vip.html", user=user)


@app.route("/vip-details")
@app.route("/vip_details")
def vip_details():
    user = get_current_user()
    if not user:
        return redirect("/login")
    return render_template("vip_details.html", user=user)


@app.route("/mailbox")
def mailbox():
    user = get_current_user()
    if not user:
        return redirect("/login")
    return render_template("mailbox.html", user=user)


@app.route("/payment")
def payment():
    user = get_current_user()
    if not user:
        return redirect("/login")
    return render_template("payment.html", user=user)


# ============================================================
# PROFILE
# ============================================================

@app.route("/profile")
def profile():
    user = get_current_user()

    if not user:
        return redirect("/login")

    try:
        return render_template(
            "profile.html",
            user=user,
            username=user["username"],
            balance=user["balance"],
        )
    except Exception:
        return render_template_string("""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>Hồ sơ</title>
    <style>
    body{margin:0;background:#0b1120;color:#fff;font-family:Arial}
    .box{max-width:600px;margin:40px auto;padding:25px;
         background:#131c2e;border:1px solid #263653;border-radius:12px}
    .row{padding:12px 0;border-bottom:1px solid #263653}
    a{color:#38bdf8}
    </style>
    </head>
    <body>
    <div class="box">
    <h2>👤 Hồ sơ</h2>
    <div class="row">ID: #{{ user["id"] }}</div>
    <div class="row">Tài khoản: <b>{{ user["username"] }}</b></div>
    <div class="row">Quyền: {{ user["role"] }}</div>
    <div class="row">FC: 🪙 {{ "{:,}".format(user["balance"]) }}</div>
    <div class="row">Tạo lúc: {{ user["created_at"] }}</div>
    <p><a href="/">← Về trang chủ</a></p>
    </div>
    </body>
    </html>
    """, user=user)


# ============================================================
# SIMPLE GAME
# Chỉ là điểm game ảo, không tiền thật.
# ============================================================

@app.route("/game")
def game_page():
    """Redirect mini-game cu sang game Mahjong day du."""
    user = get_current_user()
    if not user:
        return redirect("/login")
    return redirect("/mahjong")


@app.route("/api/game/play", methods=["POST"])
def game_play():
    """Trừ tiền cược từ balance chung."""
    user, error = require_login_api()

    if error:
        return error

    data = request.get_json(silent=True) or {}

    try:
        amount = int(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"message": "Số FC không hợp lệ"}), 400

    if amount <= 0:
        return jsonify({"message": "Số FC phải lớn hơn 0"}), 400

    if amount > 10_000_000:
        return jsonify({"message": "Tối đa 10.000.000 mỗi lượt"}), 400

    game_name = str(data.get("game") or "Game").strip()[:50]

    conn = get_db_connection()

    current = conn.execute(
        "SELECT balance FROM users WHERE id = ?",
        (user["id"],)
    ).fetchone()

    if not current or current["balance"] < amount:
        conn.close()
        return jsonify({"message": "Không đủ số dư", "balance": current["balance"] if current else 0}), 400

    new_balance = int(current["balance"]) - amount

    conn.execute(
        "UPDATE users SET balance = ? WHERE id = ?",
        (new_balance, user["id"])
    )
    conn.commit()
    conn.close()

    add_log(
        user["username"],
        game_name,
        bet_amount=amount,
        win_amount=0,
        status="bet"
    )

    return jsonify({
        "success": True,
        "message": f"Đã cược {amount:,}.",
        "balance": new_balance
    })


@app.route("/api/game/win", methods=["POST"])
def game_win():
    """Cộng tiền thắng vào balance chung."""
    user, error = require_login_api()

    if error:
        return error

    data = request.get_json(silent=True) or {}

    try:
        amount = int(data.get("amount") or 0)
    except (TypeError, ValueError):
        return jsonify({"message": "Số tiền không hợp lệ"}), 400

    if amount < 0:
        return jsonify({"message": "Số tiền không hợp lệ"}), 400

    if amount > 50_000_000:
        return jsonify({"message": "Số tiền quá lớn"}), 400

    game_name = str(data.get("game") or "Game").strip()[:50]

    conn = get_db_connection()

    current = conn.execute(
        "SELECT balance FROM users WHERE id = ?",
        (user["id"],)
    ).fetchone()

    if not current:
        conn.close()
        return jsonify({"message": "Không tìm thấy tài khoản"}), 404

    new_balance = int(current["balance"] or 0) + amount

    conn.execute(
        "UPDATE users SET balance = ? WHERE id = ?",
        (new_balance, user["id"])
    )
    conn.commit()
    conn.close()

    if amount > 0:
        add_log(
            user["username"],
            game_name,
            bet_amount=0,
            win_amount=amount,
            status="win"
        )

    return jsonify({
        "success": True,
        "message": f"Thắng +{amount:,}." if amount else "Hòa.",
        "balance": new_balance
    })


@app.route("/api/balance", methods=["GET"])
def api_balance():
    """Lấy số dư hiện tại (dùng chung cho mọi game)."""
    user, error = require_login_api()
    if error:
        return error
    return jsonify({
        "success": True,
        "balance": int(user["balance"] or 0),
        "username": user["username"]
    })


# ============================================================
# ADMIN PANEL
# ============================================================

ADMIN_HTML = r"""
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>TX68 - Admin</title>
<style>
*{
    box-sizing:border-box;
    margin:0;
    padding:0;
    font-family:Arial,sans-serif;
}
body{
    background:#0b1120;
    color:#fff;
}
.header{
    background:#131c2e;
    border-bottom:1px solid #263653;
    padding:15px 20px;
    display:flex;
    justify-content:space-between;
    align-items:center;
}
.logo{
    color:#f3a838;
    font-size:20px;
    font-weight:bold;
}
.admin-user{
    color:#94a3b8;
    font-size:13px;
}
.container{
    padding:20px;
    max-width:1400px;
    margin:auto;
}
.stats{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:15px;
    margin-bottom:20px;
}
.stat{
    background:#131c2e;
    border:1px solid #263653;
    border-radius:10px;
    padding:20px;
}
.stat-title{
    color:#94a3b8;
    font-size:13px;
    margin-bottom:8px;
}
.stat-value{
    font-size:25px;
    font-weight:bold;
    color:#f3a838;
}
.card{
    background:#131c2e;
    border:1px solid #263653;
    border-radius:10px;
    padding:18px;
    margin-bottom:20px;
}
.card h2{
    font-size:16px;
    color:#38bdf8;
    margin-bottom:15px;
}
.search{
    width:100%;
    padding:11px;
    margin-bottom:15px;
    background:#0b1120;
    border:1px solid #334155;
    border-radius:6px;
    color:white;
    outline:none;
}
table{
    width:100%;
    border-collapse:collapse;
    font-size:13px;
}
th{
    background:#172136;
    color:#94a3b8;
    text-align:left;
}
th,td{
    padding:11px;
    border-bottom:1px solid #263653;
}
.fc{
    color:#f3a838;
    font-weight:bold;
}
.badge{
    display:inline-block;
    padding:4px 8px;
    border-radius:5px;
    font-size:11px;
    font-weight:bold;
}
.badge-admin{
    background:rgba(168,85,247,.2);
    color:#c084fc;
}
.badge-user{
    background:rgba(56,189,248,.15);
    color:#38bdf8;
}
.badge-owner{
    background: linear-gradient(90deg, #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3, #ff0000);
    background-size: 300% 100%;
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    animation: rainbowMove 3s linear infinite;
    font-weight: bold;
    font-size: 12px;
    letter-spacing: 0.5px;
}
@keyframes rainbowMove {
    0% { background-position: 0% 50%; }
    100% { background-position: 300% 50%; }
}
.btn{
    border:none;
    border-radius:5px;
    padding:6px 10px;
    cursor:pointer;
    font-weight:bold;
}
.btn-add{
    background:#22c55e;
    color:#000;
}
.btn-sub{
    background:#ef4444;
    color:#fff;
}
.btn-role{
    background:#38bdf8;
    color:#000;
}
.input-small{
    width:100px;
    padding:7px;
    background:#0b1120;
    color:white;
    border:1px solid #334155;
    border-radius:5px;
}
@media(max-width:700px){
    .stats{grid-template-columns:1fr}
    .container{padding:10px;overflow-x:auto}
    table{min-width:800px}
}
</style>
</head>
<body>

<div class="header">
    <div class="logo">🎮 TX68 GAME ADMIN</div>
    <div class="admin-user">
        👤 {{ username }}
        {% if role == 'owner' %}
        <span class="badge-owner">OWNER</span>
        {% else %}
        <span class="badge badge-admin">{{ role|upper }}</span>
        {% endif %}
        &nbsp; <a href="/logout">Đăng xuất</a>
    </div>
</div>

<div class="container">

<div style="display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap;">
    <a href="/" target="_blank" style="background:#22c55e;color:#000;border:0;padding:10px 16px;border-radius:7px;text-decoration:none;font-weight:bold;font-size:13px;">🎮 Mở Game</a>
    <button onclick="createAdminAccount()" style="background:#a855f7;color:#fff;border:0;padding:10px 16px;border-radius:7px;cursor:pointer;font-weight:bold;font-size:13px;">➕ Tạo TK Admin</button>
    <a href="/deposit" target="_blank" style="background:#1e293b;color:#fff;border:1px solid #334155;padding:10px 16px;border-radius:7px;text-decoration:none;font-weight:bold;font-size:13px;">💳 Nạp / Rút</a>
</div>

<div class="stats">
    <div class="stat">
        <div class="stat-title">👥 Tổng người chơi</div>
        <div class="stat-value" id="total-users">0</div>
    </div>
    <div class="stat">
        <div class="stat-title">🟢 Đang hoạt động</div>
        <div class="stat-value" id="active-users">0</div>
    </div>
    <div class="stat">
        <div class="stat-title">🪙 Tổng FC</div>
        <div class="stat-value" id="total-fc">0</div>
    </div>
</div>

<div class="card">
<h2>👥 QUẢN LÝ NGƯỜI CHƠI</h2>

<input class="search" id="search"
placeholder="🔎 Tìm tài khoản..."
oninput="filterUsers()">

<div style="overflow-x:auto">
<table>
<thead>
<tr>
<th>ID</th>
<th>Tài khoản</th>
<th>FC</th>
<th>Quyền</th>
<th>Thay đổi FC</th>
<th>Quyền</th>
</tr>
</thead>
<tbody id="users">
<tr><td colspan="6" style="text-align:center">Đang tải...</td></tr>
</tbody>
</table>
</div>
</div>

<div class="card">
<h2>📜 LỊCH SỬ HOẠT ĐỘNG</h2>
<div style="overflow-x:auto">
<table>
<thead>
<tr>
<th>Thời gian</th>
<th>Tài khoản</th>
<th>Hoạt động</th>
<th>FC chơi</th>
<th>FC nhận</th>
<th>Trạng thái</th>
</tr>
</thead>
<tbody id="logs">
<tr><td colspan="6" style="text-align:center">Đang tải...</td></tr>
</tbody>
</table>
</div>
</div>

</div>

<script>
let allUsers=[];

async function loadUsers(){
    try{
        const res=await fetch('/admin/api/users');
        if(!res.ok) throw new Error('API error');

        const data=await res.json();

        allUsers=data.users||[];

        document.getElementById('total-users').textContent =
            data.total_users||0;

        document.getElementById('active-users').textContent =
            data.active_users||0;

        document.getElementById('total-fc').textContent =
            Number(data.total_fc||0).toLocaleString();

        renderUsers(allUsers);
    }catch(e){
        document.getElementById('users').innerHTML =
            '<tr><td colspan="6">Không thể tải dữ liệu.</td></tr>';
    }
}

function renderUsers(users){
    let html='';

    if(!users.length){
        html='<tr><td colspan="6" style="text-align:center">Không có người chơi.</td></tr>';
    }else{
        users.forEach(u=>{
            let roleBadge;
            if (u.role === 'owner') {
                roleBadge = '<span class="badge-owner">OWNER</span>';
            } else if (u.role === 'admin') {
                roleBadge = '<span class="badge badge-admin">ADMIN</span>';
            } else {
                roleBadge = '<span class="badge badge-user">USER</span>';
            }

            // Không hiện nút đổi quyền cho owner
            const roleBtn = u.role === 'owner'
                ? '<span style="color:#64748b;font-size:12px;">—</span>'
                : `<button class="btn btn-role" onclick="changeRole(${u.id})">Đổi quyền</button>`;

            html+=`
            <tr>
                <td>#${u.id}</td>
                <td><b>${escapeHtml(u.username)}</b></td>
                <td class="fc">
                    🪙 ${Number(u.fc||0).toLocaleString()}
                </td>
                <td>${roleBadge}</td>
                <td>
                    <input id="amount-${u.id}"
                           type="number"
                           class="input-small"
                           placeholder="FC"
                           min="1">
                    <button class="btn btn-add"
                            onclick="modifyFC(${u.id},1)">+</button>
                    <button class="btn btn-sub"
                            onclick="modifyFC(${u.id},-1)">-</button>
                </td>
                <td>${roleBtn}</td>
            </tr>`;
        });
    }

    document.getElementById('users').innerHTML=html;
}

function filterUsers(){
    const q=document.getElementById('search')
        .value.toLowerCase().trim();

    const filtered=allUsers.filter(u=>
        String(u.username).toLowerCase().includes(q)
    );

    renderUsers(filtered);
}

async function modifyFC(id,direction){
    const input=document.getElementById('amount-'+id);
    const amount=Number(input.value);

    if(!amount || amount<=0){
        alert('Nhập số FC hợp lệ!');
        return;
    }

    const finalAmount=amount*direction;

    try{
        const res=await fetch('/admin/api/user/fc',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({
                user_id:id,
                amount:finalAmount
            })
        });

        const data=await res.json();

        alert(data.message||'Đã cập nhật.');

        if(res.ok){
            input.value='';
            loadUsers();
            loadLogs();
        }
    }catch(e){
        alert('Không thể kết nối máy chủ.');
    }
}

async function changeRole(id){
    const role=prompt(
        'Nhập quyền mới: user / admin'
    );

    if(!role) return;

    if(!['user','admin'].includes(role)){
        alert('Quyền không hợp lệ.');
        return;
    }

    const res=await fetch('/admin/api/user/role',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
            user_id:id,
            role:role
        })
    });

    const data=await res.json();
    alert(data.message||'Hoàn tất');

    if(res.ok) loadUsers();
}

async function createAdminAccount(){
    const username=prompt('Tên tài khoản Admin mới:');
    if(!username) return;

    const password=prompt('Mật khẩu (tối thiểu 4 ký tự):');
    if(!password) return;

    const balStr=prompt('Số dư ban đầu (mặc định 10000):','10000');
    let balance=10000;
    if(balStr!==null && balStr!==''){
        balance=parseInt(balStr,10)||0;
    }

    try{
        const res=await fetch('/admin/api/create-admin',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({
                username:username.trim(),
                password:password,
                balance:balance
            })
        });
        const data=await res.json();
        alert(data.message||'Hoàn tất');
        if(res.ok) loadUsers();
    }catch(e){
        alert('Không thể kết nối máy chủ.');
    }
}

async function loadLogs(){
    try{
        const res=await fetch('/admin/api/logs');
        const data=await res.json();

        let html='';

        if(!data.length){
            html='<tr><td colspan="6" style="text-align:center">Chưa có lịch sử.</td></tr>';
        }else{
            data.forEach(item=>{
                html+=`
                <tr>
                    <td>${escapeHtml(item.created_at||'')}</td>
                    <td><b>${escapeHtml(item.username||'')}</b></td>
                    <td>${escapeHtml(item.action||'')}</td>
                    <td>${Number(item.bet_amount||0).toLocaleString()}</td>
                    <td class="fc">${Number(item.win_amount||0).toLocaleString()}</td>
                    <td>${escapeHtml(item.status||'')}</td>
                </tr>`;
            });
        }

        document.getElementById('logs').innerHTML=html;
    }catch(e){
        document.getElementById('logs').innerHTML =
            '<tr><td colspan="6">Không tải được lịch sử.</td></tr>';
    }
}

function escapeHtml(value){
    return String(value)
        .replaceAll('&','&amp;')
        .replaceAll('<','&lt;')
        .replaceAll('>','&gt;')
        .replaceAll('"','&quot;')
        .replaceAll("'","&#039;");
}

loadUsers();
loadLogs();

setInterval(()=>{
    loadUsers();
    loadLogs();
},10000);
</script>

</body>
</html>
"""


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Trang đăng nhập riêng cho Admin/Owner."""
    # Đã login sẵn và đúng quyền thì vào thẳng admin
    user = get_current_user()
    if user and user["role"] in ("owner", "admin"):
        return redirect("/admin")

    if request.method == "GET":
        return render_template("admin_login.html")

    # POST (JSON từ form admin_login.html)
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")

    if not username or not password:
        return jsonify({"message": "Vui lòng nhập tài khoản và mật khẩu."}), 400

    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT id, username, password_hash, role
        FROM users
        WHERE username = ?
        """,
        (username,)
    ).fetchone()
    conn.close()

    if not row or row["password_hash"] != hash_password(password):
        return jsonify({"message": "Sai tài khoản hoặc mật khẩu."}), 401

    if row["role"] not in ("owner", "admin"):
        return jsonify({"message": "Tài khoản này không có quyền Admin."}), 403

    session.clear()
    session["username"] = row["username"]

    return jsonify({
        "success": True,
        "message": "Đăng nhập thành công.",
        "redirect": "/admin"
    })


@app.route("/admin")
@app.route("/admin/dashboard")
@admin_required_page
def admin_panel():
    user = get_current_user()

    return render_template_string(
        ADMIN_HTML,
        username=user["username"],
        role=user["role"]
    )


# ============================================================
# ADMIN API - USERS
# ============================================================

@app.route("/admin/api/users")
def admin_api_users():
    admin, error = admin_required_api()

    if error:
        return error

    conn = get_db_connection()

    rows = conn.execute("""
        SELECT id, username, balance, role, created_at
        FROM users
        ORDER BY id DESC
        LIMIT 200
    """).fetchall()

    total_users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    total_fc = conn.execute(
        "SELECT COALESCE(SUM(balance), 0) FROM users"
    ).fetchone()[0]

    conn.close()

    users = []

    for row in rows:
        users.append({
            "id": row["id"],
            "username": row["username"],
            "fc": row["balance"] or 0,
            "role": row["role"] or "user",
            "created_at": row["created_at"] or ""
        })

    return jsonify({
        "users": users,
        "total_users": total_users,
        "active_users": 0,
        "total_fc": total_fc
    })


# ============================================================
# ADMIN API - MODIFY FC
# ============================================================

@app.route("/admin/api/user/fc", methods=["POST"])
def admin_api_modify_fc():
    admin, error = admin_required_api()

    if error:
        return error

    data = request.get_json(silent=True) or {}

    try:
        user_id = int(data.get("user_id"))
        amount = int(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify({
            "message": "Dữ liệu không hợp lệ"
        }), 400

    if amount == 0:
        return jsonify({
            "message": "Số FC phải khác 0"
        }), 400

    if abs(amount) > 10_000_000:
        return jsonify({
            "message": "Mỗi lần chỉ được thay đổi tối đa 10.000.000 FC"
        }), 400

    conn = get_db_connection()

    user = conn.execute(
        """
        SELECT id, username, balance, role
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()
        return jsonify({
            "message": "Không tìm thấy tài khoản"
        }), 404

    # Không cho admin tự đổi FC của owner.
    if user["role"] == "owner" and admin["role"] != "owner":
        conn.close()
        return jsonify({
            "message": "Admin không thể thay đổi FC của Owner"
        }), 403

    old_balance = int(user["balance"] or 0)
    new_balance = old_balance + amount

    if new_balance < 0:
        conn.close()
        return jsonify({
            "message": "Không thể để FC âm"
        }), 400

    conn.execute(
        "UPDATE users SET balance = ? WHERE id = ?",
        (new_balance, user_id)
    )

    conn.commit()
    conn.close()

    add_log(
        admin["username"],
        "ADMIN FC",
        bet_amount=0,
        win_amount=amount,
        status=f"Đã {'cộng' if amount > 0 else 'trừ'} FC cho {user['username']}"
    )

    return jsonify({
        "success": True,
        "message": (
            f"Đã {'cộng' if amount > 0 else 'trừ'} "
            f"{abs(amount):,} FC cho {user['username']}."
        ),
        "old_balance": old_balance,
        "new_balance": new_balance
    })


# ============================================================
# ADMIN API - ROLE
# ============================================================

@app.route("/admin/api/user/role", methods=["POST"])
def admin_api_modify_role():
    admin, error = admin_required_api()

    if error:
        return error

    # Chỉ owner được đổi quyền.
    if admin["role"] != "owner":
        return jsonify({
            "message": "Chỉ Owner mới được đổi quyền."
        }), 403

    data = request.get_json(silent=True) or {}

    try:
        user_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        return jsonify({
            "message": "ID không hợp lệ"
        }), 400

    role = str(data.get("role", "")).lower().strip()

    if role not in ("user", "admin"):
        return jsonify({
            "message": "Quyền chỉ có thể là user hoặc admin"
        }), 400

    conn = get_db_connection()

    user = conn.execute(
        "SELECT id, username, role FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()
        return jsonify({
            "message": "Không tìm thấy tài khoản"
        }), 404

    if user["role"] == "owner":
        conn.close()
        return jsonify({
            "message": "Không thể thay đổi quyền Owner"
        }), 403

    conn.execute(
        "UPDATE users SET role = ? WHERE id = ?",
        (role, user_id)
    )
    conn.commit()
    conn.close()

    add_log(
        admin["username"],
        "ADMIN ROLE",
        status=f"Đổi {user['username']} thành {role}"
    )

    return jsonify({
        "success": True,
        "message": f"Đã đổi quyền {user['username']} thành {role}."
    })


# ============================================================
# ADMIN API - TẠO TÀI KHOẢN ADMIN
# ============================================================

@app.route("/admin/api/create-admin", methods=["POST"])
def admin_api_create_admin():
    admin, error = admin_required_api()

    if error:
        return error

    # Chỉ owner được tạo admin mới
    if admin["role"] != "owner":
        return jsonify({
            "message": "Chỉ Owner mới được tạo tài khoản Admin."
        }), 403

    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip().lower()
    password = str(data.get("password") or "").strip()

    if not valid_username(username):
        return jsonify({
            "message": "Tên tài khoản không hợp lệ (3-20 ký tự, chữ/số/_)."
        }), 400

    if len(password) < 4:
        return jsonify({
            "message": "Mật khẩu tối thiểu 4 ký tự."
        }), 400

    conn = get_db_connection()

    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if existing:
        conn.close()
        return jsonify({
            "message": "Tên tài khoản đã tồn tại."
        }), 400

    init_balance = 10000
    try:
        init_balance = int(data.get("balance") or 10000)
        if init_balance < 0:
            init_balance = 0
        if init_balance > 10_000_000:
            init_balance = 10_000_000
    except (TypeError, ValueError):
        init_balance = 10000

    conn.execute(
        """
        INSERT INTO users
        (username, password_hash, role, balance, created_at)
        VALUES (?, ?, 'admin', ?, ?)
        """,
        (username, hash_password(password), init_balance, now())
    )
    conn.commit()
    conn.close()

    add_log(
        admin["username"],
        "TẠO ADMIN",
        status=f"Tạo admin: {username}"
    )

    return jsonify({
        "success": True,
        "message": f"Đã tạo tài khoản Admin: {username} (số dư {init_balance:,})."
    })


# ============================================================
# ADMIN API - LOGS
# ============================================================

@app.route("/admin/api/logs")
def admin_api_logs():
    admin, error = admin_required_api()

    if error:
        return error

    conn = get_db_connection()

    rows = conn.execute("""
        SELECT
            id,
            created_at,
            username,
            game_name,
            bet_amount,
            win_amount,
            status
        FROM game_logs
        ORDER BY id DESC
        LIMIT 100
    """).fetchall()

    conn.close()

    result = []

    for row in rows:
        result.append({
            "id": row["id"],
            "created_at": row["created_at"] or "",
            "username": row["username"] or "",
            "action": row["game_name"] or "",
            "bet_amount": row["bet_amount"] or 0,
            "win_amount": row["win_amount"] or 0,
            "amount": row["win_amount"] or 0,
            "status": row["status"] or ""
        })

    return jsonify(result)


# ============================================================
# ADMIN API - 1 USER
# ============================================================

@app.route("/admin/api/user/<int:user_id>")
def admin_api_user(user_id):
    admin, error = admin_required_api()

    if error:
        return error

    conn = get_db_connection()

    user = conn.execute("""
        SELECT
            id,
            username,
            balance,
            role,
            created_at
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    conn.close()

    if not user:
        return jsonify({
            "message": "Không tìm thấy tài khoản"
        }), 404

    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "fc": user["balance"] or 0,
        "role": user["role"] or "user",
        "created_at": user["created_at"]
    })


# ============================================================
# API - CURRENT USER
# ============================================================

@app.route("/api/me")
def api_me():
    user, error = require_login_api()

    if error:
        return error

    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "balance": user["balance"]
    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "TX68 GAME",
        "time": now()
    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"message": "Không tìm thấy API"}), 404

    return """
    <h1>404</h1>
    <p>Không tìm thấy trang.</p>
    <a href="/">Về trang chủ</a>
    """, 404


@app.errorhandler(500)
def server_error(error):
    if request.path.startswith("/api/"):
        return jsonify({"message": "Lỗi máy chủ"}), 500

    return """
    <h1>500</h1>
    <p>Máy chủ gặp lỗi.</p>
    """, 500


# ============================================================
# START
# ============================================================

init_db()

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))

    print("=" * 55)
    print("TX68 GAME SERVER")
    print("=" * 55)
    print(f"Database : {DB_PATH}")
    print(f"Server   : http://127.0.0.1:{port}")
    print("Owner mặc định: pphuc8386 / Mmmmmm@6")
    print("Hãy đổi mật khẩu Owner trước khi dùng thật.")
    print("=" * 55)

    app.run(
        host=host,
        port=port,
        debug=False
    )
