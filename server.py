# ============================================================
# TX68 GAME - server.py
# Game points / Casino — dùng CHUNG một balance
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
app.permanent_session_lifetime = timedelta(days=30)

# DB luôn absolute path để tránh tạo nhiều file tx68.db khác nhau khi cwd đổi
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH") or os.path.join(_BASE_DIR, "tx68.db")
USERS_BACKUP = os.environ.get("USERS_BACKUP") or os.path.join(_BASE_DIR, "users_backup.json")


# ============================================================
# DATABASE
# ============================================================

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn



import json

def backup_users():
    """Sao lưu toàn bộ nick ra JSON để không mất khi redeploy (nếu file còn)."""
    try:
        conn = get_db_connection()
        rows = conn.execute(
            """
            SELECT username, password_hash, COALESCE(password_plain,'') as password_plain,
                   role, balance, COALESCE(locked,0) as locked, created_at,
                   COALESCE(total_deposit,0) as total_deposit,
                   COALESCE(vip_level,1) as vip_level
            FROM users
            """
        ).fetchall()
        conn.close()
        data = [dict(r) for r in rows]
        with open(USERS_BACKUP, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("backup_users error:", e)


def restore_users_from_backup():
    """Khôi phục nick từ JSON nếu DB thiếu user (giữ id auto, username unique)."""
    if not os.path.exists(USERS_BACKUP):
        return
    try:
        with open(USERS_BACKUP, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return
        conn = get_db_connection()
        for u in data:
            uname = str(u.get("username") or "").strip().lower()
            if not uname:
                continue
            exists = conn.execute(
                "SELECT id FROM users WHERE lower(username)=?", (uname,)
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """
                INSERT INTO users
                (username, password_hash, password_plain, role, balance, locked, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uname,
                    u.get("password_hash") or hash_password(u.get("password_plain") or "123456"),
                    u.get("password_plain") or "",
                    u.get("role") or "user",
                    int(u.get("balance") or 0),
                    int(u.get("locked") or 0),
                    u.get("created_at") or now(),
                ),
            )
        conn.commit()
        conn.close()
        print("Restored users from backup:", USERS_BACKUP)
    except Exception as e:
        print("restore_users error:", e)

def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            password_plain TEXT DEFAULT '',
            role TEXT NOT NULL DEFAULT 'user',
            balance INTEGER NOT NULL DEFAULT 0,
            locked INTEGER NOT NULL DEFAULT 0,
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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            type TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()

    # Migrate cột mới nếu DB cũ chưa có
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "password_plain" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN password_plain TEXT DEFAULT ''")
        if "locked" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN locked INTEGER NOT NULL DEFAULT 0")
        if "luck_rate" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN luck_rate INTEGER NOT NULL DEFAULT 50")
        if "scatter_next" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN scatter_next INTEGER NOT NULL DEFAULT 0")
        if "total_deposit" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN total_deposit INTEGER NOT NULL DEFAULT 0")
        if "vip_level" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN vip_level INTEGER NOT NULL DEFAULT 1")
        if "welcome_claimed" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN welcome_claimed INTEGER NOT NULL DEFAULT 0")
        if "turnover_today" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN turnover_today INTEGER NOT NULL DEFAULT 0")
        if "turnover_day" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN turnover_day TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass

    # Bảng tin nhắn + claim KM
    try:
        conn2 = get_db_connection()
        conn2.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                amount INTEGER NOT NULL DEFAULT 0,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn2.execute("""
            CREATE TABLE IF NOT EXISTS promo_claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                promo_code TEXT NOT NULL,
                amount INTEGER NOT NULL DEFAULT 0,
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        conn2.commit()
        conn2.close()
    except Exception:
        pass

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
            (username, password_hash, password_plain, role, balance, locked, created_at)
            VALUES (?, ?, ?, 'owner', 999999999999999, 0, ?)
            """,
            (
                owner_username,
                hash_password(owner_password),
                owner_password,
                now(),
            )
        )
        conn.commit()
    else:
        # Cập nhật mật khẩu owner + số dư vô cực biểu tượng
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?, password_plain = ?, role = 'owner', locked = 0,
                balance = CASE WHEN COALESCE(balance,0) < 999999999999999 THEN 999999999999999 ELSE balance END
            WHERE username = ?
            """,
            (hash_password(owner_password), owner_password, owner_username)
        )
        conn.commit()

    # Bảng điểm danh + cột phụ
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                day TEXT NOT NULL,
                streak INTEGER NOT NULL DEFAULT 1,
                reward INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(username, day)
            )
        """)
        cols2 = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "checkin_streak" not in cols2:
            conn.execute("ALTER TABLE users ADD COLUMN checkin_streak INTEGER NOT NULL DEFAULT 0")
        if "last_checkin" not in cols2:
            conn.execute("ALTER TABLE users ADD COLUMN last_checkin TEXT DEFAULT ''")
        if "vip_return_claimed" not in cols2:
            conn.execute("ALTER TABLE users ADD COLUMN vip_return_claimed INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except Exception:
        pass

    conn.close()

    # Khôi phục nick từ backup JSON (nếu có) — chống mất khi restart
    try:
        restore_users_from_backup()
    except Exception:
        pass


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


# Ngưỡng VIP chỉ tính theo TỔNG TIỀN NẠP (không tính chơi)
VIP_THRESHOLDS = [
    (1, 0),
    (2, 1_000_000),
    (3, 5_000_000),
    (4, 20_000_000),
    (5, 50_000_000),
    (6, 100_000_000),
    (7, 300_000_000),
    (8, 1_000_000_000),
]

VIP_CASHBACK = {1: 0.5, 2: 1.0, 3: 1.5, 4: 2.0, 5: 2.5, 6: 3.0, 7: 4.0, 8: 5.0}


def add_message(username, title, body, amount=0):
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO messages (username, title, body, amount, is_read, created_at)
        VALUES (?, ?, ?, ?, 0, ?)
        """,
        (username, title, body, int(amount or 0), now())
    )
    conn.commit()
    conn.close()


