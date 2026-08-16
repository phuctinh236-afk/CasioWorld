# ============================================
# File: ai.py
# Code AI VIP - trợ lý lập trình tự học (TF-IDF, không dùng API AI ngoài)
# + Đăng nhập Google, hệ thống VIP (quota ảnh/file, tên 7 màu, avatar, sửa ảnh)
# + Sidebar: nút mở/đóng menu, "Chat mới", danh sách lịch sử chat, bấm vào xem lại
# ============================================

import os
import io
import json
import uuid
import sqlite3
import datetime
import numpy as np
from flask import (
    Flask, request, jsonify, render_template_string,
    session, redirect, url_for
)
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from authlib.integrations.flask_client import OAuth
from PIL import Image, ImageFilter, ImageEnhance

# ---------- Cấu hình ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AVATAR_DIR = os.path.join(BASE_DIR, "static", "avatars")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
DB_FILE = os.path.join(BASE_DIR, "app.db")
KB_FILE = os.path.join(BASE_DIR, "knowledge_base.json")

MAX_IMAGES_FREE_PER_DAY = 3
MAX_FILES_FREE_PER_DAY = 3

os.makedirs(AVATAR_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "doi-key-nay-truoc-khi-deploy-that")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


# ---------- Database ----------
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id TEXT UNIQUE NOT NULL,
            email TEXT,
            name TEXT,
            avatar_url TEXT,
            is_vip INTEGER DEFAULT 0,
            vip_expire TEXT,
            image_count INTEGER DEFAULT 0,
            file_count INTEGER DEFAULT 0,
            last_reset TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_key TEXT NOT NULL,
            title TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


def today_str():
    return datetime.date.today().isoformat()


def now_str():
    return datetime.datetime.now().isoformat()


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return row


