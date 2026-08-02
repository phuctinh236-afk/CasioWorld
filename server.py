import os
import sqlite3
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, g

app = Flask(__name__)
app.secret_key = 'casio_world_secret_key_123'
app.config['DEBUG'] = True

# -------------------------------------------------------------
# BỘ BẪY LỖI CHẨN ĐOÁN
# -------------------------------------------------------------
@app.errorhandler(500)
@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    return f"""
    <div style="padding: 20px; font-family: monospace; background: #ffffff; color: #cc0000;">
        <h2 style="color: red;">⚠️ PHÁT HIỆN LỖI TRONG CODE:</h2>
        <pre style="background: #1e1e1e; color: #00ff00; padding: 15px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap;">{tb}</pre>
    </div>
    """, 500

# -------------------------------------------------------------
# CUNG CẤP TẤT CẢ BIẾN CẦN THIẾT CHO PROFILE & GAME
# -------------------------------------------------------------
@app.context_processor
def inject_defaults():
    balance_val = session.get('balance', session.get('points', 0))
    user_data = {
        'id': session.get('user_id', 888888),
        'user_id': session.get('user_id', 888888),
        'username': session.get('username', 'GUEST'),
        'points': session.get('points', 0),
        'money': session.get('money', 0),
        'vip': session.get('vip', 1),
        'vip_level': session.get('vip', 1),
        'balance': balance_val,
        'phone': session.get('phone', '09******88'),
        'bank_name': 'TECHCOMBANK',
        'bank_account': '8992362013',
        'account_name': 'LỶ KIM HẰNG'
    }
    return dict(
        user=user_data,
        current_user=user_data,
        username=user_data['username'],
        points=user_data['points'],
        balance=balance_val,
        money=user_data['money'],
        vip=user_data['vip'],
        vip_level=user_data['vip_level']
    )

def safe_render(template_name):
    try:
        return render_template(template_name)
    except Exception:
        return render_template('index.html')

# -------------------------------------------------------------
# 1. CÁC TRANG CHÍNH & THÀNH VIÊN
# -------------------------------------------------------------
@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/vip')
def vip():
    return safe_render('vip.html')

@app.route('/vip_details')
def vip_details():
    return safe_render('vip_details.html')

@app.route('/cskh')
def cskh():
    return safe_render('cskh.html')

@app.route('/promotions')
def promotions():
    return safe_render('promotions.html')

@app.route('/withdraw')
def withdraw():
    return safe_render('withdraw.html')

@app.route('/activity')
def activity():
    return safe_render('activity.html')

# -------------------------------------------------------------
# 2. BỔ SUNG CÁC ROUTE PHỤ TRÁNH LỖI TRONG PROFILE.HTML
# -------------------------------------------------------------
@app.route('/transaction_center')
def transaction_center():
    return safe_render('transaction_center.html')

@app.route('/history')
def history():
    return safe_render('history.html')

@app.route('/bank_card')
def bank_card():
    return safe_render('bank_card.html')

@app.route('/security')
def security():
    return safe_render('security.html')

@app.route('/messages')
def messages():
    return safe_render('messages.html')

# -------------------------------------------------------------
# 3. ĐĂNG NHẬP & ĐĂNG KÝ
# -------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['username'] = request.form.get('username', 'User')
        session['points'] = 0
        session['balance'] = 0
        return redirect(url_for('index'))
    return safe_render('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        return redirect(url_for('login'))
    return safe_render('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# -------------------------------------------------------------
# 4. TRANG NẠP TIỀN & THANH TOÁN QR TECHCOMBANK
# -------------------------------------------------------------
@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if request.method == 'POST':
        amount_points = request.form.get('amount', 0)
        try:
            amount_points = float(amount_points)
        except ValueError:
            amount_points = 0
            
        amount_vnd = int(amount_points * 1000)
        return redirect(url_for('payment', amount=amount_vnd))
        
    return safe_render('deposit.html')

@app.route('/payment')
def payment():
    amount_vnd = request.args.get('amount', 0, type=int)
    formatted_amount = "{:,}".format(amount_vnd).replace(",", ".")
    
    bank_info = {
        "bank_id": "TCB",
        "bank_name": "Ngân hàng Techcombank",
        "account_no": "8992362013",
        "account_name": "LỶ KIM HẰNG",
        "amount": amount_vnd,
        "amount_str": f"{formatted_amount} VND"
    }
    
    qr_url = f"https://img.vietqr.io/image/{bank_info['bank_id']}-{bank_info['account_no']}-compact2.png?amount={amount_vnd}&addInfo=NAP%20TIEN&accountName={bank_info['account_name']}"
    
    return render_template('payment.html', bank=bank_info, qr_url=qr_url)

# -------------------------------------------------------------
# KHỞI CHẠY SERVER
# -------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    
