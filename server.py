import os
import random
import string
import sqlite3
import traceback
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from jinja2 import TemplateNotFound

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

DB_NAME = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 500000,
            role TEXT DEFAULT 'user'
        )
    ''')
    
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

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/play/<game_name>')
def play_game_by_name(game_name):
    username = session.get('username', request.args.get('username', 'GUEST'))
    return redirect(f"/static/games/{game_name}/index.html?username={username}")

@app.route('/play_game')
def play_game():
    return redirect('/')

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

@app.route('/mahjong')
def mahjong():
    return render_safe('mahjong.html')

@app.route('/mahjong_ways_2')
def mahjong_ways_2():
    return render_safe('mahjong_ways_2.html')

@app.route('/super_ace')
def super_ace():
    return render_safe('super_ace.html')