def get_or_create_user(google_id, email, name, picture):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE google_id=?", (google_id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users (google_id, email, name, avatar_url, last_reset) VALUES (?,?,?,?,?)",
            (google_id, email, name, picture, today_str()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE google_id=?", (google_id,)).fetchone()
    conn.close()
    return row


def reset_quota_if_new_day(user_row):
    if user_row["last_reset"] != today_str():
        conn = get_db()
        conn.execute(
            "UPDATE users SET image_count=0, file_count=0, last_reset=? WHERE id=?",
            (today_str(), user_row["id"]),
        )
        conn.commit()
        conn.close()
        return get_user_by_id(user_row["id"])
    return user_row


def is_vip_active(user_row):
    if not user_row["is_vip"]:
        return False
    if user_row["vip_expire"]:
        try:
            expire = datetime.date.fromisoformat(user_row["vip_expire"])
            return expire >= datetime.date.today()
        except ValueError:
            return True
    return True


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    row = get_user_by_id(uid)
    if row is None:
        return None
    return reset_quota_if_new_day(row)


def owner_key():
    """Định danh chủ sở hữu hội thoại: user đăng nhập -> 'u:<id>', khách -> 'g:<uuid ngẫu nhiên>' lưu trong session."""
    user = current_user()
    if user is not None:
        return f"u:{user['id']}"
    if "guest_id" not in session:
        session["guest_id"] = uuid.uuid4().hex
    return f"g:{session['guest_id']}"


# ---------- AI lập trình ----------
class CodeAIVIP:
    def __init__(self):
        self.default_kb = [
            {"question": "bạn tên gì", "answer": "Tôi là Code AI VIP, trợ lý lập trình của riêng bạn."},
            {"question": "bạn làm được gì", "answer": "Tôi giải thích khái niệm lập trình, gỡ lỗi code, và học thêm từ bạn."},
            {"question": "python là gì", "answer": "Python là ngôn ngữ lập trình bậc cao, cú pháp rõ ràng, dùng nhiều trong web, AI, khoa học dữ liệu."},
            {"question": "list và tuple khác nhau thế nào", "answer": "List có thể thay đổi (mutable) dùng [], tuple không thể thay đổi (immutable) dùng ()."},
            {"question": "git là gì", "answer": "Git là hệ thống quản lý phiên bản, theo dõi thay đổi code qua commit, push, pull."},
            {"question": "flask là gì", "answer": "Flask là web framework nhẹ của Python để dựng web server/API nhanh."},
            {"question": "tạm biệt", "answer": "Tạm biệt! Hẹn gặp lại."}
        ]
        self.knowledge_base = self._load_kb()
        self._rebuild_vectors()

    def _load_kb(self):
        if os.path.exists(KB_FILE):
            try:
                with open(KB_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and data:
                        return data
            except Exception:
                pass
        return list(self.default_kb)

    def _save_kb(self):
        try:
            with open(KB_FILE, "w", encoding="utf-8") as f:
                json.dump(self.knowledge_base, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _rebuild_vectors(self):
        self.questions = [i["question"] for i in self.knowledge_base]
        self.answers = [i["answer"] for i in self.knowledge_base]
        self.vectorizer = TfidfVectorizer()
        self.question_vectors = self.vectorizer.fit_transform(self.questions)

    def train(self, pairs):
        for q, a in pairs:
            self.knowledge_base.append({"question": q, "answer": a})
        self._rebuild_vectors()
        self._save_kb()

    def respond(self, text):
        if not text.strip():
            return "Vui lòng nhập câu hỏi."
        vec = self.vectorizer.transform([text])
        sims = cosine_similarity(vec, self.question_vectors).flatten()
        idx = int(np.argmax(sims))
        if sims[idx] > 0.2:
            return self.answers[idx]
        return "Tôi chưa hiểu. Dạy tôi bằng: học|câu hỏi|câu trả lời"

    def learn_from_input(self, text):
        parts = text.split("|")
        if len(parts) == 3 and parts[0].strip().lower() == "học":
            q, a = parts[1].strip(), parts[2].strip()
            if q and a:
                self.train([(q, a)])
                return "Đã học xong, cảm ơn bạn!"
        return None


ai_vip = CodeAIVIP()


# ---------- Auth ----------
@app.route("/login/google")
def login_google():
    redirect_uri = url_for("auth_google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def auth_google_callback():
    token = google.authorize_access_token()
    userinfo = token.get("userinfo") or google.parse_id_token(token)
    google_id = userinfo["sub"]
    email = userinfo.get("email", "")
    name = userinfo.get("name", email or "User")
    picture = userinfo.get("picture", "")
    user = get_or_create_user(google_id, email, name, picture)
    session["user_id"] = user["id"]
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


def user_public_dict(user_row):
    if user_row is None:
        return None
    return {
        "name": user_row["name"],
        "email": user_row["email"],
        "avatar_url": user_row["avatar_url"] or "",
        "is_vip": bool(is_vip_active(user_row)),
        "image_count": user_row["image_count"],
        "file_count": user_row["file_count"],
        "image_limit": MAX_IMAGES_FREE_PER_DAY,
        "file_limit": MAX_FILES_FREE_PER_DAY,
    }


@app.route("/me")
def me():
    return jsonify(user_public_dict(current_user()))


# ---------- Hội thoại (sidebar / lịch sử chat) ----------
def make_title_from_message(text):
    text = text.strip().replace("\n", " ")
    if len(text) > 40:
        text = text[:40].rstrip() + "..."
    return text or "Cuộc trò chuyện mới"


@app.route("/conversations")
def list_conversations():
    ok = owner_key()
    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, created_at FROM conversations WHERE owner_key=? ORDER BY id DESC LIMIT 100",
        (ok,),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/conversations/new", methods=["POST"])
def new_conversation():
    ok = owner_key()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO conversations (owner_key, title, created_at) VALUES (?,?,?)",
        (ok, "Cuộc trò chuyện mới", now_str()),
    )
    conn.commit()
    conv_id = cur.lastrowid
    conn.close()
    return jsonify({"id": conv_id, "title": "Cuộc trò chuyện mới"})


@app.route("/conversations/<int:conv_id>/messages")
def get_messages(conv_id):
    ok = owner_key()
    conn = get_db()
    conv = conn.execute(
        "SELECT * FROM conversations WHERE id=? AND owner_key=?", (conv_id, ok)
    ).fetchone()
    if conv is None:
        conn.close()
        return jsonify({"error": "Không tìm thấy cuộc trò chuyện."}), 404
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id ASC",
        (conv_id,),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/conversations/<int:conv_id>", methods=["DELETE"])
def delete_conversation(conv_id):
    ok = owner_key()
    conn = get_db()
    conv = conn.execute(
        "SELECT * FROM conversations WHERE id=? AND owner_key=?", (conv_id, ok)
    ).fetchone()
    if conv is None:
        conn.close()
        return jsonify({"error": "Không tìm thấy cuộc trò chuyện."}), 404
    conn.execute("DELETE FROM messages WHERE conversation_id=?", (conv_id,))
    conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ---------- Chat (giờ có lưu lịch sử) ----------
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    msg = data.get("message", "")
    conv_id = data.get("conversation_id")
    ok = owner_key()

    conn = get_db()
    if conv_id:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id=? AND owner_key=?", (conv_id, ok)
        ).fetchone()
        if conv is None:
            conn.close()
            return jsonify({"error": "Cuộc trò chuyện không hợp lệ."}), 404
    else:
        cur = conn.execute(
            "INSERT INTO conversations (owner_key, title, created_at) VALUES (?,?,?)",
            (ok, make_title_from_message(msg), now_str()),
        )
        conn.commit()
        conv_id = cur.lastrowid

    learned = ai_vip.learn_from_input(msg)
    reply = learned if learned else ai_vip.respond(msg)

    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?,?,?,?)",
        (conv_id, "user", msg, now_str()),
    )
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?,?,?,?)",
        (conv_id, "ai", reply, now_str()),
    )
    conn.commit()
    conn.close()

    return jsonify({"reply": reply, "conversation_id": conv_id})


