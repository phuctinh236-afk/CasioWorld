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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username and password:
            conn = get_db_connection()
            try:
                conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
                session['username'] = username
                session['role'] = 'user'
                session['balance'] = 500000
                conn.close()
                return redirect('/')
            except sqlite3.IntegrityError:
                conn.close()
                return render_safe('register.html', error="Tài khoản đã tồn tại!")
    return render_safe('register.html')

@app.route('/play/<game_name>')
def play_game_by_name(game_name):
    username = session.get('username', request.args.get('username', 'GUEST'))
    return redirect(f"/static/games/{game_name}/index.html?username={username}")

@app.route('/play_game')
def play_game():
    return redirect('/')

# --- BỔ SUNG CÁC ROUTE KHUYẾN MÃI, TÀI KHOẢN, CSKH ---
@app.route('/promotions')
def promotions():
    return render_safe('promotions.html')

@app.route('/cskh')
def cskh():
    return render_safe('cskh.html')

@app.route('/profile')
def profile():
    return render_safe('profile.html')

@app.route('/deposit')
def deposit():
    return render_safe('deposit.html')

@app.route('/withdraw')
def withdraw():
    return render_safe('withdraw.html')

@app.route('/mailbox')
def mailbox():
    return render_safe('mailbox.html')

@app.route('/payment')
def payment():
    return render_safe('payment.html')

@app.route('/vip')
def vip():
    return render_safe('vip.html')

@app.route('/vip_details')
def vip_details():
    return render_safe('vip_details.html')

# --- BỔ SUNG CÁC ROUTE SLOT GAME HTML ---
@app.route('/mahjong')
def mahjong():
    return render_safe('mahjong.html')

@app.route('/mahjong_ways_2')
def mahjong_ways_2():
    return render_safe('mahjong_ways_2.html')

@app.route('/super_ace')
def super_ace():
    return render_safe('super_ace.html')# =========================================================
# HỆ THỐNG DỰ PHÒNG & GIÁM SÁT (ĐÃ XÓA FAVICON)
# =========================================================

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
    # Bỏ qua log favicon để không làm bẩn trang giám sát
    if request.path == '/favicon.ico':
        return '', 204
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
# HỆ THỐNG PANEL ADMIN
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
            <div>Tài khoản: <b>{username}</b> <span class="badge">OWNER</span></div>
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
                try {{
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
                                <td class="\( {{statusClass}}"> \){{item.status}}</td>
                                <td>${{actions}}</td>
                            </tr>`;
                        }});
                    }}
                    document.getElementById('deposit-rows').innerHTML = html;
                }} catch(e) {{ console.error(e); }}
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
                try {{
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
                                <td style="color:\( {{winColor}}; font-weight:bold;"> \){{Number(item.win_amount).toLocaleString()}}</td>
                                <td>${{isJp}}</td>
                                <td>${{item.status || 'Đang cược'}}</td>
                            </tr>`;
                        }});
                    }}
                    document.getElementById('game-rows').innerHTML = html;
                }} catch(e) {{ console.error(e); }}
            }}

            async function modifyBalance() {{
                const username = document.getElementById('target-user').value;
                const amount = document.getElementById('mod-amount').value;
                if(!username || !amount) return alert("Vui lòng điền đủ thông tin!");

                const res = await fetch('/admin/api/user/balance', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ username, amount: parseFloat(amount) }})
                }});
                const result = await res.json();
                alert(result.message || 'Thành công!');
            }}

            setInterval(() => {{
                fetchDeposits();
                fetchGameLogs();
            }}, 4000);

            fetchDeposits();
            fetchGameLogs();
        </script>
    </body>
    </html>
    """@app.route('/admin/api/deposits')
def api_get_deposits():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM deposits ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/admin/api/deposit/update', methods=['POST'])
def api_update_deposit():
    data = request.get_json()
    code = data.get('code')
    status = data.get('status')
    
    conn = get_db_connection()
    deposit = conn.execute("SELECT * FROM deposits WHERE code = ?", (code,)).fetchone()
    
    if deposit and deposit['status'] == 'PENDING':
        conn.execute("UPDATE deposits SET status = ? WHERE code = ?", (status, code))
        
        if status == 'SUCCESS':
            conn.execute("UPDATE users SET balance = balance + ? WHERE username = ?", 
                        (deposit['amount'], deposit['username']))
        
        conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/admin/api/gamelogs')
def api_get_gamelogs():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM game_logs ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/admin/api/user/balance', methods=['POST'])
def api_modify_balance():
    data = request.get_json()
    username = data.get('username')
    amount = data.get('amount')
    
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    
    if not user:
        conn.close()
        return jsonify({"message": "Không tìm thấy tài khoản!"})
    
    conn.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount, username))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Đã cập nhật số dư cho {username} thành công!"})

@app.route('/admin/api/app/users')
def api_app_get_users():
    conn = get_db_connection()
    users = conn.execute("SELECT id, username, balance, role FROM users ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(row) for row in users])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
