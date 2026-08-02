import os
import random
import string
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from jinja2 import TemplateNotFound

app = Flask(__name__)
app.secret_key = 'casio_world_secret_key_123'
app.config['DEBUG'] = True

# Bộ lưu trữ đơn nạp tiền
payment_orders = {}

# -------------------------------------------------------------
# HỆ THỐNG AN TOÀN: TỰ ĐỘNG HIỂN THỊ GIAO DIỆN DỰ PHÒNG NẾU THIẾU FILE HTML
# -------------------------------------------------------------
def render_safe(template_name, **kwargs):
    try:
        return render_template(template_name, **kwargs)
    except TemplateNotFound:
        title = template_name.replace('.html', '').replace('_', ' ').upper()
        return f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{ background: #0f172a; color: #f8fafc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; text-align: center; }}
                .container {{ max-width: 450px; margin: 60px auto; background: #1e293b; padding: 30px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.4); border: 1px solid #334155; }}
                h2 {{ color: #38bdf8; margin-bottom: 15px; font-size: 22px; }}
                p {{ color: #94a3b8; font-size: 14px; line-height: 1.6; }}
                .btn {{ display: inline-block; margin-top: 25px; background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; transition: 0.2s; box-shadow: 0 4px 12px rgba(59,130,246,0.3); }}
                .btn:hover {{ opacity: 0.9; transform: translateY(-2px); }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>✨ {title}</h2>
                <p>Tính năng này đang hoạt động. Giao diện chi tiết sẽ hiển thị ngay khi bạn cập nhật file mẫu lên hệ thống.</p>
                <a href="/" class="btn">⬅ Quay lại Trang chủ</a>
            </div>
        </body>
        </html>
        """

@app.errorhandler(404)
def not_found_error(error):
    return redirect(url_for('index'))

@app.errorhandler(500)
@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    if "BuildError" in tb or "NotFound" in tb:
        return redirect(url_for('index'))
    return f"""
    <div style="padding: 20px; font-family: monospace; background: #ffffff; color: #cc0000;">
        <h2 style="color: red;">⚠️ THÔNG BÁO HỆ THỐNG:</h2>
        <pre style="background: #1e1e1e; color: #00ff00; padding: 15px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap;">{tb}</pre>
    </div>
    """, 500

# -------------------------------------------------------------
# CUNG CẤP BIẾN CHO HTML
# -------------------------------------------------------------
@app.context_processor
def inject_defaults():
    balance_val = session.get('balance', 0)
    user_data = {
        'id': session.get('user_id', 888888),
        'user_id': session.get('user_id', 888888),
        'username': session.get('username', 'GUEST'),
        'points': balance_val,
        'money': balance_val,
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
        points=balance_val,
        balance=balance_val,
        money=balance_val,
        vip=user_data['vip'],
        vip_level=user_data['vip_level']
    )

def generate_memo():
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
    return f"chuyen tien DMCNA{random_str}"

# -------------------------------------------------------------
# 1. ĐỊNH TUYẾN TẤT CẢ CÁC TRANG
# -------------------------------------------------------------
@app.route('/')
@app.route('/index')
def index():
    return render_safe('index.html')

@app.route('/profile')
def profile():
    return render_safe('profile.html')

@app.route('/promotions')
def promotions():
    return render_safe('promotions.html')

@app.route('/vip')
@app.route('/vip_details')
def vip():
    return render_safe('vip.html')

@app.route('/cskh')
def cskh():
    return render_safe('cskh.html')

@app.route('/withdraw')
def withdraw():
    return render_safe('withdraw.html')

@app.route('/activity')
def activity():
    return render_safe('activity.html')

@app.route('/transaction_center')
def transaction_center():
    return render_safe('transaction_center.html')

@app.route('/history', endpoint='bet history')
@app.route('/bet_history')
@app.route('/bet-history')
def history():
    return render_safe('history.html')

@app.route('/bank_card')
def bank_card():
    return render_safe('bank_card.html')

@app.route('/security')
def security():
    return render_safe('security.html')

@app.route('/messages')
def messages():
    return render_safe('messages.html')

@app.route('/referral')
def referral():
    return render_safe('referral.html')

@app.route('/mailbox')
def mailbox():
    return render_safe('mailbox.html')

# -------------------------------------------------------------
# 2. ĐĂNG NHẬP & ĐĂNG KÝ
# -------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['username'] = request.form.get('username', 'User')
        session['balance'] = 0
        return redirect(url_for('index'))
    return render_safe('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        return redirect(url_for('login'))
    return render_safe('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# -------------------------------------------------------------
# 3. TRANG NẠP TIỀN & XỬ LÝ THANH TOÁN
# -------------------------------------------------------------
@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if request.method == 'POST':
        amount_points = request.form.get('amount', 50)
        try:
            amount_points = float(amount_points)
        except ValueError:
            amount_points = 50
        amount_vnd = int(amount_points * 1000)
        return redirect(url_for('payment', amount=amount_vnd))
    return render_safe('deposit.html')

@app.route('/payment')
def payment():
    amount_vnd = request.args.get('amount', 50000, type=int)
    formatted_amount = "{:,}".format(amount_vnd).replace(",", ".")
    
    memo_code = generate_memo()
    points_to_add = amount_vnd / 1000  
    
    payment_orders[memo_code] = {
        "username": session.get('username', 'GUEST'),
        "amount_vnd": amount_vnd,
        "points": points_to_add,
        "status": "PENDING"
    }
    
    bank_info = {
        "bank_id": "TCB",
        "bank_name": "Ngân hàng Techcombank",
        "account_no": "8992362013",
        "account_name": "LỶ KIM HẰNG",
        "amount": amount_vnd,
        "amount_str": f"{formatted_amount} VND",
        "memo": memo_code
    }
    
    qr_url = f"https://img.vietqr.io/image/{bank_info['bank_id']}-{bank_info['account_no']}-qr_only.png?amount={amount_vnd}&addInfo={memo_code}"
    
    return render_safe('payment.html', bank=bank_info, qr_url=qr_url)

@app.route('/api/check_payment/<path:memo>')
def check_payment(memo):
    order = payment_orders.get(memo)
    if order and order['status'] == 'SUCCESS':
        return jsonify({"status": "SUCCESS", "message": "Thanh toán thành công! Tiền đã cộng vào ví."})
    return jsonify({"status": "PENDING"})

@app.route('/api/bank_webhook', methods=['POST', 'GET'])
def bank_webhook():
    memo = request.args.get('memo') or (request.json.get('content') if request.is_json else None)
    if memo and memo in payment_orders:
        order = payment_orders[memo]
        if order['status'] != 'SUCCESS':
            order['status'] = 'SUCCESS'
            session['balance'] = session.get('balance', 0) + order['points']
            return jsonify({"status": "ok", "message": f"Đã cộng {order['points']} điểm vào tài khoản!"})
    return jsonify({"status": "failed", "message": "Mã giao dịch không hợp lệ"}), 400

@app.route('/test_pay/<path:memo>')
def test_pay(memo):
    if memo in payment_orders:
        payment_orders[memo]['status'] = 'SUCCESS'
        session['balance'] = session.get('balance', 0) + payment_orders[memo]['points']
        return f"<h3>Thành công! Đã giả lập nạp tiền cho đơn: {memo}. Số dư hiện tại: {session['balance']}</h3><a href='/'>Quay lại trang chủ</a>"
    return "Không tìm thấy mã đơn!"

@app.route('/<path:subpath>')
def catch_all(subpath):
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