# ---------- Upload ảnh / file (có quota) ----------
def check_and_consume_quota(user, kind):
    if user is None:
        return False, "Bạn cần đăng nhập bằng Google để gửi ảnh/file."
    if is_vip_active(user):
        return True, None
    field = "image_count" if kind == "image" else "file_count"
    limit = MAX_IMAGES_FREE_PER_DAY if kind == "image" else MAX_FILES_FREE_PER_DAY
    if user[field] >= limit:
        loai = "ảnh" if kind == "image" else "file"
        return False, (f"Bạn đã gửi {limit} {loai} hôm nay (giới hạn tài khoản thường). "
                        f"Nâng cấp VIP để gửi không giới hạn, hoặc quay lại vào ngày mai.")
    conn = get_db()
    conn.execute(f"UPDATE users SET {field} = {field} + 1 WHERE id=?", (user["id"],))
    conn.commit()
    conn.close()
    return True, None


@app.route("/upload/image", methods=["POST"])
def upload_image():
    user = current_user()
    ok, msg = check_and_consume_quota(user, "image")
    if not ok:
        return jsonify({"error": msg}), 403
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Thiếu file ảnh."}), 400
    filename = f"{user['id']}_{int(datetime.datetime.now().timestamp())}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, filename)
    file.save(path)
    return jsonify({"ok": True, "url": f"/static/uploads/{filename}"})


@app.route("/upload/file", methods=["POST"])
def upload_file():
    user = current_user()
    ok, msg = check_and_consume_quota(user, "file")
    if not ok:
        return jsonify({"error": msg}), 403
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Thiếu file."}), 400
    filename = f"{user['id']}_{int(datetime.datetime.now().timestamp())}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, filename)
    file.save(path)
    return jsonify({"ok": True, "url": f"/static/uploads/{filename}"})


# ---------- Sửa ảnh (Pillow, chỉ VIP) ----------
@app.route("/edit-image", methods=["POST"])
def edit_image():
    user = current_user()
    if user is None or not is_vip_active(user):
        return jsonify({"error": "Tính năng sửa ảnh chỉ dành cho tài khoản VIP."}), 403
    file = request.files.get("file")
    action = request.form.get("action", "grayscale")
    if not file:
        return jsonify({"error": "Thiếu file ảnh."}), 400
    img = Image.open(file.stream).convert("RGB")
    if action == "grayscale":
        img = img.convert("L")
    elif action == "blur":
        img = img.filter(ImageFilter.GaussianBlur(4))
    elif action == "sharpen":
        img = img.filter(ImageFilter.SHARPEN)
    elif action == "brighten":
        img = ImageEnhance.Brightness(img).enhance(1.4)
    elif action == "darken":
        img = ImageEnhance.Brightness(img).enhance(0.7)
    elif action == "rotate":
        img = img.rotate(90, expand=True)
    else:
        return jsonify({"error": "Hành động chỉnh sửa không hợp lệ."}), 400
    filename = f"edit_{user['id']}_{int(datetime.datetime.now().timestamp())}.png"
    path = os.path.join(UPLOAD_DIR, filename)
    img.save(path)
    return jsonify({"ok": True, "url": f"/static/uploads/{filename}"})


