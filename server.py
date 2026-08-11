import os
import random
import string
import sqlite3
import traceback
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, jsonify
from jinja2 import TemplateNotFound

if os.environ.get("RENDER"):
    try:
        subprocess.Popen(["python", "bot.py"])
        print(">>> Bot.py đã chạy ngầm!")
    except Exception as e:
        print(f">>> Lỗi bot: {e}")

app = Flask(__name__)
app.secret_key = 'casio_world_secret_key_123'
app.config['DEBUG'] = True

error_logs = []
DB_NAME = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, balance REAL DEFAULT 500000, role TEXT DEFAULT 'user')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS deposits (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, amount REAL NOT NULL, code TEXT UNIQUE NOT NULL, status TEXT DEFAULT 'PENDING', created_at TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS game_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, game_name TEXT NOT NULL, bet_amount REAL DEFAULT 0, win_amount REAL DEFAULT 0, is_jackpot INTEGER DEFAULT 0, status TEXT DEFAULT 'Đang cược', created_at TEXT NOT NULL)''')
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, balance, role) VALUES ('admin', 'admin123', 99999999, 'owner')")
    conn.commit()
    conn.close()

init_db()

def log_error(err_msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    error_logs.insert(0, {"time": timestamp, "detail": err_msg})
    if len(error_logs) > 50:
        error_logs.pop()

def render_safe(template_name, **kwargs):
    try:
        return render_template(template_name, **kwargs)
    except TemplateNotFound:
        log_error(f"Thiếu file: {template_name}")
        return f"<h2>✨ {template_name} đang cập nhật</h2><a href='/'>Quay lại</a>"
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
            session['username'], session['role'], session['balance'] = user['username'], user['role'], user['balance']
            return redirect('/admin' if user['role'] in ['admin', 'owner'] else '/')
        return render_safe('login.html', error="Sai thông tin!")
    return render_safe('login.html')

@app.route('/play/<game_name>')
def play_game(game_name):
    username = session.get('username', request.args.get('username', 'GUEST'))
    return redirect(f"/static/games/{game_name}/index.html?username={username}")

@app.route('/ktraloibug')
def ktraloibug():
    logs_html = "".join([f"<p><b>[{item['time']}]</b>: {item['detail']}</p>" for item in error_logs]) or "<p>Không có lỗi</p>"
    return f"<h2>Hệ Thống Lỗi TX68</h2>{logs_html}<br><a href='/'>Về trang chủ</a>"

@app.errorhandler(404)
def not_found_error(e):
    return redirect('/')

@app.errorhandler(Exception)
def handle_exception(e):
    log_error(traceback.format_exc())
    return "<h2>Đã xảy ra lỗi hệ thống (500)</h2><a href='/'>Về trang chủ</a>", 500

@app.context_processor
def inject_defaults():
    username = session.get('username', 'GUEST')
    conn = get_db_connection()
    user_row = conn.execute("SELECT balance, role FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    balance_val = user_row['balance'] if user_row else 500000
    user_role = user_row['role'] if user_row else 'user'
    user_data = {'id': 8386888, 'username': username, 'balance': balance_val, 'money': balance_val, 'role': user_role, 'bank_name': 'TECHCOMBANK', 'bank_account': '8992362013', 'account_name': 'LỶ KIM HẰNG'}
    return dict(user=user_data, current_user=user_data, username=username, balance=balance_val, role=user_role)

@app.route('/admin')
def admin_panel():
    if session.get('role') not in ['owner', 'admin']:
        return "🚫 Từ chối truy cập", 403
    return """
    <h2>BẢNG QUẢN TRỊ ADMIN TX68</h2>
    <div id="deposits">Đang tải nạp tiền...</div><br>
    <div id="logs">Đang tải lịch sử cược...</div>
    <script>
        async function loadData() {
            let res1 = await fetch('/admin/api/deposits');
            let dep = await res1.json();
            document.getElementById('deposits').innerHTML = '<b>Đơn nạp:</b> ' + JSON.stringify(dep);
            let res2 = await fetch('/admin/api/gamelogs');
            let logs = await res2.json();
            document.getElementById('logs').innerHTML = '<b>Lịch sử cược:</b> ' + JSON.stringify(logs);
        }
        setInterval(loadData, 3000); loadData();
    </script>
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
    conn = get_db_connection()
    cursor = conn.cursor()
    dep = cursor.execute("SELECT username, amount, status FROM deposits WHERE code = ?", (data.get('code'),)).fetchone()
    if dep and dep['status'] == 'PENDING':
        cursor.execute("UPDATE deposits SET status = ? WHERE code = ?", (data.get('status'), data.get('code')))
        if data.get('status') == 'SUCCESS':
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (data.get('amount', 0), data.get('username')))
    conn.commit()
    conn.close()
    return jsonify({"message": "Thành công!"})

@app.route('/api/game/log', methods=['POST'])
def api_game_log():
    try:
        data = request.json or {}
        username = data.get('username') or session.get('username', 'GUEST')
        if username != 'GUEST':
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO game_logs (username, game_name, bet_amount, win_amount, is_jackpot, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                           (username, data.get('game_name', 'Game'), float(data.get('bet_amount', 0)), float(data.get('win_amount', 0)), 1 if data.get('is_jackpot') else 0, data.get('status', 'Xong'), datetime.now().strftime("%H:%M:%S")))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (float(data.get('win_amount', 0)) - float(data.get('bet_amount', 0)), username))
            conn.commit()
            conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin-app')
def admin_app_page():
    return "<h2>App Admin Mobile TX68</h2><p>Hệ thống đang chạy ngầm ổn định.</p>"

@app.route('/admin/api/app/users')
def api_app_get_users():
    conn = get_db_connection()
    users = conn.execute("SELECT id, username, balance, role FROM users ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(row) for row in users])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
    
