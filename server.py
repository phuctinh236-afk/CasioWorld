import os
import random
import string
import traceback
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from jinja2 import TemplateNotFound

app = Flask(__name__)
app.secret_key = 'casio_world_secret_key_123'
app.config['DEBUG'] = True

payment_orders = {}
error_logs = []

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
            <title>{title}</title>
            <style>
                body {{ background: #0f172a; color: #f8fafc; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; text-align: center; }}
                .container {{ max-width: 450px; margin: 60px auto; background: #1e293b; padding: 30px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.4); border: 1px solid #334155; }}
                h2 {{ color: #38bdf8; margin-bottom: 15px; font-size: 22px; }}
                p {{ color: #94a3b8; font-size: 14px; line-height: 1.6; }}
                .btn {{ display: inline-block; margin-top: 25px; background: #3b82f6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>✨ {title}</h2>
                <p>Khu vực này đang hoạt động bình thường.</p>
                <a href="/" class="btn">⬅ Quay lại Trang chủ</a>
            </div>
        </body>
        </html>
        """

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
        <title>Kiểm Tra Lỗi</title>
        <style>
            body {{ background: #0f172a; color: #f8fafc; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; text-align: center; }}
            .wrapper {{ max-width: 800px; margin: 30px auto; background: #090d16; padding: 30px; border-radius: 12px; border: 1px solid #1e293b; }}
            h2 {{ color: #f87171; margin-bottom: 5px; }}
            .btn {{ background: #3b82f6; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 14px; display: inline-block; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="wrapper">
            <h2>🛠️ HỆ THỐNG GIÁM SÁT LỖI (/ktraloibug)</h2>
            {logs_html}
            <a href="/" class="btn">⬅ Về Trang Chủ</a>
        </div>
    </body>
    </html>
    """

@app.errorhandler(404)
def not_found_error(error):
    log_error(f"Lỗi 404 - Không tìm thấy: {request.path}")
    return redirect(url_for('index'))

@app.errorhandler(500)
@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    log_error(tb)
    return redirect(url_for('index'))

@app.context_processor
def inject_defaults():
    balance_val = session.get('balance', 0)
    user_data = {
        'id': 888888, 'user_id': 888888, 'username': session.get('username', 'GUEST'),
        'points': balance_val, 'money': balance_val, 'vip': 1, 'vip_level': 1,
        'balance': balance_val, 'phone': '09******88', 'bank_name': 'TECHCOMBANK',
        'bank_account': '8992362013', 'account_name': 'LỶ KIM HẰNG'
    }
    return dict(user=user_data, current_user=user_data, username=user_data['username'], points=balance_val, balance=balance_val, money=balance_val, vip=1, vip_level=1)

def generate_memo():
    return f"chuyen tien DMCNA{''.join(random.choices(string.ascii_uppercase + string.digits, k=7))}"

@app.route('/')
@app.route('/index')
def index():
    return render_safe('index.html')

@app.route('/profile')
def profile():
    return render_safe('profile.html')

@app.route('/promotions')
@app.route('/khuyen_mai')
@app.route('/khuyenmai')
def promotions():
    return render_safe('promotions.html')

@app.route('/vip')
@app.route('/member')
@app.route('/thanh_vien')
@app.route('/thanhvien')
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

@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if request.method == 'POST':
        try:
            amt = float(request.form.get('amount', 50))
        except ValueError:
            amt = 50
        return redirect(url_for('payment', amount=int(amt * 1000)))
    return render_safe('deposit.html')

@app.route('/payment')
def payment():
    amount_vnd = request.args.get('amount', 50000, type=int)
    memo_code = generate_memo()
    payment_orders[memo_code] = {"amount_vnd": amount_vnd, "points": amount_vnd / 1000, "status": "PENDING"}
    bank_info = {
        "bank_name": "Techcombank", "account_no": "8992362013",
        "account_name": "LỶ KIM HẰNG", "amount": amount_vnd,
        "amount_str": "{:,}".format(amount_vnd).replace(",", ".") + " VND",
        "memo": memo_code
    }
    qr_url = f"https://img.vietqr.io/image/TCB-8992362013-qr_only.png?amount={amount_vnd}&addInfo={memo_code}"
    return render_safe('payment.html', bank=bank_info, qr_url=qr_url)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['username'] = request.form.get('username', 'User')
        return redirect(url_for('index'))
    return render_safe('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    return render_safe('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/<path:subpath>')
def catch_all(subpath):
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