# ---------- Tạo ảnh / video / audio (chưa kết nối API tạo sinh) ----------
@app.route("/generate/image", methods=["POST"])
def generate_image():
    user = current_user()
    if user is None or not is_vip_active(user):
        return jsonify({"error": "Tính năng tạo ảnh chỉ dành cho VIP."}), 403
    return jsonify({"error": "Tính năng tạo ảnh bằng AI chưa được kết nối dịch vụ tạo sinh."}), 501


@app.route("/generate/video", methods=["POST"])
def generate_video():
    user = current_user()
    if user is None or not is_vip_active(user):
        return jsonify({"error": "Tính năng tạo video chỉ dành cho VIP."}), 403
    return jsonify({"error": "Tính năng tạo video bằng AI chưa được kết nối dịch vụ tạo sinh."}), 501


@app.route("/generate/audio", methods=["POST"])
def generate_audio():
    user = current_user()
    if user is None or not is_vip_active(user):
        return jsonify({"error": "Tính năng tạo audio chỉ dành cho VIP."}), 403
    return jsonify({"error": "Tính năng tạo audio bằng AI chưa được kết nối dịch vụ tạo sinh."}), 501


# ---------- Avatar tuỳ chỉnh (chỉ VIP) ----------
@app.route("/profile/avatar", methods=["POST"])
def change_avatar():
    user = current_user()
    if user is None or not is_vip_active(user):
        return jsonify({"error": "Chỉ VIP mới được đổi avatar tuỳ chọn."}), 403
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Thiếu file ảnh."}), 400
    ext = os.path.splitext(file.filename)[1] or ".png"
    filename = f"avatar_{user['id']}{ext}"
    path = os.path.join(AVATAR_DIR, filename)
    file.save(path)
    url = f"/static/avatars/{filename}"
    conn = get_db()
    conn.execute("UPDATE users SET avatar_url=? WHERE id=?", (url, user["id"]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "url": url})


# ---------- Kích hoạt VIP thủ công (chưa có cổng thanh toán thật) ----------
def set_vip(user_id, days=30):
    expire = (datetime.date.today() + datetime.timedelta(days=days)).isoformat()
    conn = get_db()
    conn.execute("UPDATE users SET is_vip=1, vip_expire=? WHERE id=?", (expire, user_id))
    conn.commit()
    conn.close()


@app.route("/admin/activate-vip", methods=["POST"])
def admin_activate_vip():
    data = request.get_json(silent=True) or {}
    if data.get("admin_key") != os.environ.get("ADMIN_KEY", "change-me"):
        return jsonify({"error": "Không có quyền."}), 403
    set_vip(data.get("user_id"), int(data.get("days", 30)))
    return jsonify({"ok": True})


