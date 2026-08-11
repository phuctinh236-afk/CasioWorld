import os
import random
import string
import sqlite3
import traceback
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, jsonify, url_for, send_from_directory
from jinja2 import TemplateNotFound

# =========================================================
# TỰ ĐỘNG CHẠY BOT.PY NGẦM KHI SERVER KHỞI ĐỘNG TRÊN RENDER
# =========================================================
if os.environ.get("RENDER"):
    try:
        subprocess.Popen(["python", "bot.py"])
        print(">>> Đã kích hoạt bot.py chạy ngầm trên Render thành công!")
    except Exception as e:
        print(f">>> Lỗi khi khởi chạy bot.py: {e}")

app = Flask(__name__)
app.secret_key = 'casio_world_secret_key_123'
app.config['DEBUG'] = True

payment_orders = {}
error_logs = []

# =========================================================
# KHO TRUY VẤN VÀ KHỞI TẠO CƠ SỞ DỮ LIỆU (SQLITE DB)
# =========================================================
DB_NAME = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Bảng 1: Quản lý người dùng
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 500000,
            role TEXT DEFAULT 'user'
        )
    ''')
    
    # Bảng 2: Quản lý đơn nạp tiền
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            amount REAL NOT NULL,
            code TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'PENDING',
            created_at TEXT NOT NULL
        )
    ''')
    
    # Bảng 3: Giám sát trò chơi (Realtime Game Logs)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            game_name TEXT NOT NULL,
            bet_amount REAL DEFAULT 0,
            win_amount REAL DEFAULT 0,
            is_jackpot INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Đang cược',
            created_at TEXT NOT NULL
        )
    ''')
    
    # Khởi tạo sẵn tài khoản Admin/Owner mặc định
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, balance, role) VALUES ('admin', 'admin123', 99999999, 'owner')")
    
    conn.commit()
    conn.close()

init_db()

# =========================================================
# BỘ XỬ LÝ LỖI & MẪU GIAO DIỆN DỰ PHÒNG
# =========================================================
def log_error(err_msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    error_logs.insert(0, {"time": timestamp, "detail": err_msg})
    if len(error_logs) > 50:
        error_logs.pop()

def render_safe(template_name, **kwargs):
    try:
        return render_template(template_name, **kwargs)
    except TemplateNotFound:
        log_error(f"Thiếu file giao diện: {template_name}")
        title = template_name.replace('.html', '').replace('_', ' ').upper()
        return f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>TX68 - {title}</title>
            <style>
                body {{ background: #0f172a; color: #f8fafc; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; text-align: center; }}
                .container {{ max-width: 450px; margin: 60px auto; background: #1e293b; padding: 30px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.4); border: 1px solid #334155; }}
                h2 {{ color: #cca352; margin-bottom: 15px; font-size: 22px; }}
                p {{ color: #94a3b8; font-size: 14px; line-height: 1.6; }}
                .btn {{ display: inline-block; margin-top: 25px; background: #cca352; color: #131521; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>✨ {title}</h2>
                <p>Game/Khu vực này đang được cập nhật thêm trên hệ thống TX68.</p>
                <a href="/" class="btn">⬅ Quay lại Trang chủ</a>
            </div>
        </body>
        </html>
        """

# =========================================================
# ROUTE TRANG CHỦ & ROUTE NỀN TẢNG
# =========================================================

@app.route('/')
def index():
    return render_safe('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        conn.close()
        
        if user:
            session['username'] = user['username']
            session['role'] = user['role']
            session['balance'] = user['balance']
            if user['role'] in ['admin', 'owner']:
                return redirect('/admin')
            return redirect('/')
        else:
            return render_safe('login.html', error="Sai tài khoản hoặc mật khẩu!")
            
    return render_safe('login.html')

@app.route('/play/<game_name>')
def play_game_by_name(game_name):
    username = session.get('username', request.args.get('username', 'GUEST'))
    return redirect(f"/static/games/{game_name}/index.html?username={username}")

# [FIX] Route play_game dự phòng cho template Jinja
@app.route('/play_game')
def play_game():
    return redirect('/')

# [FIX LỖI BuildError url_for('profile')]
@app.route('/profile')
def profile():
    return render_safe('profile.html')

# [FIX LỖI 404 /favicon.ico]
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

@app.route('/ktraloibug')
def ktraloibug():
    logs_html = ""
    if not error_logs:
        logs_html = "<p style='color: #4ade80; font-size: 16px;'>🎉 Chưa phát hiện lỗi nào gần đây.</p>"
    else:
        for idx, item in enumerate(error_logs, 1):
            logs_html += f"""
            <div style="background: #1e293b; border-left: 4px solid #ef4444; padding: 15px; margin-bottom: 15px; border-radius: 6px; text-align: left;">
                <span style="color: #38bdf8; font-weight: bold;">#{idx} [{item['time']}]</span>
                <pre style="color: #fca5a5; margin-top: 8px; white-space: pre-wrap; font-family: monospace; font-size: 13px;">{item['detail']}</pre>
            </div>
            """

    return f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TX68 - Kiểm Tra Lỗi</title>
        <style>
            body {{ background: #0f172a; color: #f8fafc; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; text-align: center; }}
            .wrapper {{ max-width: 800px; margin: 30px auto; background: #090d16; padding: 30px; border-radius: 12px; border: 1px solid #1e293b; }}
            h2 {{ color: #f87171; margin-bottom: 5px; }}
            .btn {{ background: #cca352; color: #131521; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 14px; display: inline-block; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="wrapper">
            <h2>🛠️ HỆ THỐNG GIÁM SÁT LỖI TX68 (/ktraloibug)</h2>
            {logs_html}
            <a href="/" class="btn">⬅ Về Trang Chủ</a>
        </div>
    </body>
    </html>
    """

@app.errorhandler(404)
def not_found_error(error):
    log_error(f"Lỗi 404 - Không tìm thấy: {request.path}")
    return redirect('/')

@app.errorhandler(500)
@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    log_error(tb)
    return f"""
    <div style="background:#0f172a; color:#ef4444; padding:30px; font-family:sans-serif; text-align:center; min-height:100vh;">
        <h2>⚠️ Đã xảy ra lỗi hệ thống (500)</h2>
        <p style="color:#94a3b8;">Hệ thống đã ghi nhận. Xem chi tiết tại <a href="/ktraloibug" style="color:#cca352;">/ktraloibug</a></p>
        <a href="/" style="background:#cca352; color:#111; padding:10px 20px; border-radius:8px; text-decoration:none; font-weight:bold; display:inline-block; margin-top:15px;">Thử lại trang chủ</a>
    </div>
    """, 500

@app.context_processor
def inject_defaults():
    username = session.get('username', 'GUEST')
    
    conn = get_db_connection()
    user_row = conn.execute("SELECT balance, role FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    
    balance_val = user_row['balance'] if user_row else session.get('balance', 500000)
    user_role = user_row['role'] if user_row else 'user'
    
    user_data = {
        'id': 8386888, 'user_id': 8386888, 'username': username,
        'points': balance_val, 'money': balance_val, 'vip': 1, 'vip_level': 1,
        'balance': balance_val, 'phone': '09******88', 'bank_name': 'TECHCOMBANK',
        'bank_account': '8992362013', 'account_name': 'LỶ KIM HẰNG', 'role': user_role
    }
    return dict(user=user_data, current_user=user_data, username=username, points=balance_val, balance=balance_val, money=balance_val, vip=1, vip_level=1, role=user_role)

def generate_memo():
    return f"chuyen tien TX68{''.join(random.choices(string.ascii_uppercase + string.digits, k=7))}"
    # =========================================================
# HỆ THỐNG PANEL ADMIN CÁC ROUTE & API (CONTROL PANEL)
# =========================================================

@app.route('/admin')
@app.route('/admin/dashboard')
def admin_panel():
    username = session.get('username')
    conn = get_db_connection()
    user = conn.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not user or user['role'] not in ['owner', 'admin']:
        return f"""
        <div style="background:#0f172a; color:#f87171; text-align:center; padding:50px; font-family:sans-serif;">
            <h2>🚫 Quyền truy cập bị từ chối!</h2>
            <p style="color:#94a3b8;">Bạn cần đăng nhập bằng tài khoản Admin/Owner để vào trang này.</p>
            <a href="/login" style="background:#cca352; color:#000; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold;">Đăng Nhập Quản Trị</a>
        </div>
        """, 403

    return f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TX68 - ADMIN CONTROL PANEL</title>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif; }}
            body {{ background: #090d16; color: #f8fafc; padding: 20px; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; background: #1e293b; padding: 15px 20px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 20px; }}
            h1 {{ color: #cca352; font-size: 20px; }}
            .badge {{ background: #ef4444; color: #fff; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; }}
            .section {{ background: #131b2e; padding: 20px; border-radius: 12px; border: 1px solid #1e293b; margin-bottom: 25px; }}
            h2 {{ color: #38bdf8; font-size: 16px; margin-bottom: 15px; border-bottom: 1px solid #334155; padding-bottom: 8px; }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }}
            th, td {{ padding: 12px; border-bottom: 1px solid #1e293b; }}
            th {{ background: #1e293b; color: #94a3b8; }}
            .status-pending {{ color: #f59e0b; font-weight: bold; }}
            .status-success {{ color: #10b981; font-weight: bold; }}
            .status-fail {{ color: #ef4444; font-weight: bold; }}
            .jackpot-alert {{ color: #f59e0b; font-weight: bold; animation: pulse 1s infinite; }}
            @keyframes pulse {{ 50% {{ opacity: 0.4; }} }}
            .btn {{ padding: 6px 12px; border-radius: 6px; border: none; font-weight: bold; cursor: pointer; font-size: 12px; margin-right: 5px; }}
            .btn-approve {{ background: #10b981; color: #fff; }}
            .btn-reject {{ background: #ef4444; color: #fff; }}
            .form-input {{ padding: 8px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; width: 180px; margin-right: 10px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🀄 BẢNG QUẢN TRỊ TỔNG TX68</h1>
            <div>Tài khoản: <b>{username}</b> <span class="role-badge badge">OWNER</span></div>
        </div>

        <div class="section">
            <h2>💵 QUẢN LÝ ĐƠN NẠP TIỀN (THỜI GIAN REALTIME)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Mã GD</th>
                        <th>Người Nạp</th>
                        <th>Số Tiền</th>
                        <th>Thời Gian</th>
                        <th>Trạng Thái</th>
                        <th>Thao Tác</th>
                    </tr>
                </thead>
                <tbody id="deposit-rows">
                    <tr><td colspan="6" style="text-align:center;">Đang tải dữ liệu đơn nạp...</td></tr>
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>🎰 GIÁM SÁT NGƯỜI CHƠI (GAME, CƯỢC, THẮNG/THUA, NỔ HŨ)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Thời Gian</th>
                        <th>Tài Khoản</th>
                        <th>Tựa Game</th>
                        <th>Tiền Cược</th>
                        <th>Tiền Thắng</th>
                        <th>Nổ Hũ?</th>
                        <th>Trạng Thái</th>
                    </tr>
                </thead>
                <tbody id="game-rows">
                    <tr><td colspan="7" style="text-align:center;">Đang tải danh sách cược...</td></tr>
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>👤 QUẢN LÝ NGƯỜI DÙNG & CỘNG TIỀN</h2>
            <div style="margin-bottom: 15px;">
                <input type="text" id="target-user" placeholder="Tên tài khoản" class="form-input">
                <input type="number" id="mod-amount" placeholder="Số tiền cộng (+)/trừ (-)" class="form-input">
                <button class="btn btn-approve" onclick="modifyBalance()">Xác Nhận Thay Đổi Số Dư</button>
            </div>
        </div>

        <script>
            async function fetchDeposits() {{
                const res = await fetch('/admin/api/deposits');
                const data = await res.json();
                let html = '';
                if(data.length === 0) {{
                    html = '<tr><td colspan="6" style="text-align:center; color:#94a3b8;">Chưa có đơn nạp nào.</td></tr>';
                }} else {{
                    data.forEach(item => {{
                        let statusClass = item.status === 'SUCCESS' ? 'status-success' : (item.status === 'FAILED' ? 'status-fail' : 'status-pending');
                        let actions = item.status === 'PENDING' ? 
                            `<button class="btn btn-approve" onclick="updateDeposit('${{item.code}}', 'SUCCESS')">Duyệt</button>
                             <button class="btn btn-reject" onclick="updateDeposit('${{item.code}}', 'FAILED')">Hủy</button>` : 'Đã xử lý';
                        
                        html += `<tr>
                            <td><code>${{item.code}}</code></td>
                            <td><b>${{item.username}}</b></td>
                            <td style="color:#10b981; font-weight:bold;">${{Number(item.amount).toLocaleString()}} VNĐ</td>
                            <td>${{item.created_at}}</td>
                            <td class="${{statusClass}}">${{item.status}}</td>
                            <td>${{actions}}</td>
                        </tr>`;
                    }});
                }}
                document.getElementById('deposit-rows').innerHTML = html;
            }}

            async function updateDeposit(code, status) {{
                await fetch('/admin/api/deposit/update', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ code, status }})
                }});
                fetchDeposits();
            }}

            async function fetchGameLogs() {{
                const res = await fetch('/admin/api/gamelogs');
                const data = await res.json();
                let html = '';
                if(data.length === 0) {{
                    html = '<tr><td colspan="7" style="text-align:center; color:#94a3b8;">Chưa có dữ liệu cược.</td></tr>';
                }} else {{
                    data.forEach(item => {{
                        let isJp = item.is_jackpot === 1 ? '<span class="jackpot-alert">🔥 NỔ HŨ 🔥</span>' : 'Bình thường';
                        let winColor = item.win_amount > 0 ? '#10b981' : '#ef4444';
                        html += `<tr>
                            <td>${{item.created_at}}</td>
                            <td><b>${{item.username}}</b></td>
                            <td style="color:#38bdf8;">${{item.game_name}}</td>
                            <td>${{Number(item.bet_amount).toLocaleString()}}</td>
                            <td style="color:${{winColor}}; font-weight:bold;">${{Number(item.win_amount).toLocaleString()}}</td>
                            <td>${{isJp}}</td>
                            <td>${{item.status}}</td>
                        </tr>`;
                    }});
                }}
                document.getElementById('game-rows').innerHTML = html;
            }}

            async function modifyBalance() {{
                const username = document.getElementById('target-user').value;
                const amount = document.getElementById('mod-amount').value;
                if(!username || !amount) return alert("Vui lòng nhập đủ thông tin!");
                
                const res = await fetch('/admin/api/user/balance', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ username, amount: parseFloat(amount) }})
                }});
                const data = await res.json();
                alert(data.message);
            }}

            setInterval(() => {{
                fetchDeposits();
                fetchGameLogs();
            }}, 3000);

            fetchDeposits();
            fetchGameLogs();
        </script>
    </body>
    </html>
    """

@app.route('/admin/api/deposits')
def api_get_deposits():
    conn = get_db_connection()
    deposits = conn.execute("SELECT * FROM deposits ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(row) for row in deposits])

@app.route('/admin/api/deposit/update', methods=['POST'])
def api_update_deposit():
    data = request.json or {}
    code = data.get('code')
    status = data.get('status')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    dep = cursor.execute("SELECT username, amount, status FROM deposits WHERE code = ?", (code,)).fetchone()
    
    if dep and dep['status'] == 'PENDING':
        cursor.execute("UPDATE deposits SET status = ? WHERE code = ?", (status, code))
        if status == 'SUCCESS':
            cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (dep['amount'], dep['username']))
        conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/admin/api/gamelogs')
def api_get_gamelogs():
    conn = get_db_connection()
    logs = conn.execute("SELECT * FROM game_logs ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(row) for row in logs])

@app.route('/admin/api/user/balance', methods=['POST'])
def api_modify_user_balance():
    data = request.json or {}
    username = data.get('username')
    amount = data.get('amount', 0)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    user = cursor.execute("SELECT balance FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"message": "Tài khoản không tồn tại!"}), 400
        
    cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount, username))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Đã chỉnh sửa số dư của {username} thành công!"})

@app.route('/api/game/log', methods=['POST'])
def api_game_log():
    try:
        data = request.json or {}
        username = data.get('username') or session.get('username', 'GUEST')
        game_name = data.get('game_name', 'Trò chơi')
        bet_amount = float(data.get('bet_amount', 0))
        win_amount = float(data.get('win_amount', 0))
        is_jackpot = 1 if data.get('is_jackpot') else 0
        status = data.get('status', 'Hoàn tất')
        created_at = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")

        if username != 'GUEST':
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO game_logs (username, game_name, bet_amount, win_amount, is_jackpot, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (username, game_name, bet_amount, win_amount, is_jackpot, status, created_at))
            
            net_change = win_amount - bet_amount
            cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (net_change, username))
            
            conn.commit()
            conn.close()

        return jsonify({"success": True, "message": "Đã lưu lịch sử cược"})
    except Exception as e:
        log_error(f"Lỗi API Game Log: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
    # =========================================================
# GIAO DIỆN APP QUẢN TRỊ MOBILE WEBVIEW (/admin-app)
# =========================================================

@app.route('/admin-app')
def admin_app_page():
    return f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Admin TX68 App</title>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
            body {{ background: #0b1120; color: #f8fafc; height: 100vh; overflow: hidden; display: flex; flex-direction: column; }}
            .topbar {{ height: 50px; background: #0f172a; border-bottom: 1px solid #1e293b; display: flex; align-items: center; justify-content: space-between; padding: 0 15px; flex-shrink: 0; }}
            .topbar h1 {{ font-size: 16px; color: #fff; font-weight: 600; }}
            .star-icon {{ color: #22c55e; font-size: 20px; }}
            .app-container {{ display: flex; flex: 1; overflow: hidden; }}
            .sidebar {{ width: 220px; background: #0f172a; border-right: 1px solid #1e293b; padding: 15px 10px; display: flex; flex-direction: column; flex-shrink: 0; }}
            .sidebar-header {{ font-size: 11px; color: #475569; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 12px; padding-left: 8px; }}
            .nav-btn {{ display: flex; align-items: center; gap: 10px; padding: 10px; border-radius: 6px; color: #94a3b8; font-size: 13px; text-decoration: none; font-weight: 500; cursor: pointer; margin-bottom: 4px; }}
            .nav-btn.active {{ background: #1e293b; color: #f8fafc; font-weight: 600; }}
            .content {{ flex: 1; padding: 15px; overflow-y: auto; background: #0b1120; }}
            .card {{ background: #131c2e; border-radius: 8px; border: 1px solid #1e2d4a; padding: 12px; margin-bottom: 15px; }}
            .card-title {{ font-size: 14px; font-weight: bold; color: #cca352; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; }}
            th, td {{ padding: 8px 6px; border-bottom: 1px solid #1e2d4a; }}
            th {{ color: #64748b; font-weight: 600; font-size: 11px; background: #0f172a; }}
            .badge {{ padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; display: inline-block; }}
            .badge-success {{ background: rgba(34, 197, 94, 0.15); color: #22c55e; border: 1px solid #22c55e; }}
            .badge-pending {{ background: rgba(234, 179, 8, 0.15); color: #eab308; border: 1px solid #eab308; }}
            .badge-failed {{ background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid #ef4444; }}
            .action-btn {{ padding: 4px 8px; border-radius: 4px; border: none; font-size: 10px; font-weight: bold; cursor: pointer; margin-right: 2px; }}
            .btn-ok {{ background: #22c55e; color: #000; }}
            .btn-no {{ background: #ef4444; color: #fff; }}
            input {{ width: 100%; padding: 8px; background: #0f172a; border: 1px solid #1e2d4a; border-radius: 6px; color: #fff; font-size: 12px; margin-bottom: 8px; outline: none; }}
            button.submit-btn {{ width: 100%; padding: 9px; background: #cca352; border: none; border-radius: 6px; font-weight: bold; color: #000; font-size: 12px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="topbar">
            <h1>Admin TX68</h1>
            <span class="star-icon">★</span>
        </div>

        <div class="app-container">
            <div class="sidebar">
                <div class="sidebar-header">TX68 MANAGEMENT</div>
                <div class="nav-btn active" onclick="showTab('tab-home', this)">🏠 Trang Chủ (Online)</div>
                <div class="nav-btn" onclick="showTab('tab-deposits', this)">💳 Lịch Sử Nạp / Rút</div>
                <div class="nav-btn" onclick="showTab('tab-gamelogs', this)">📊 Lịch Sử Thắng / Thua</div>
                <div class="nav-btn" onclick="showTab('tab-balance', this)">⚙️ Cộng / Trừ Số Dư</div>
            </div>

            <div class="content">
                <div id="tab-home">
                    <div class="card">
                        <div class="card-title">
                            <span>🟢 Người Dùng Hoạt Động Realtime</span>
                            <span id="online-count" style="color:#22c55e;">0 Onl</span>
                        </div>
                        <table>
                            <thead>
                                <tr>
                                    <th>Tài khoản</th>
                                    <th>Số dư</th>
                                    <th>Trạng thái</th>
                                </tr>
                            </thead>
                            <tbody id="users-table">
                                <tr><td colspan="3" style="text-align:center;">Đang tải...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div id="tab-deposits" style="display:none;">
                    <div class="card">
                        <div class="card-title">💳 Quản Lý Đơn Nạp / Rút</div>
                        <table>
                            <thead>
                                <tr>
                                    <th>Mã GD</th>
                                    <th>User</th>
                                    <th>Số tiền</th>
                                    <th>Trạng thái</th>
                                    <th>Duyệt</th>
                                </tr>
                            </thead>
                            <tbody id="deposits-table">
                                <tr><td colspan="5" style="text-align:center;">Đang tải...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div id="tab-gamelogs" style="display:none;">
                    <div class="card">
                        <div class="card-title">📊 Nhật Ký Đặt Cược</div>
                        <table>
                            <thead>
                                <tr>
                                    <th>User</th>
                                    <th>Game</th>
                                    <th>Cược</th>
                                    <th>Thắng</th>
                                </tr>
                            </thead>
                            <tbody id="logs-table">
                                <tr><td colspan="4" style="text-align:center;">Đang tải...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div id="tab-balance" style="display:none;">
                    <div class="card">
                        <div class="card-title">⚙️ Điều Chỉnh Số Dư</div>
                        <input type="text" id="target-username" placeholder="Nhập Tên Tài Khoản">
                        <input type="number" id="target-amount" placeholder="Nhập số tiền (+Cộng / -Trừ)">
                        <button class="submit-btn" onclick="executeBalanceChange()">XÁC NHẬN THỰC HIỆN</button>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function showTab(tabId, btn) {{
                document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                document.getElementById('tab-home').style.display = 'none';
                document.getElementById('tab-deposits').style.display = 'none';
                document.getElementById('tab-gamelogs').style.display = 'none';
                document.getElementById('tab-balance').style.display = 'none';

                document.getElementById(tabId).style.display = 'block';
            }}

            async function loadHomeData() {{
                try {{
                    const res = await fetch('/admin/api/app/users');
                    const data = await res.json();
                    document.getElementById('online-count').innerText = data.length + ' Tk';
                    let html = '';
                    data.forEach(u => {{
                        html += `<tr>
                            <td><b>${{u.username}}</b></td>
                            <td style="color:#22c55e;">${{Number(u.balance).toLocaleString()}}đ</td>
                            <td><span class="badge badge-success">Online</span></td>
                        </tr>`;
                    }});
                    document.getElementById('users-table').innerHTML = html || '<tr><td colspan="3">Chưa có dữ liệu</td></tr>';
                }} catch(e) {{}}
            }}

            async function loadDepositsData() {{
                try {{
                    const res = await fetch('/admin/api/deposits');
                    const data = await res.json();
                    let html = '';
                    data.forEach(d => {{
                        let stClass = d.status === 'SUCCESS' ? 'badge-success' : (d.status === 'FAILED' ? 'badge-failed' : 'badge-pending');
                        let btns = d.status === 'PENDING' ? `
                            <button class="action-btn btn-ok" onclick="updateDep('${{d.code}}', 'SUCCESS')">✓</button>
                            <button class="action-btn btn-no" onclick="updateDep('${{d.code}}', 'FAILED')">✕</button>
                        ` : '-';

                        html += `<tr>
                            <td><code>${{d.code}}</code></td>
                            <td><b>${{d.username}}</b></td>
                            <td style="color:#22c55e;">${{Number(d.amount).toLocaleString()}}đ</td>
                            <td><span class="badge ${{stClass}}">${{d.status}}</span></td>
                            <td>${{btns}}</td>
                        </tr>`;
                    }});
                    document.getElementById('deposits-table').innerHTML = html || '<tr><td colspan="5">Không có đơn nạp</td></tr>';
                }} catch(e) {{}}
            }}

            async function updateDep(code, status) {{
                await fetch('/admin/api/deposit/update', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ code, status }})
                }});
                loadDepositsData();
            }}

            async function loadGameLogs() {{
                try {{
                    const res = await fetch('/admin/api/gamelogs');
                    const data = await res.json();
                    let html = '';
                    data.forEach(l => {{
                        let winColor = l.win_amount > 0 ? '#22c55e' : '#ef4444';
                        html += `<tr>
                            <td><b>${{l.username}}</b></td>
                            <td style="color:#cca352;">${{l.game_name}}</td>
                            <td>${{Number(l.bet_amount).toLocaleString()}}</td>
                            <td style="color:${{winColor}};">${{Number(l.win_amount).toLocaleString()}}</td>
                        </tr>`;
                    }});
                    document.getElementById('logs-table').innerHTML = html || '<tr><td colspan="4">Chưa có lịch sử cược</td></tr>';
                }} catch(e) {{}}
            }}

            async function executeBalanceChange() {{
                const username = document.getElementById('target-username').value;
                const amount = document.getElementById('target-amount').value;
                if(!username || !amount) return alert("Vui lòng điền đủ thông tin!");

                const res = await fetch('/admin/api/user/balance', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ username, amount: parseFloat(amount) }})
                }});
                const result = await res.json();
                alert(result.message);
            }}

            setInterval(() => {{
                loadHomeData();
                loadDepositsData();
                loadGameLogs();
            }}, 3000);

            loadHomeData();
            loadDepositsData();
            loadGameLogs();
        </script>
    </body>
    </html>
    """

@app.route('/admin/api/app/users')
def api_app_get_users():
    conn = get_db_connection()
    users = conn.execute("SELECT id, username, balance, role FROM users ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(row) for row in users])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
    