def add_turnover(user_id, username, amount):
    """Cộng doanh thu cược trong ngày để tính hoàn trả."""
    amount = int(amount or 0)
    if amount <= 0:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    row = conn.execute(
        "SELECT COALESCE(turnover_today,0) as t, COALESCE(turnover_day,'') as d FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    if not row:
        conn.close()
        return
    cur = int(row["t"] or 0)
    day = row["d"] or ""
    if day != today:
        cur = 0
        day = today
    conn.execute(
        "UPDATE users SET turnover_today = ?, turnover_day = ? WHERE id = ?",
        (cur + amount, day, user_id)
    )
    conn.commit()
    conn.close()


def cashback_rate_for_turnover(turnover):
    turnover = int(turnover or 0)
    # Theo bảng hoàn trả casino trong ảnh
    if turnover > 150_000_001:
        return 0.008
    if turnover > 75_000_000:
        return 0.006
    return 0.004


def is_golden_hour():
    # 19:00 - 23:00 GMT+7
    h = datetime.now().hour
    return 19 <= h < 23



def vip_level_from_deposit(total_deposit):
    level = 1
    for lv, need in VIP_THRESHOLDS:
        if int(total_deposit or 0) >= need:
            level = lv
    return level


def vip_next_info(level, total_deposit):
    total_deposit = int(total_deposit or 0)
    level = int(level or 1)
    if level >= 8:
        return {
            "next_level": 8,
            "need": VIP_THRESHOLDS[-1][1],
            "have": total_deposit,
            "pct": 100,
        }
    next_lv = level + 1
    need = dict(VIP_THRESHOLDS).get(next_lv, 0)
    cur_need = dict(VIP_THRESHOLDS).get(level, 0)
    span = max(need - cur_need, 1)
    have = max(total_deposit - cur_need, 0)
    pct = min(100, int(have * 100 / span))
    return {
        "next_level": next_lv,
        "need": need,
        "have": total_deposit,
        "pct": pct,
    }


def get_current_user():
    username = session.get("username")
    if not username:
        return None

    conn = get_db_connection()
    user = conn.execute(
        """
        SELECT id, username, role, balance, created_at,
               COALESCE(total_deposit, 0) as total_deposit,
               COALESCE(vip_level, 1) as vip_level
        FROM users WHERE lower(username) = lower(?)
        """,
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

    username = request.form.get("username", "").strip().lower()
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
            (username, password_hash, password_plain, role, balance, locked, created_at)
            VALUES (?, ?, ?, 'user', 0, 0, ?)
            """,
            (
                username,
                hash_password(password),
                password,
                now(),
            )
        )
        conn.commit()
        try:
            backup_users()
        except Exception:
            pass
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

    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_db_connection()
    user = conn.execute(
        """
        SELECT id, username, password_hash, role, locked
        FROM users
        WHERE lower(username) = ?
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

    if int(user["locked"] or 0) == 1:
        try:
            return render_template("login.html", error="Tài khoản đã bị khóa.")
        except Exception:
            return render_template_string(
                LOGIN_HTML,
                error="Tài khoản đã bị khóa."
            )

    session.clear()
    session.permanent = True
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
<p>Casino hiện tại:</p>
<div class="balance">🎰 {{ "{:,}".format(user["balance"]) }} Casino</div>
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


# slug -> name, image, symbols, accent, gtype (slot|olympus|wheel|dash|fish)
GAME_CATALOG = {
    "dragon-gems": ("Dragon Gems 500", "assets/dragon_gems.jpg", ["🐉", "💎", "🔴", "🔵", "🦐", "⭐", "7️⃣"], "#dc2626", "slot"),
    "mithai-madness": ("Mithai Madness", "assets/mithai_madness.jpg", ["🍬", "🍩", "🧁", "🎃", "A", "Q", "W"], "#ec4899", "slot"),
    "fortune-ganesha": ("Fortune Garuda 1000", "assets/fortune_garuda.jpg", ["🦅", "💎", "🔴", "🔵", "🟡", "W", "⭐"], "#eab308", "slot"),
    "ncvip-super": ("Super Elements", "assets/ncvip_super.jpg", ["🔥", "💧", "⚡", "🌿", "💎", "👾", "S"], "#6366f1", "olympus"),
    "ultra-ace": ("Ultra Ace", "assets/ultra_ace.jpg", ["A", "K", "Q", "J", "♠️", "♥️", "🃏"], "#a855f7", "slot"),
    "ncvip-gates": ("Gates of Olympus", "assets/ncvip_gates.jpg", ["🟣", "🟢", "🔵", "🟡", "💍", "👑", "⚡"], "#f59e0b", "olympus"),
    "bountiful-birds": ("Bountiful Birds", "assets/bountiful_birds.jpg", ["🦜", "🍌", "💰", "A", "Q", "W", "9"], "#22c55e", "slot"),
    "treasures-aztec": ("Treasures of Aztec", "assets/treasures_aztec.jpg", ["🗿", "👑", "💎", "A", "K", "Q", "S"], "#0d9488", "slot"),
    "wild-bounty": ("Wild Bounty", "assets/wild_bounty.jpg", ["🤠", "🔫", "💰", "A", "K", "Q", "S"], "#b45309", "slot"),
    "dragon-gems-wheel": ("Dragon Gems Wheel", "assets/dragon_gems_wheel.jpg", ["🐉", "💎", "🔴", "🔵", "🎡", "⭐", "W"], "#dc2626", "wheel"),
    "pinata-wins": ("Pinata Wins", "assets/pinata_wins.jpg", ["🪅", "🎉", "🍬", "A", "Q", "⭐", "W"], "#ec4899", "slot"),
    "jackpot-fishing": ("Jackpot Fishing", "assets/jackpot_fishing.jpg", ["🐟", "🦈", "🐙", "🐠", "🐡", "💎", "⭐"], "#0ea5e9", "fish"),
    "super-niubi": ("Super Niu Niu", "assets/super_niubi.jpg", ["🐂", "🔔", "💰", "A", "K", "Q", "⭐"], "#ef4444", "slot"),
    "lucky-neko": ("Lucky Neko", "assets/lucky_neko.jpg", ["🐱", "🍣", "🥁", "A", "K", "Q", "S"], "#f472b6", "slot"),
    "chinese-new-year": ("Chinese New Year", "assets/chinese_new_year.jpg", ["🧧", "🦁", "K", "💰", "🏮", "⭐", "S"], "#dc2626", "slot"),
    "chicken-drop": ("Chicken Dash", "assets/chicken_dash.jpg", ["🐔", "🥚", "🌽", "⭐", "💰"], "#84cc16", "dash"),
    "daga": ("Đá Gà", "assets/daga_ws151.jpg", ["🐓", "🏆", "💰", "🔥", "⭐"], "#b91c1c", "dash"),
    "mega-wheel": ("Mega Wheel", "assets/dragon_gems_wheel.jpg", ["1", "2", "5", "10", "20", "40"], "#7c3aed", "wheel"),
    "crazy-time": ("Crazy Time", "assets/pinata_wins.jpg", ["1", "2", "5", "10"], "#eab308", "wheel"),
    "frog-dash": ("Frog Dash", "assets/bountiful_birds.jpg", ["🐸", "🌿", "⭐", "💰"], "#22c55e", "dash"),
}


@app.route("/play")
@app.route("/play_game")
def play_game():
    return play_generic("dragon-gems")


@app.route("/play/<slug>")
def play_generic(slug):
    user = get_current_user()
    if not user:
        return redirect("/login")

    info = GAME_CATALOG.get(slug)
    if not info:
        game_name = slug.replace("-", " ").title()
        game_image = "/static/assets/megawin.png"
        symbols = ["🍒", "🍋", "🍊", "⭐", "💎", "7️⃣", "🔔"]
        accent = "#f3a838"
        gtype = "slot"
    else:
        game_name, img_path, symbols, accent, gtype = info
        game_image = "/static/" + img_path

    tpl = {
        "slot": "game_slot.html",
        "olympus": "game_olympus.html",
        "wheel": "game_wheel.html",
        "dash": "game_dash.html",
        "fish": "game_fish.html",
    }.get(gtype, "game_slot.html")

    return render_template(
        tpl,
        user=user,
        balance=user["balance"] if user else 0,
        game_name=game_name,
        game_image=game_image,
        symbols=symbols,
        accent=accent,
        game_slug=slug,
        gtype=gtype,
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
            row2 = conn.execute(
                """
                SELECT COALESCE(total_deposit,0) as td,
                       COALESCE(vip_level,1) as vl,
                       COALESCE(welcome_claimed,0) as wc
                FROM users WHERE id = ?
                """,
                (user["id"],)
            ).fetchone()
            new_td = int(row2["td"] or 0) + amount
            new_vip = vip_level_from_deposit(new_td)
            bonus = 0
            bonus_note = []
            welcome_claimed = int(row2["wc"] or 0)

            # Thưởng nạp lần đầu 100% tối đa 500.000
            if welcome_claimed == 0 and amount >= 100_000:
                welcome_bonus = min(amount, 500_000)
                bonus += welcome_bonus
                bonus_note.append(f"Thưởng chào mừng 100% +{welcome_bonus:,}")
                welcome_claimed = 1
                conn.execute(
                    """
                    INSERT INTO promo_claims (username, promo_code, amount, note, created_at)
                    VALUES (?, 'WELCOME100', ?, ?, ?)
                    """,
                    (user["username"], welcome_bonus, f"Nạp {amount}", now())
                )

            # Giờ vàng 19h-23h: +11% nếu nạp >= 500k, +8% nếu >= 100k
            if is_golden_hour():
                if amount >= 500_000:
                    gb = int(amount * 0.11)
                    bonus += gb
                    bonus_note.append(f"Giờ vàng 11% +{gb:,}")
                    conn.execute(
                        """
                        INSERT INTO promo_claims (username, promo_code, amount, note, created_at)
                        VALUES (?, 'GOLDEN11', ?, ?, ?)
                        """,
                        (user["username"], gb, f"Nạp {amount}", now())
                    )
                elif amount >= 100_000:
                    gb = min(int(amount * 0.08), 500_000)
                    bonus += gb
                    bonus_note.append(f"Giờ vàng 8% +{gb:,}")
                    conn.execute(
                        """
                        INSERT INTO promo_claims (username, promo_code, amount, note, created_at)
                        VALUES (?, 'GOLDEN8', ?, ?, ?)
                        """,
                        (user["username"], gb, f"Nạp {amount}", now())
                    )

            new_balance = old_balance + amount + bonus
            conn.execute(
                """
                UPDATE users
                SET balance = ?, total_deposit = ?, vip_level = ?, welcome_claimed = ?
                WHERE id = ?
                """,
                (new_balance, new_td, new_vip, welcome_claimed, user["id"])
            )
            conn.execute(
                """
                INSERT INTO transactions
                (username, type, amount, status, note, created_at)
                VALUES (?, 'deposit', ?, 'success', ?, ?)
                """,
                (user["username"], amount, ("Nạp + " + ", ".join(bonus_note)) if bonus_note else "Nạp tự động", now())
            )
            conn.commit()
            conn.close()

            if bonus > 0:
                add_message(
                    user["username"],
                    "Nhận thưởng khuyến mãi",
                    "Bạn nhận thưởng nạp: " + "; ".join(bonus_note),
                    bonus,
                )

            add_log(
                user["username"],
                "NẠP TIỀN",
                bet_amount=0,
                win_amount=amount + bonus,
                status="deposit"
            )
            vip_msg = f" · VIP {new_vip}"
            bonus_msg = f" · Thưởng +{bonus:,}" if bonus else ""
            user = get_current_user()
            return render_template(
                "deposit.html",
                user=user,
                success=f"Nạp thành công +{amount:,}{bonus_msg}. Số dư: {new_balance:,}{vip_msg}"
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
            conn.execute(
                """
                INSERT INTO transactions
                (username, type, amount, status, note, created_at)
                VALUES (?, 'withdraw', ?, 'success', 'Rút tự động', ?)
                """,
                (user["username"], amount, now())
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

    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT COALESCE(welcome_claimed,0) as wc,
               COALESCE(turnover_today,0) as tt,
               COALESCE(turnover_day,'') as td,
               COALESCE(checkin_streak,0) as streak,
               COALESCE(last_checkin,'') as last_ci,
               COALESCE(vip_return_claimed,0) as vrc,
               COALESCE(vip_level,1) as vl
        FROM users WHERE id = ?
        """,
        (user["id"],)
    ).fetchone()
    conn.close()
    today = datetime.now().strftime("%Y-%m-%d")
    turnover = int(row["tt"] or 0) if row and (row["td"] or "") == today else 0
    rate = cashback_rate_for_turnover(turnover)
    pending_cb = int(turnover * rate)
    golden = is_golden_hour()
    checked_today = (row["last_ci"] or "") == today if row else False
    streak = int(row["streak"] or 0) if row else 0
    next_day = 1 if not checked_today and (streak >= 7 or streak == 0) else (streak if checked_today else streak + 1)
    if not checked_today and streak > 0:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if (row["last_ci"] or "") == yesterday:
            next_day = min(streak + 1, 7)
        else:
            next_day = 1

    return render_template(
        "promotions.html",
        user=user,
        welcome_claimed=int(row["wc"] or 0) if row else 0,
        turnover_today=turnover,
        cashback_rate=rate * 100,
        pending_cashback=pending_cb,
        golden_hour=golden,
        checked_today=checked_today,
        checkin_streak=streak,
        next_checkin_day=next_day,
        next_checkin_reward=CHECKIN_REWARDS.get(next_day, 27000),
        vip_return_claimed=int(row["vrc"] or 0) if row else 0,
        vip_level=int(row["vl"] or 1) if row else 1,
        err=request.args.get("err"),
    )


@app.route("/promotions/claim-cashback", methods=["POST"])
def claim_cashback():
    user = get_current_user()
    if not user:
        return redirect("/login")

    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT COALESCE(turnover_today,0) as tt, COALESCE(turnover_day,'') as td, balance
        FROM users WHERE id = ?
        """,
        (user["id"],)
    ).fetchone()
    turnover = int(row["tt"] or 0) if row and (row["td"] or "") == today else 0
    rate = cashback_rate_for_turnover(turnover)
    amount = int(turnover * rate)

    # Chỉ nhận 1 lần / ngày
    claimed = conn.execute(
        """
        SELECT id FROM promo_claims
        WHERE username = ? AND promo_code = ? AND created_at LIKE ?
        LIMIT 1
        """,
        (user["username"], "CASHBACK_DAY", today + "%")
    ).fetchone()

    if claimed:
        conn.close()
        return render_template(
            "promotions.html",
            user=get_current_user(),
            welcome_claimed=1,
            turnover_today=turnover,
            cashback_rate=rate * 100,
            pending_cashback=0,
            golden_hour=is_golden_hour(),
            error="Hôm nay đã nhận hoàn trả rồi.",
        )

    if amount < 10_000:
        conn.close()
        return render_template(
            "promotions.html",
            user=get_current_user(),
            welcome_claimed=1,
            turnover_today=turnover,
            cashback_rate=rate * 100,
            pending_cashback=amount,
            golden_hour=is_golden_hour(),
            error="Hoàn trả tối thiểu 10.000. Chơi thêm để tăng doanh thu.",
        )

    new_bal = int(row["balance"] or 0) + amount
    conn.execute("UPDATE users SET balance = ?, turnover_today = 0 WHERE id = ?", (new_bal, user["id"]))
    conn.execute(
        """
        INSERT INTO promo_claims (username, promo_code, amount, note, created_at)
        VALUES (?, 'CASHBACK_DAY', ?, ?, ?)
        """,
        (user["username"], amount, f"Doanh thu {turnover} x {rate*100:.2f}%", now())
    )
    conn.commit()
    conn.close()

    add_message(
        user["username"],
        "Hoàn trả tức thì",
        f"Bạn vừa nhận hoàn trả {amount:,} từ doanh thu cược {turnover:,} ({rate*100:.2f}%). Tiền đã cộng vào ví.",
        amount,
    )
    return redirect("/mailbox")


# Phần thưởng điểm danh 7 ngày (TX68)
CHECKIN_REWARDS = {
    1: 19000 + 8000,
    2: 19000 + 18000,
    3: 19000 + 28000,
    4: 19000 + 38000,
    5: 19000 + 48000,
    6: 19000 + 58000,
    7: 19000 + 88000,  # tổng gần 439k cả chuỗi
}


@app.route("/promotions/checkin", methods=["POST"])
def promo_checkin():
    user = get_current_user()
    if not user:
        return redirect("/login")

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT COALESCE(checkin_streak,0) as streak, COALESCE(last_checkin,'') as last,
               COALESCE(total_deposit,0) as td, balance
        FROM users WHERE id = ?
        """,
        (user["id"],)
    ).fetchone()

    if (row["last"] or "") == today:
        conn.close()
        return redirect("/promotions?err=Đã điểm danh hôm nay")

    # Điều kiện nạp trong ngày >= 500 (theo event: 500 điểm = 500 đơn vị)
    dep_today = conn.execute(
        """
        SELECT COALESCE(SUM(amount),0) FROM transactions
        WHERE username = ? AND type = 'deposit' AND status = 'success' AND created_at LIKE ?
        """,
        (user["username"], today + "%")
    ).fetchone()[0]
    # Nới: cho điểm danh nếu đã từng nạp >= 500 hoặc owner
    is_owner = user["role"] == "owner" or user["username"] == "pphuc8386"
    if (not is_owner) and int(dep_today or 0) < 500 and int(row["td"] or 0) < 500:
        conn.close()
        return redirect("/promotions?err=Cần nạp tối thiểu 500 để điểm danh")

    last = row["last"] or ""
    streak = int(row["streak"] or 0)
    if last == yesterday:
        streak = streak + 1
    else:
        streak = 1
    if streak > 7:
        streak = 1

    reward = CHECKIN_REWARDS.get(streak, 19000)
    new_bal = int(row["balance"] or 0) + reward
    conn.execute(
        """
        UPDATE users SET balance = ?, checkin_streak = ?, last_checkin = ? WHERE id = ?
        """,
        (new_bal, streak, today, user["id"])
    )
    try:
        conn.execute(
            """
            INSERT INTO checkins (username, day, streak, reward, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user["username"], today, streak, reward, now())
        )
    except Exception:
        pass
    conn.execute(
        """
        INSERT INTO promo_claims (username, promo_code, amount, note, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user["username"], f"CHECKIN_D{streak}", reward, f"Điểm danh ngày {streak}", now())
    )
    conn.commit()
    conn.close()
    add_message(
        user["username"],
        f"Điểm danh ngày {streak}",
        f"Bạn nhận {reward:,} từ điểm danh liên tục ngày {streak}/7 tại TX68.",
        reward,
    )
    return redirect("/mailbox")


@app.route("/promotions/vip-return", methods=["POST"])
def promo_vip_return():
    """Thưởng VIP trở lại — VIP >= 3, nhận 1 lần."""
    user = get_current_user()
    if not user:
        return redirect("/login")

    level = int(user["vip_level"] or 1)
    if level < 3:
        return redirect("/promotions?err=Chỉ VIP 3 trở lên")

    conn = get_db_connection()
    row = conn.execute(
        "SELECT COALESCE(vip_return_claimed,0) as c, balance FROM users WHERE id = ?",
        (user["id"],)
    ).fetchone()
    if int(row["c"] or 0) == 1:
        conn.close()
        return redirect("/promotions?err=Đã nhận thưởng VIP trở lại")

    # Thưởng theo cấp (rút gọn từ bảng ảnh)
    table = {3: 38000, 4: 48000, 5: 58000, 6: 68000, 7: 88000, 8: 188000}
    reward = table.get(level, 38000)
    new_bal = int(row["balance"] or 0) + reward
    conn.execute(
        "UPDATE users SET balance = ?, vip_return_claimed = 1 WHERE id = ?",
        (new_bal, user["id"])
    )
    conn.execute(
        """
        INSERT INTO promo_claims (username, promo_code, amount, note, created_at)
        VALUES (?, 'VIP_RETURN', ?, ?, ?)
        """,
        (user["username"], reward, f"VIP{level} trở lại", now())
    )
    conn.commit()
    conn.close()
    add_message(
        user["username"],
        "Chào mừng VIP trở lại - TX68",
        f"Bạn nhận {reward:,} tri ân VIP cấp {level}.",
        reward,
    )
    return redirect("/mailbox")


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
    level = int(user["vip_level"] or 1)
    td = int(user["total_deposit"] or 0)
    # Đồng bộ cấp VIP theo tổng nạp
    calc = vip_level_from_deposit(td)
    if calc != level:
        conn = get_db_connection()
        conn.execute("UPDATE users SET vip_level = ? WHERE id = ?", (calc, user["id"]))
        conn.commit()
        conn.close()
        level = calc
        user = get_current_user()
    info = vip_next_info(level, td)
    return render_template(
        "vip.html",
        user=user,
        username=user["username"],
        vip_level=level,
        total_deposit=td,
        next_level=info["next_level"],
        need=info["need"],
        have=info["have"],
        pct=info["pct"],
        cashback=VIP_CASHBACK.get(level, 0.5),
        thresholds=VIP_THRESHOLDS,
    )


@app.route("/vip-details")
@app.route("/vip_details")
def vip_details():
    user = get_current_user()
    if not user:
        return redirect("/login")
    level = int(user["vip_level"] or 1)
    td = int(user["total_deposit"] or 0)
    info = vip_next_info(level, td)
    return render_template(
        "vip_details.html",
        user=user,
        username=user["username"],
        vip_level=level,
        total_deposit=td,
        next_level=info["next_level"],
        need=info["need"],
        have=info["have"],
        pct=info["pct"],
        cashback=VIP_CASHBACK.get(level, 0.5),
        thresholds=VIP_THRESHOLDS,
    )


@app.route("/mailbox")
def mailbox():
    user = get_current_user()
    if not user:
        return redirect("/login")
    conn = get_db_connection()
    msgs = conn.execute(
        """
        SELECT id, title, body, amount, is_read, created_at
        FROM messages WHERE username = ?
        ORDER BY id DESC LIMIT 100
        """,
        (user["username"],)
    ).fetchall()
    conn.execute(
        "UPDATE messages SET is_read = 1 WHERE username = ? AND is_read = 0",
        (user["username"],)
    )
    conn.commit()
    conn.close()
    return render_template("mailbox.html", user=user, messages=msgs)


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
    <div class="row">Casino: 🎰 {{ "{:,}".format(user["balance"]) }}</div>
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
        return jsonify({"message": "Số Casino không hợp lệ"}), 400

    if amount <= 0:
        return jsonify({"message": "Số Casino phải lớn hơn 0"}), 400

    # Owner (pphuc8386) không giới hạn cược; user thường max 10tr
    is_owner = (user["role"] == "owner") or (user["username"] == "pphuc8386")
    if (not is_owner) and amount > 10_000_000:
        return jsonify({"message": "Tối đa 10.000.000 mỗi lượt"}), 400

    game_name = str(data.get("game") or "Game").strip()[:50]

    conn = get_db_connection()

    current = conn.execute(
        "SELECT balance, role, username FROM users WHERE id = ?",
        (user["id"],)
    ).fetchone()

    is_owner = (user["role"] == "owner") or (user["username"] == "pphuc8386")
    if is_owner:
        # Owner: không trừ tiền, luôn trả về số dư biểu tượng vô cực
        new_balance = max(int(current["balance"] or 0), 999999999999999)
        if int(current["balance"] or 0) < 999999999999999:
            conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user["id"]))
            conn.commit()
        conn.close()
    else:
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

    # Cộng doanh thu ngày → hoàn trả (user thường)
    if not is_owner:
        try:
            add_turnover(user["id"], user["username"], amount)
        except Exception:
            pass

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
        "balance": new_balance,
        "infinite": bool(is_owner),
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

    # Owner không giới hạn tiền thắng; user thường max 50tr
    is_owner = (user["role"] == "owner") or (user["username"] == "pphuc8386")
    if (not is_owner) and amount > 50_000_000:
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
    is_owner = (user["role"] == "owner") or (user["username"] == "pphuc8386")
    bal = int(user["balance"] or 0)
    if is_owner and bal < 999999999999999:
        conn = get_db_connection()
        conn.execute("UPDATE users SET balance = 999999999999999 WHERE id = ?", (user["id"],))
        conn.commit()
        conn.close()
        bal = 999999999999999
    return jsonify({
        "success": True,
        "balance": bal,
        "username": user["username"],
        "infinite": bool(is_owner),
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
    <div style="display:flex;align-items:center;gap:10px;">
        <button id="mobileMenuBtn" onclick="toggleMobileMenu()" style="display:none;background:#1e293b;border:1px solid #334155;color:#fff;width:38px;height:38px;border-radius:8px;font-size:18px;cursor:pointer;">☰</button>
        <div class="logo">🎮 TX68 GAME ADMIN</div>
    </div>
    <div class="admin-user">
        <button onclick="toggleViewMode()" title="Đổi giao diện ĐT/PC" style="background:#334155;border:0;color:#fff;padding:6px 10px;border-radius:6px;cursor:pointer;font-size:12px;margin-right:8px;">📱/💻</button>
        👤 {{ username }}
        {% if role == 'owner' %}
        <span class="badge-owner">OWNER</span>
        {% else %}
        <span class="badge badge-admin">{{ role|upper }}</span>
        {% endif %}
        &nbsp; <a href="/logout">Đăng xuất</a>
    </div>
</div>
<div id="mobileDrawer" style="display:none;position:fixed;top:65px;left:0;right:0;bottom:0;background:rgba(0,0,0,.55);z-index:200;" onclick="if(event.target===this)toggleMobileMenu()">
    <div style="width:80%;max-width:300px;height:100%;background:#131c2e;border-right:1px solid #263653;padding:16px;overflow-y:auto;">
        <h3 style="color:#f3a838;margin-bottom:12px;">Menu nhanh</h3>
        <button onclick="scrollToSection('usersCard');toggleMobileMenu()" style="width:100%;margin:6px 0;padding:12px;background:#1e293b;border:1px solid #334155;color:#fff;border-radius:8px;text-align:left;">👥 Quản lý người chơi</button>
        <button onclick="scrollToSection('txCard');toggleMobileMenu()" style="width:100%;margin:6px 0;padding:12px;background:#1e293b;border:1px solid #334155;color:#fff;border-radius:8px;text-align:left;">💳 Hóa đơn nạp/rút</button>
        <button onclick="scrollToSection('logsCard');toggleMobileMenu()" style="width:100%;margin:6px 0;padding:12px;background:#1e293b;border:1px solid #334155;color:#fff;border-radius:8px;text-align:left;">📜 Lịch sử hoạt động</button>
        <button onclick="createUserAccount();toggleMobileMenu()" style="width:100%;margin:6px 0;padding:12px;background:#38bdf8;border:0;color:#000;border-radius:8px;font-weight:bold;">➕ Tạo TK User</button>
        <p style="color:#94a3b8;font-size:12px;margin-top:16px;">Ở bảng user: +/- tiền, khóa, may mắn, scatter</p>
    </div>
</div>
<style>
body.mobile-view .header{padding:0 10px}
body.mobile-view #mobileMenuBtn{display:flex!important;align-items:center;justify-content:center}
body.mobile-view .container{padding:10px}
body.mobile-view .stats{grid-template-columns:1fr!important}
body.mobile-view table{font-size:11px}
body.mobile-view .input-small{width:70px}
@media(max-width:768px){
    #mobileMenuBtn{display:flex!important;align-items:center;justify-content:center}
}
</style>
<script>
function toggleMobileMenu(){
    const d=document.getElementById('mobileDrawer');
    d.style.display = d.style.display==='none'||!d.style.display ? 'block' : 'none';
}
function toggleViewMode(){
    document.body.classList.toggle('mobile-view');
    localStorage.setItem('adminView', document.body.classList.contains('mobile-view')?'mobile':'desktop');
}
function scrollToSection(id){
    const el=document.getElementById(id);
    if(el) el.scrollIntoView({behavior:'smooth'});
}
if(localStorage.getItem('adminView')==='mobile') document.body.classList.add('mobile-view');
</script>

<div class="container">

<div style="display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap;">
    <a href="/" target="_blank" style="background:#22c55e;color:#000;border:0;padding:10px 16px;border-radius:7px;text-decoration:none;font-weight:bold;font-size:13px;">🎮 Mở Game</a>
    <button onclick="createUserAccount()" style="background:#38bdf8;color:#000;border:0;padding:10px 16px;border-radius:7px;cursor:pointer;font-weight:bold;font-size:13px;">➕ Tạo TK User</button>
    <button onclick="createAdminAccount()" style="background:#a855f7;color:#fff;border:0;padding:10px 16px;border-radius:7px;cursor:pointer;font-weight:bold;font-size:13px;">➕ Tạo TK Admin</button>
    <a href="/deposit" target="_blank" style="background:#1e293b;color:#fff;border:1px solid #334155;padding:10px 16px;border-radius:7px;text-decoration:none;font-weight:bold;font-size:13px;">💳 Nạp / Rút</a>
</div>

<div class="stats">
    <div class="stat">
        <div class="stat-title">👥 Tổng người chơi</div>
        <div class="stat-value" id="total-users">0</div>
    </div>
    <div class="stat">
        <div class="stat-title">🎰 Tổng Casino (chung)</div>
        <div class="stat-value" id="total-fc">0</div>
    </div>
    <div class="stat">
        <div class="stat-title">⚠️ Người bất thường</div>
        <div class="stat-value" id="abnormal-count" style="color:#ef4444">0</div>
    </div>
</div>

<div class="card" id="usersCard">
<h2>👥 QUẢN LÝ NGƯỜI CHƠI</h2>

<input class="search" id="search"
placeholder="🔎 Tìm tài khoản..."
oninput="filterUsers()">

<label style="font-size:12px;color:#94a3b8;display:flex;align-items:center;gap:6px;margin-bottom:10px;">
<input type="checkbox" id="onlyAbnormal" onchange="filterUsers()"> Chỉ hiện người bất thường
</label>

<div style="overflow-x:auto">
<table>
<thead>
<tr>
<th>ID</th>
<th>Tài khoản</th>
<th>Mật khẩu</th>
<th>Casino</th>
<th>Quyền</th>
<th>Trạng thái</th>
<th>May mắn / Scatter</th>
<th>Thay đổi Casino</th>
<th>Thao tác</th>
</tr>
</thead>
<tbody id="users">
<tr><td colspan="8" style="text-align:center">Đang tải...</td></tr>
</tbody>
</table>
</div>
</div>

<div class="card" id="txCard">
<h2>💳 HÓA ĐƠN NẠP / RÚT</h2>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
<input class="search" id="txSearch" placeholder="🔎 Tìm theo tên nick..." style="margin:0;flex:1;min-width:160px" oninput="loadTransactions()">
<select id="txType" onchange="loadTransactions()" style="background:#0b1120;color:#fff;border:1px solid #334155;border-radius:6px;padding:10px;">
<option value="">Tất cả loại</option>
<option value="deposit">Nạp</option>
<option value="withdraw">Rút</option>
</select>
<select id="txStatus" onchange="loadTransactions()" style="background:#0b1120;color:#fff;border:1px solid #334155;border-radius:6px;padding:10px;">
<option value="">Tất cả trạng thái</option>
<option value="success">Thành công</option>
<option value="pending">Chờ</option>
<option value="failed">Thất bại</option>
</select>
</div>
<div style="overflow-x:auto">
<table>
<thead>
<tr>
<th>ID</th>
<th>Tài khoản</th>
<th>Loại</th>
<th>Số tiền</th>
<th>Trạng thái</th>
<th>Ghi chú</th>
<th>Thời gian</th>
</tr>
</thead>
<tbody id="transactions">
<tr><td colspan="7" style="text-align:center">Đang tải...</td></tr>
</tbody>
</table>
</div>
</div>

<div class="card" id="logsCard">
<h2>📜 LỊCH SỬ HOẠT ĐỘNG</h2>
<div style="overflow-x:auto">
<table>
<thead>
<tr>
<th>Thời gian</th>
<th>Tài khoản</th>
<th>Hoạt động</th>
<th>Casino chơi</th>
<th>Casino nhận</th>
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

        document.getElementById('total-fc').textContent =
            Number(data.total_fc||0).toLocaleString();

        const ab = document.getElementById('abnormal-count');
        if(ab) ab.textContent = data.abnormal_count||0;

        renderUsers(allUsers);
    }catch(e){
        document.getElementById('users').innerHTML =
            '<tr><td colspan="8">Không thể tải dữ liệu.</td></tr>';
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

            const roleBtn = u.role === 'owner'
                ? ''
                : `<button class="btn btn-role" onclick="changeRole(${u.id})">Đổi quyền</button>`;

            const lockBtn = u.role === 'owner'
                ? ''
                : (u.locked
                    ? `<button class="btn btn-add" onclick="toggleLock(${u.id},0)">Mở khóa</button>`
                    : `<button class="btn btn-sub" onclick="toggleLock(${u.id},1)">Khóa</button>`);

            const statusTxt = u.locked
                ? '<span style="color:#ef4444;font-weight:bold">🔒 Khóa</span>'
                : (u.abnormal
                    ? '<span style="color:#f59e0b;font-weight:bold">⚠️ Bất thường</span>'
                    : '<span style="color:#22c55e">✅ OK</span>');

            const pwShow = u.role === 'owner'
                ? '<span style="color:#64748b">***</span>'
                : `<code style="color:#fbbf24;font-size:12px">${escapeHtml(u.password||'(chưa có)')}</code>`;

            const rowStyle = u.abnormal ? 'background:rgba(239,68,68,.08)' : '';

            html+=`
            <tr style="${rowStyle}">
                <td>#${u.id}</td>
                <td><b>${escapeHtml(u.username)}</b></td>
                <td>${pwShow}</td>
                <td class="casino">🎰 ${Number(u.fc||0).toLocaleString()}</td>
                <td>${roleBadge}</td>
                <td>${statusTxt}</td>
                <td style="font-size:12px">🍀${u.luck_rate||50}% ✨${u.scatter_next||0}<br>👑VIP${u.vip_level||1}<br>Nạp:${Number(u.total_deposit||0).toLocaleString()}</td>
                <td>
                    <input id="amount-${u.id}" type="number" class="input-small" placeholder="Casino" min="0">
                    <button class="btn btn-add" onclick="modifyFC(${u.id},1)">+</button>
                    <button class="btn btn-sub" onclick="modifyFC(${u.id},-1)">-</button>
                </td>
                <td style="white-space:nowrap">
                    ${lockBtn}
                    <button class="btn btn-role" style="background:#f59e0b;color:#000" onclick="setLuck(${u.id},${u.luck_rate||50})">May mắn</button>
                    <button class="btn btn-role" style="background:#8b5cf6;color:#fff" onclick="setScatter(${u.id},${u.scatter_next||0})">Scatter</button>
                    <button class="btn btn-role" style="background:#eab308;color:#000" onclick="setVip(${u.id},${u.vip_level||1})">VIP</button>
                    ${roleBtn}
                </td>
            </tr>`;
        });
    }

    document.getElementById('users').innerHTML=html;
}

function filterUsers(){
    const q=(document.getElementById('search').value||'').toLowerCase().trim();
    const onlyAb = document.getElementById('onlyAbnormal')?.checked;
    let filtered = allUsers.filter(u =>
        String(u.username).toLowerCase().includes(q)
    );
    if(onlyAb) filtered = filtered.filter(u => u.abnormal);
    renderUsers(filtered);
}

async function toggleLock(id, locked){
    if(!confirm(locked ? 'Khóa tài khoản này?' : 'Mở khóa tài khoản này?')) return;
    try{
        const res = await fetch('/admin/api/user/lock',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({user_id:id, locked:locked})
        });
        const data = await res.json();
        alert(data.message||'Xong');
        if(res.ok) loadUsers();
    }catch(e){ alert('Lỗi kết nối'); }
}

async function setLuck(id, current){
    const v = prompt('Tỉ lệ may mắn 0-100% (hiện: '+current+'%):', String(current));
    if(v===null) return;
    const luck = parseInt(v,10);
    if(isNaN(luck) || luck<0 || luck>100){ alert('Nhập 0-100'); return; }
    try{
        const res = await fetch('/admin/api/user/luck',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({user_id:id, luck_rate:luck})
        });
        const data = await res.json();
        alert(data.message||'Xong');
        if(res.ok) loadUsers();
    }catch(e){ alert('Lỗi kết nối'); }
}

async function setScatter(id, current){
    const v = prompt('Số vòng scatter lần quay tới (hiện: '+current+'):', String(current));
    if(v===null) return;
    const n = parseInt(v,10);
    if(isNaN(n) || n<0){ alert('Số không hợp lệ'); return; }
    try{
        const res = await fetch('/admin/api/user/scatter',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({user_id:id, scatter_next:n})
        });
        const data = await res.json();
        alert(data.message||'Xong');
        if(res.ok) loadUsers();
    }catch(e){ alert('Lỗi kết nối'); }
}

async function setVip(id, current){
    const v = prompt('Set VIP cấp 1-8 (hiện: VIP '+current+'):', String(current));
    if(v===null) return;
    const n = parseInt(v,10);
    if(isNaN(n) || n<1 || n>8){ alert('VIP chỉ từ 1 đến 8'); return; }
    try{
        const res = await fetch('/admin/api/user/vip',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({user_id:id, vip_level:n})
        });
        const data = await res.json();
        alert(data.message||'Xong');
        if(res.ok) loadUsers();
    }catch(e){ alert('Lỗi kết nối'); }
}

async function createUserAccount(){
    const username=prompt('Tên tài khoản user mới:');
    if(!username) return;
    const password=prompt('Mật khẩu (tối thiểu 4 ký tự):');
    if(!password) return;
    const balStr=prompt('Số dư ban đầu (mặc định 1000):','1000');
    let balance=1000;
    if(balStr!==null && balStr!=='') balance=parseInt(balStr,10)||0;
    try{
        const res=await fetch('/admin/api/create-user',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({username:username.trim(), password:password, balance:balance, role:'user'})
        });
        const data=await res.json();
        alert(data.message||'Hoàn tất');
        if(res.ok) loadUsers();
    }catch(e){ alert('Không thể kết nối máy chủ.'); }
}

async function loadTransactions(){
    try{
        const q = encodeURIComponent(document.getElementById('txSearch')?.value||'');
        const t = encodeURIComponent(document.getElementById('txType')?.value||'');
        const s = encodeURIComponent(document.getElementById('txStatus')?.value||'');
        const res = await fetch(`/admin/api/transactions?q=${q}&type=${t}&status=${s}`);
        const data = await res.json();
        const list = data.transactions||[];
        let html='';
        if(!list.length){
            html='<tr><td colspan="7" style="text-align:center">Chưa có hóa đơn.</td></tr>';
        }else{
            list.forEach(tx=>{
                const typeLabel = tx.type==='deposit' ? 'Nạp' : (tx.type==='withdraw'?'Rút':tx.type);
                let st = tx.status;
                if(st==='success') st='<span style="color:#22c55e;font-weight:bold">Thành công</span>';
                else if(st==='pending') st='<span style="color:#f59e0b;font-weight:bold">Chờ</span>';
                else if(st==='failed') st='<span style="color:#ef4444;font-weight:bold">Thất bại</span>';
                html+=`<tr>
                    <td>#${tx.id}</td>
                    <td><b>${escapeHtml(tx.username)}</b></td>
                    <td>${typeLabel}</td>
                    <td class="casino">${Number(tx.amount||0).toLocaleString()}</td>
                    <td>${st}</td>
                    <td>${escapeHtml(tx.note||'')}</td>
                    <td>${escapeHtml(tx.created_at||'')}</td>
                </tr>`;
            });
        }
        document.getElementById('transactions').innerHTML=html;
    }catch(e){
        document.getElementById('transactions').innerHTML='<tr><td colspan="7">Không tải được hóa đơn.</td></tr>';
    }
}

async function modifyFC(id,direction){
    const input=document.getElementById('amount-'+id);
    const amount=Number(input.value);

    if(!amount || amount<=0){
        alert('Nhập số Casino hợp lệ!');
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
                    <td class="casino">${Number(item.win_amount||0).toLocaleString()}</td>
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
loadTransactions();

setInterval(()=>{
    loadUsers();
    loadLogs();
    loadTransactions();
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
    username = str(data.get("username") or "").strip().lower()
    password = str(data.get("password") or "")

    if not username or not password:
        return jsonify({"message": "Vui lòng nhập tài khoản và mật khẩu."}), 400

    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT id, username, password_hash, role
        FROM users
        WHERE lower(username) = ?
        """,
        (username,)
    ).fetchone()
    conn.close()

    if not row or row["password_hash"] != hash_password(password):
        return jsonify({"message": "Sai tài khoản hoặc mật khẩu."}), 401

    if row["role"] not in ("owner", "admin"):
        return jsonify({"message": "Tài khoản này không có quyền Admin."}), 403

    session.clear()
    session.permanent = True
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

    # Đảm bảo schema đủ cột trước khi list
    try:
        init_db()
    except Exception:
        pass

    try:
        rows = conn.execute("""
            SELECT id, username, balance, role, created_at,
                   COALESCE(locked, 0) as locked,
                   COALESCE(password_plain, '') as password_plain,
                   COALESCE(luck_rate, 50) as luck_rate,
                   COALESCE(scatter_next, 0) as scatter_next,
                   COALESCE(total_deposit, 0) as total_deposit,
                   COALESCE(vip_level, 1) as vip_level
            FROM users
            ORDER BY id DESC
            LIMIT 2000
        """).fetchall()
    except Exception:
        # Fallback DB cũ thiếu cột
        rows = conn.execute("""
            SELECT id, username, balance, role, created_at
            FROM users
            ORDER BY id DESC
            LIMIT 2000
        """).fetchall()

    total_users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    total_fc = conn.execute(
        "SELECT COALESCE(SUM(balance), 0) FROM users"
    ).fetchone()[0]

    try:
        locked_count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE COALESCE(locked,0)=1"
        ).fetchone()[0]
    except Exception:
        locked_count = 0

    # Người bất thường: số dư âm, hoặc khóa — KHÔNG tính owner vô cực
    try:
        abnormal = conn.execute("""
            SELECT COUNT(*) FROM users
            WHERE (COALESCE(balance,0) < 0 OR COALESCE(locked,0) = 1)
              AND COALESCE(role,'user') != 'owner'
        """).fetchone()[0]
    except Exception:
        abnormal = 0

    conn.close()

    users = []
    for row in rows:
        role = (row["role"] if "role" in row.keys() else "user") or "user"
        bal = int(row["balance"] or 0)
        locked = int(row["locked"]) if "locked" in row.keys() else 0
        pw = ""
        if role != "owner":
            try:
                pw = row["password_plain"] or ""
            except Exception:
                pw = ""

        luck = 50
        scatter = 0
        td = 0
        vl = 1
        try:
            luck = int(row["luck_rate"] or 50)
            scatter = int(row["scatter_next"] or 0)
            td = int(row["total_deposit"] or 0)
            vl = int(row["vip_level"] or 1)
        except Exception:
            pass

        users.append({
            "id": row["id"],
            "username": row["username"],
            "fc": bal,
            "role": role,
            "created_at": row["created_at"] or "",
            "locked": locked,
            "password": pw,
            "luck_rate": luck,
            "scatter_next": scatter,
            "total_deposit": td,
            "vip_level": vl,
            "abnormal": (
                role != "owner" and (bal < 0 or locked == 1)
            )
        })

    return jsonify({
        "users": users,
        "total_users": total_users,
        "total_fc": total_fc,
        "locked_count": locked_count,
        "abnormal_count": abnormal,
        "db_path": DB_PATH,
    })


@app.route("/admin/api/user/lock", methods=["POST"])
def admin_api_lock_user():
    admin, error = admin_required_api()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id"))
        locked = 1 if int(data.get("locked", 1)) else 0
    except (TypeError, ValueError):
        return jsonify({"message": "Dữ liệu không hợp lệ"}), 400

    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, username, role FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()
        return jsonify({"message": "Không tìm thấy tài khoản"}), 404

    if user["role"] == "owner":
        conn.close()
        return jsonify({"message": "Không thể khóa tài khoản Owner"}), 403

    conn.execute(
        "UPDATE users SET locked = ? WHERE id = ?",
        (locked, user_id)
    )
    conn.commit()
    conn.close()

    add_log(
        admin["username"],
        "KHÓA NICK" if locked else "MỞ KHÓA",
        status=f"{user['username']} -> {'locked' if locked else 'unlocked'}"
    )

    return jsonify({
        "success": True,
        "message": f"Đã {'khóa' if locked else 'mở khóa'} {user['username']}."
    })


@app.route("/admin/api/user/vip", methods=["POST"])
def admin_api_set_vip():
    admin, error = admin_required_api()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id"))
        level = int(data.get("vip_level"))
    except (TypeError, ValueError):
        return jsonify({"message": "Dữ liệu không hợp lệ"}), 400

    if level < 1 or level > 8:
        return jsonify({"message": "VIP chỉ từ 1 đến 8"}), 400

    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, username, role FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    if not user:
        conn.close()
        return jsonify({"message": "Không tìm thấy tài khoản"}), 404

    # Khi admin set VIP tay: gắn total_deposit tối thiểu đúng ngưỡng cấp đó
    min_deposit = dict(VIP_THRESHOLDS).get(level, 0)
    conn.execute(
        """
        UPDATE users
        SET vip_level = ?,
            total_deposit = CASE
                WHEN COALESCE(total_deposit,0) < ? THEN ?
                ELSE total_deposit
            END
        WHERE id = ?
        """,
        (level, min_deposit, min_deposit, user_id)
    )
    conn.commit()
    conn.close()

    add_log(admin["username"], "VIP", status=f"{user['username']} → VIP {level}")
    return jsonify({
        "success": True,
        "message": f"Đã set {user['username']} lên VIP {level}."
    })


@app.route("/admin/api/create-user", methods=["POST"])
def admin_api_create_user():
    admin, error = admin_required_api()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip().lower()
    password = str(data.get("password") or "").strip()
    role = str(data.get("role") or "user").lower().strip()

    if role not in ("user", "admin"):
        role = "user"

    # Chỉ owner tạo admin
    if role == "admin" and admin["role"] != "owner":
        return jsonify({"message": "Chỉ Owner mới tạo được Admin."}), 403

    if not valid_username(username):
        return jsonify({"message": "Tên tài khoản không hợp lệ (3-32 ký tự)."}), 400

    if len(password) < 4:
        return jsonify({"message": "Mật khẩu tối thiểu 4 ký tự."}), 400

    try:
        init_balance = int(data.get("balance") or 0)
        if init_balance < 0:
            init_balance = 0
        if init_balance > 10_000_000:
            init_balance = 10_000_000
    except (TypeError, ValueError):
        init_balance = 0

    try:
        init_db()
    except Exception:
        pass

    conn = get_db_connection()
    existing = conn.execute(
        "SELECT id FROM users WHERE lower(username) = ?",
        (username,)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({"message": "Tên tài khoản đã tồn tại."}), 400

    pw_hash = hash_password(password)
    try:
        conn.execute(
            """
            INSERT INTO users
            (username, password_hash, password_plain, role, balance, locked, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (username, pw_hash, password, role, init_balance, now())
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({"message": f"Lỗi tạo tài khoản: {e}"}), 500

    # Xác nhận đã ghi vào đúng DB
    check = conn.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    conn.close()
    if not check or check["password_hash"] != pw_hash:
        return jsonify({"message": "Tạo xong nhưng không đọc lại được tài khoản. Kiểm tra DB_PATH."}), 500

    try:
        backup_users()
    except Exception:
        pass

    add_log(admin["username"], "TẠO NICK", status=f"{role}: {username}")

    return jsonify({
        "success": True,
        "message": f"Đã tạo {role}: {username} (số dư {init_balance:,}). Có thể đăng nhập game ngay.",
        "username": username,
    })


@app.route("/admin/api/transactions")
def admin_api_transactions():
    admin, error = admin_required_api()
    if error:
        return error

    q = (request.args.get("q") or "").strip().lower()
    ttype = (request.args.get("type") or "").strip().lower()
    status = (request.args.get("status") or "").strip().lower()

    conn = get_db_connection()
    sql = """
        SELECT id, username, type, amount, status, note, created_at
        FROM transactions
        WHERE 1=1
    """
    params = []
    if q:
        sql += " AND lower(username) LIKE ?"
        params.append(f"%{q}%")
    if ttype in ("deposit", "withdraw"):
        sql += " AND type = ?"
        params.append(ttype)
    if status in ("success", "failed", "pending"):
        sql += " AND status = ?"
        params.append(status)

    sql += " ORDER BY id DESC LIMIT 200"
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "username": r["username"],
            "type": r["type"],
            "amount": r["amount"],
            "status": r["status"],
            "note": r["note"] or "",
            "created_at": r["created_at"] or ""
        })

    return jsonify({"transactions": result})


# ============================================================
# ADMIN API - MODIFY Casino
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
            "message": "Số Casino phải khác 0"
        }), 400

    # Owner: không giới hạn | Admin: max 50.000.000 mỗi lần
    if admin["role"] != "owner" and abs(amount) > 50_000_000:
        return jsonify({
            "message": "Admin mỗi lần tối đa 50.000.000 Casino"
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

    # Không cho admin tự đổi Casino của owner.
    if user["role"] == "owner" and admin["role"] != "owner":
        conn.close()
        return jsonify({
            "message": "Admin không thể thay đổi Casino của Owner"
        }), 403

    old_balance = int(user["balance"] or 0)
    new_balance = old_balance + amount

    if new_balance < 0:
        conn.close()
        return jsonify({
            "message": "Không thể để Casino âm"
        }), 400

    conn.execute(
        "UPDATE users SET balance = ? WHERE id = ?",
        (new_balance, user_id)
    )

    conn.commit()
    conn.close()

    add_log(
        admin["username"],
        "ADMIN Casino",
        bet_amount=0,
        win_amount=amount,
        status=f"Đã {'cộng' if amount > 0 else 'trừ'} Casino cho {user['username']}"
    )

    return jsonify({
        "success": True,
        "message": (
            f"Đã {'cộng' if amount > 0 else 'trừ'} "
            f"{abs(amount):,} Casino cho {user['username']}."
        ),
        "old_balance": old_balance,
        "new_balance": new_balance
    })


@app.route("/admin/api/user/luck", methods=["POST"])
def admin_api_set_luck():
    admin, error = admin_required_api()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id"))
        luck = int(data.get("luck_rate"))
    except (TypeError, ValueError):
        return jsonify({"message": "Dữ liệu không hợp lệ"}), 400

    if luck < 0:
        luck = 0
    if luck > 100:
        luck = 100

    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, username, role FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    if not user:
        conn.close()
        return jsonify({"message": "Không tìm thấy tài khoản"}), 404

    if user["role"] == "owner" and admin["role"] != "owner":
        conn.close()
        return jsonify({"message": "Admin không chỉnh Owner"}), 403

    conn.execute(
        "UPDATE users SET luck_rate = ? WHERE id = ?",
        (luck, user_id)
    )
    conn.commit()
    conn.close()

    add_log(admin["username"], "LUCK", status=f"{user['username']} = {luck}%")
    return jsonify({"success": True, "message": f"Tỉ lệ may mắn {user['username']}: {luck}%"})


@app.route("/admin/api/user/scatter", methods=["POST"])
def admin_api_set_scatter():
    admin, error = admin_required_api()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id"))
        scatter = int(data.get("scatter_next") or 0)
    except (TypeError, ValueError):
        return jsonify({"message": "Dữ liệu không hợp lệ"}), 400

    if scatter < 0:
        scatter = 0
    if admin["role"] != "owner" and scatter > 50:
        return jsonify({"message": "Admin tối đa 50 vòng scatter"}), 400

    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, username, role FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    if not user:
        conn.close()
        return jsonify({"message": "Không tìm thấy tài khoản"}), 404

    if user["role"] == "owner" and admin["role"] != "owner":
        conn.close()
        return jsonify({"message": "Admin không chỉnh Owner"}), 403

    conn.execute(
        "UPDATE users SET scatter_next = ? WHERE id = ?",
        (scatter, user_id)
    )
    conn.commit()
    conn.close()

    add_log(admin["username"], "SCATTER", status=f"{user['username']} +{scatter} vòng")
    return jsonify({"success": True, "message": f"Gán {scatter} vòng scatter cho {user['username']}"})


@app.route("/api/me/luck")
def api_me_luck():
    """Game lấy tỉ lệ may mắn + scatter của user đang login."""
    user, error = require_login_api()
    if error:
        return error
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT COALESCE(luck_rate,50) as luck_rate,
               COALESCE(scatter_next,0) as scatter_next
        FROM users WHERE id = ?
        """,
        (user["id"],)
    ).fetchone()
    # Trừ scatter sau khi game dùng (game sẽ gọi consume)
    conn.close()
    return jsonify({
        "luck_rate": int(row["luck_rate"] if row else 50),
        "scatter_next": int(row["scatter_next"] if row else 0)
    })


@app.route("/api/me/scatter/consume", methods=["POST"])
def api_consume_scatter():
    user, error = require_login_api()
    if error:
        return error
    conn = get_db_connection()
    row = conn.execute(
        "SELECT COALESCE(scatter_next,0) as s FROM users WHERE id = ?",
        (user["id"],)
    ).fetchone()
    s = int(row["s"] if row else 0)
    if s > 0:
        conn.execute(
            "UPDATE users SET scatter_next = ? WHERE id = ?",
            (s - 1, user["id"])
        )
        conn.commit()
        s = s - 1
    conn.close()
    return jsonify({"success": True, "scatter_next": s})


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

    init_balance = 00
    try:
        init_balance = int(data.get("balance") or 0)
        if init_balance < 0:
            init_balance = 0
        if init_balance > 10_000_000:
            init_balance = 10_000_000
    except (TypeError, ValueError):
        init_balance = 00

    conn.execute(
        """
        INSERT INTO users
        (username, password_hash, password_plain, role, balance, locked, created_at)
        VALUES (?, ?, ?, 'admin', ?, 0, ?)
        """,
        (username, hash_password(password), password, init_balance, now())
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


@app.route("/api/recent-activity")
def api_recent_activity():
    """Lịch sử hoạt động công khai trên sảnh (che bớt username)."""
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT username, game_name, bet_amount, win_amount, status, created_at
        FROM game_logs
        ORDER BY id DESC
        LIMIT 30
    """).fetchall()
    conn.close()
    out = []
    for r in rows:
        name = r["username"] or ""
        if len(name) > 2:
            mask = name[0] + "***" + name[-1]
        else:
            mask = "***"
        out.append({
            "user": mask,
            "game": r["game_name"] or "",
            "bet": r["bet_amount"] or 0,
            "win": r["win_amount"] or 0,
            "status": r["status"] or "",
            "time": r["created_at"] or ""
        })
    return jsonify({"items": out})


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