# ---------- Giao diện ----------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Code AI VIP</title>
<style>
  :root {
    --bg:#1a1a19; --panel:#232322; --sidebar:#181817; --bubble-user:#3a3a38; --bubble-ai:#2b2b29;
    --accent:#d97757; --text:#ece9e6; --muted:#9a968f; --border:#333;
  }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    background:var(--bg); color:var(--text); height:100vh; display:flex; overflow:hidden; }

  /* ---- Sidebar ---- */
  #sidebar {
    width:270px; background:var(--sidebar); border-right:1px solid var(--border);
    display:flex; flex-direction:column; flex-shrink:0;
    position:fixed; top:0; bottom:0; left:0; z-index:50;
    transform:translateX(-100%); transition:transform 0.2s ease;
  }
  #sidebar.open { transform:translateX(0); }
  #overlay {
    position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:40;
    display:none;
  }
  #overlay.show { display:block; }
  .sidebar-top { padding:16px; display:flex; align-items:center; justify-content:space-between; }
  .sidebar-top .brand { font-weight:700; font-size:16px; }
  .new-chat-btn {
    margin:0 16px 12px; padding:10px 12px; background:var(--panel); border:1px solid var(--border);
    border-radius:10px; color:var(--text); display:flex; align-items:center; gap:8px;
    cursor:pointer; font-size:14px;
  }
  .sidebar-section-title { padding:6px 16px; font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:0.05em; }
  #conv-list { flex:1; overflow-y:auto; padding:0 8px; }
  .conv-item {
    padding:10px 10px; border-radius:8px; font-size:13.5px; color:var(--text);
    cursor:pointer; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    display:flex; align-items:center; justify-content:space-between; gap:6px;
  }
  .conv-item:hover { background:var(--panel); }
  .conv-item.active { background:var(--bubble-user); }
  .conv-item .del-btn { opacity:0; background:none; border:none; color:var(--muted); cursor:pointer; font-size:13px; }
  .conv-item:hover .del-btn { opacity:1; }
  .sidebar-bottom { border-top:1px solid var(--border); padding:12px 16px; }

  /* ---- Main ---- */
  #main { flex:1; display:flex; flex-direction:column; margin-left:0; height:100vh; }
  header { padding:12px 16px; border-bottom:1px solid var(--border); display:flex; align-items:center;
    justify-content:space-between; gap:10px; }
  .brand-row { display:flex; align-items:center; gap:10px; }
  .hamburger { background:none; border:none; color:var(--text); font-size:20px; cursor:pointer; padding:4px 6px; }
  .logo { width:26px; height:26px; border-radius:8px; background:var(--accent);
    display:flex; align-items:center; justify-content:center; font-weight:bold; color:#1a1a19; font-size:13px; }
  header h1 { font-size:15px; margin:0; font-weight:600; }
  header span.sub { font-size:11.5px; color:var(--muted); margin-left:4px; display:none; }
  @media (min-width:520px) { header span.sub { display:inline; } }

  .user-box { display:flex; align-items:center; gap:8px; }
  .avatar-img { width:28px; height:28px; border-radius:50%; object-fit:cover; background:#444; }
  .rainbow-name { font-weight:700; font-size:13px;
    background:linear-gradient(90deg,#ff4d4d,#ffa64d,#ffe14d,#4dff88,#4dd2ff,#4d79ff,#c14dff);
    background-size:300% 100%; -webkit-background-clip:text; background-clip:text; color:transparent;
    animation:rainbow-move 4s linear infinite; }
  @keyframes rainbow-move { 0%{background-position:0% 50%} 100%{background-position:300% 50%} }
  .vip-badge { font-size:10px; font-weight:700; color:#1a1a19; background:#f5c542; padding:2px 6px; border-radius:6px; margin-left:4px; }
  .plain-name { font-size:13px; color:var(--text); }
  .login-btn { background:var(--accent); color:#1a1a19; border:none; padding:7px 12px; border-radius:8px;
    font-size:12.5px; font-weight:600; cursor:pointer; text-decoration:none; }

  #chat-box { flex:1; overflow-y:auto; padding:20px; max-width:760px; width:100%; margin:0 auto; }
  .row { display:flex; margin-bottom:16px; }
  .row.user { justify-content:flex-end; }
  .row.ai { justify-content:flex-start; }
  .bubble { max-width:78%; padding:12px 16px; border-radius:14px; line-height:1.5; font-size:14.5px; white-space:pre-wrap; }
  .row.user .bubble { background:var(--bubble-user); border-bottom-right-radius:4px; }
  .row.ai .bubble { background:var(--bubble-ai); border:1px solid var(--border); border-bottom-left-radius:4px; }
  .avatar { width:26px; height:26px; border-radius:6px; background:var(--accent); color:#1a1a19;
    display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:bold; margin-right:10px; flex-shrink:0; }

  #input-area { border-top:1px solid var(--border); padding:12px 16px 18px; }
  #input-inner { max-width:760px; margin:0 auto; display:flex; align-items:flex-end; gap:8px;
    background:var(--panel); border:1px solid var(--border); border-radius:16px; padding:10px 12px; }
  #user-input { flex:1; resize:none; border:none; outline:none; background:transparent; color:var(--text);
    font-size:14.5px; max-height:140px; font-family:inherit; }
  .icon-btn { background:transparent; border:none; color:var(--muted); cursor:pointer; font-size:16px; }
  button#send-btn { background:var(--accent); border:none; color:#1a1a19; font-weight:600; padding:8px 16px;
    border-radius:10px; cursor:pointer; font-size:13.5px; }
  .hint { text-align:center; color:var(--muted); font-size:11px; margin-top:8px; max-width:760px; margin-left:auto; margin-right:auto; }
</style>
</head>
<body>

<div id="overlay" onclick="closeSidebar()"></div>

<div id="sidebar">
  <div class="sidebar-top">
    <div class="brand">Code AI VIP</div>
    <button class="hamburger" onclick="closeSidebar()">✕</button>
  </div>
  <div class="new-chat-btn" onclick="startNewChat()">＋ Chat mới</div>
  <div class="sidebar-section-title">Gần đây</div>
  <div id="conv-list"></div>
  <div class="sidebar-bottom" id="sidebar-user-box"></div>
</div>

<div id="main">
  <header>
    <div class="brand-row">
      <button class="hamburger" onclick="openSidebar()">☰</button>
      <div class="logo">C</div>
      <h1>Code AI VIP <span class="sub">trợ lý lập trình tự học</span></h1>
    </div>
    <div class="user-box" id="user-box">
      <a class="login-btn" href="/login/google">Đăng nhập Google</a>
    </div>
  </header>

  <div id="chat-box"></div>

  <div id="input-area">
    <div id="input-inner">
      <button class="icon-btn" title="Gửi ảnh/file" onclick="document.getElementById('file-input').click()">📎</button>
      <input type="file" id="file-input" style="display:none" onchange="uploadPickedFile()">
      <textarea id="user-input" rows="1" placeholder="Nhắn cho Code AI VIP..."></textarea>
      <button id="send-btn" onclick="sendMessage()">Gửi</button>
    </div>
    <div class="hint" id="quota-hint">Đang tải thông tin tài khoản...</div>
  </div>
</div>

<script>
const chatBox = document.getElementById('chat-box');
const input = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const userBox = document.getElementById('user-box');
const sidebarUserBox = document.getElementById('sidebar-user-box');
const quotaHint = document.getElementById('quota-hint');
const sidebar = document.getElementById('sidebar');
const overlay = document.getElementById('overlay');
const convList = document.getElementById('conv-list');

let ME = null;
let CURRENT_CONV_ID = null;

function openSidebar() { sidebar.classList.add('open'); overlay.classList.add('show'); loadConversations(); }
function closeSidebar() { sidebar.classList.remove('open'); overlay.classList.remove('show'); }

function addBubble(text, who) {
  const row = document.createElement('div');
  row.className = 'row ' + who;
  if (who === 'ai') {
    const avatar = document.createElement('div');
    avatar.className = 'avatar'; avatar.textContent = 'C';
    row.appendChild(avatar);
  }
  const bubble = document.createElement('div');
  bubble.className = 'bubble'; bubble.textContent = text;
  row.appendChild(bubble);
  chatBox.appendChild(row);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function clearChat() {
  chatBox.innerHTML = '';
  addBubble('Chào bạn! Hỏi mình về lập trình, hoặc dạy mình bằng: học|câu hỏi|câu trả lời', 'ai');
}

async function loadMe() {
  const res = await fetch('/me');
  ME = await res.json();
  renderUserBox();
}

function renderUserBox() {
  if (!ME || !ME.name) {
    const html = '<a class="login-btn" href="/login/google">Đăng nhập Google</a>';
    userBox.innerHTML = html;
    sidebarUserBox.innerHTML = html;
    quotaHint.textContent = 'Đăng nhập để gửi ảnh/file cho AI.';
    return;
  }
  const nameClass = ME.is_vip ? 'rainbow-name' : 'plain-name';
  const badge = ME.is_vip ? '<span class="vip-badge">VIP</span>' : '';
  const avatarImg = ME.avatar_url ? `<img class="avatar-img" src="${ME.avatar_url}">` : '';
  const box = `
    ${avatarImg}
    <span class="${nameClass}">${ME.name}</span>${badge}
    <a href="/logout" class="login-btn" style="background:#3a3a38;color:#ece9e6;">Đăng xuất</a>
  `;
  userBox.innerHTML = box;
  sidebarUserBox.innerHTML = box;
  quotaHint.textContent = ME.is_vip
    ? 'Tài khoản VIP: gửi ảnh/file không giới hạn.'
    : `Ảnh: ${ME.image_count}/${ME.image_limit} hôm nay · File: ${ME.file_count}/${ME.file_limit} hôm nay`;
}

async function loadConversations() {
  const res = await fetch('/conversations');
  const list = await res.json();
  convList.innerHTML = '';
  list.forEach(c => {
    const item = document.createElement('div');
    item.className = 'conv-item' + (c.id === CURRENT_CONV_ID ? ' active' : '');
    item.innerHTML = `<span style="overflow:hidden;text-overflow:ellipsis;">${c.title}</span>
                       <button class="del-btn" onclick="event.stopPropagation();deleteConv(${c.id})">🗑</button>`;
    item.onclick = () => openConversation(c.id);
    convList.appendChild(item);
  });
}

async function openConversation(id) {
  CURRENT_CONV_ID = id;
  const res = await fetch(`/conversations/${id}/messages`);
  const msgs = await res.json();
  chatBox.innerHTML = '';
  msgs.forEach(m => addBubble(m.content, m.role === 'user' ? 'user' : 'ai'));
  closeSidebar();
}

async function deleteConv(id) {
  await fetch(`/conversations/${id}`, { method: 'DELETE' });
  if (id === CURRENT_CONV_ID) { CURRENT_CONV_ID = null; clearChat(); }
  loadConversations();
}

function startNewChat() {
  CURRENT_CONV_ID = null;
  clearChat();
  closeSidebar();
}

async function sendMessage() {
  const message = input.value.trim();
  if (!message) return;
  addBubble(message, 'user');
  input.value = ''; input.style.height = 'auto';
  sendBtn.disabled = true;
  try {
    const response = await fetch('/chat', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ message, conversation_id: CURRENT_CONV_ID })
    });
    const data = await response.json();
    addBubble(data.reply, 'ai');
    if (data.conversation_id) CURRENT_CONV_ID = data.conversation_id;
  } catch (e) {
    addBubble('Lỗi kết nối tới server.', 'ai');
  } finally {
    sendBtn.disabled = false;
  }
}

