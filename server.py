import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, g

app = Flask(__name__)
app.secret_key = 'casio_world_secret_key_123'

DATABASE = 'database.db'

# -------------------------------------------------------------
# XỬ LÝ CƠ SỞ DỮ LIỆU & BIẾN TOÀN CỤC (Chống lỗi 500)
# -------------------------------------------------------------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        if os.path.exists(DATABASE):
            db = g._database = sqlite3.connect(DATABASE)
            db.row_factory = sqlite3.Row
        else:
            db = None
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Tự động gửi thông tin user vào TẤT CẢ các file HTML để không bị lỗi thiếu biến
@app.context_processor
def inject_user():
    user_info = None
    if 'username' in session:
        user_info = {
            'username': session['username'],
            'points': session.get('points', 0)
        }
    return dict(current_user=user_info, user=user_info)


# -------------------------------------------------------------
# 1. TRANG CHỦ & TRANG CHỨC NĂNG
# -------------------------------------------------------------
@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/cskh')
def cskh():
    return render_template('cskh.html')

@app.route('/vip')
def vip():
    return render_template('vip.html')

@app.route('/vip_details')
def vip_details():
    return render_template('vip_details.html')


# -------------------------------------------------------------
# 2. ĐĂNG NHẬP & ĐĂNG KÝ
# -------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', 'User')
        session['username'] = username
        session['points'] = 0
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# -------------------------------------------------------------
# 3. TRANG NẠP TIỀN
# -------------------------------------------------------------
@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if request.method == 'POST':
        amount_points = request.form.get('amount', 0)
        try:
            amount_points = float(amount_points)
        except ValueError:
            amount_points = 0
            
        # Quy đổi: 1 Điểm = 1.000 VNĐ
        amount_vnd = int(amount_points * 1000)
        return redirect(url_for('payment', amount=amount_vnd))
        
    return render_template('deposit.html')


# -------------------------------------------------------------
# 4. TRANG THANH TOÁN (MÃ QR TECHCOMBANK)
# -------------------------------------------------------------
@app.route('/payment')
def payment():
    amount_vnd = request.args.get('amount', 0, type=int)
    formatted_amount = "{:,}".format(amount_vnd).replace(",", ".")
    
    # Thông tin tài khoản Techcombank LỶ KIM HẰNG
    bank_info = {
        "bank_id": "TCB",
        "bank_name": "Ngân hàng Techcombank",
        "account_no": "8992362013",
        "account_name": "LỶ KIM HẰNG",
        "amount": amount_vnd,
        "amount_str": f"{formatted_amount} VND"
    }
    
    # Tự động tạo link mã QR VietQR khớp đúng số tiền
    qr_url = f"https://img.vietqr.io/image/{bank_info['bank_id']}-{bank_info['account_no']}-compact2.png?amount={amount_vnd}&addInfo=NAP%20TIEN&accountName={bank_info['account_name']}"
    
    return render_template('payment.html', bank=bank_info, qr_url=qr_url)


# -------------------------------------------------------------
# KHỞI CHẠY SERVER
# -------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
        