async function uploadPickedFile() {
  const fileInput = document.getElementById('file-input');
  const file = fileInput.files[0];
  if (!file) return;
  const isImage = file.type.startsWith('image/');
  const endpoint = isImage ? '/upload/image' : '/upload/file';
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(endpoint, { method: 'POST', body: form });
  const data = await res.json();
  if (data.error) {
    addBubble('⚠️ ' + data.error, 'ai');
  } else {
    addBubble('Đã gửi: ' + file.name, 'user');
    await loadMe();
  }
  fileInput.value = '';
}

input.addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
input.addEventListener('input', function() {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 140) + 'px';
});

clearChat();
loadMe();
loadConversations();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ============================================
# HƯỚNG DẪN TRIỂN KHAI
# 1. requirements.txt cần đủ:
#       flask
#       scikit-learn
#       numpy
#       pillow
#       authlib
#       requests
#       gunicorn
#
# 2. Biến môi trường trên Render:
#       GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET (từ Google Cloud Console,
#         redirect URI: https://<domain>/auth/google/callback)
#       SECRET_KEY (chuỗi ngẫu nhiên dài)
#       ADMIN_KEY (mật khẩu để tự kích hoạt VIP qua /admin/activate-vip)
#
# 3. Lịch sử chat được lưu theo "chủ sở hữu":
#    - Đã đăng nhập Google -> gắn với tài khoản, xem lại được ở bất kỳ máy nào đã đăng nhập.
#    - Chưa đăng nhập (khách) -> gắn với 1 session cookie tạm, mất khi xoá cookie/trình duyệt khác.
#
# 4. Trên Render free tier, ổ đĩa (app.db, ảnh upload) có thể bị xoá khi
#    deploy lại. Muốn giữ lịch sử chat vĩnh viễn, cần gắn Render Disk
#    hoặc chuyển database sang PostgreSQL.
# ============================================
