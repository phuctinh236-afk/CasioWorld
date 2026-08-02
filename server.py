import os
import random
import string
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'casio_world_secret_key_123'
app.config['DEBUG'] = True

# Bộ lưu trữ đơn nạp tiền trong bộ nhớ tạm (Mã memo -> thông tin đơn)
payment_orders = {}

# -------------------------------------------------------------
# CUNG CẤP BIẾN TOÀN CỤC CHO TEMPLATE
# -------------------------------------------------------------
@app.context_processor
def inject_defaults():
    balance_val = session.get('balance', 0)
    user_data = {
        'id': session.get('user_id', 888888),
        'username': session.get('username', 'GUEST'),
        'balance': balance_val,
        'points': balance_val
    }
    return dict(user=user_data, balance=balance_val)

def generate_memo():
    """Tạo mã nội dung chuyển khoản dạng: chuyen tien DMCNA + 7 số/chữ"""
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
    return f"chuyen tien DMCNA{random_str}"

# -------------------------------------------------------------
# 1. TRANG THANH TOÁN QR & BỘ ĐỒNG BỘ TỰ ĐỘNG CỘNG TIỀN
# -------------------------------------------------------------
@app.route('/payment')
def payment():
    amount_vnd = request.args.get('amount', 50000, type=int)
    formatted_amount = "{:,}".format(amount_vnd).replace(",", ".")
    
    # Tạo nội dung chuyển khoản mới
    memo_code = generate_memo()
    
    # Tính số điểm/tiền ví ảo sẽ cộng (Ví dụ 1,000 VND = 1 điểm ví)
    points_to_add = amount_vnd / 1000  
    
    # Lưu thông tin đơn nạp chờ thanh toán
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
    
    # Mã QR tự điền sẵn nội dung chuyển khoản
    qr_url = f"https://img.vietqr.io/image/{bank_info['bank_id']}-{bank_info['account_no']}-qr_only.png?amount={amount_vnd}&addInfo={memo_code}"
    
    return render_template('payment.html', bank=bank_info, qr_url=qr_url)

# API để giao diện kiểm tra xem đơn đã được cộng tiền chưa
@app.route('/api/check_payment/<path:memo>')
def check_payment(memo):
    order = payment_orders.get(memo)
    if order and order['status'] == 'SUCCESS':
        return jsonify({"status": "SUCCESS", "message": "Thanh toán thành công! Tiền đã cộng vào ví."})
    return jsonify({"status": "PENDING"})

# API Webhook (Cổng nhận thông báo tự động từ Ngân hàng / Casso / SePay / Hoặc giả lập)
@app.route('/api/bank_webhook', methods=['POST', 'GET'])
def bank_webhook():
    # Nhận dữ liệu memo và số tiền
    memo = request.args.get('memo') or (request.json.get('content') if request.is_json else None)
    
    if memo and memo in payment_orders:
        order = payment_orders[memo]
        if order['status'] != 'SUCCESS':
            # Cập nhật trạng thái thành công
            order['status'] = 'SUCCESS'
            
            # Cộng tiền trực tiếp vào Ví ảo của người dùng
            current_balance = session.get('balance', 0)
            session['balance'] = current_balance + order['points']
            
            return jsonify({"status": "ok", "message": f"Đã cộng {order['points']} điểm vào tài khoản!"})
            
    return jsonify({"status": "failed", "message": "Mã giao dịch không hợp lệ hoặc đã xử lý"}), 400

# Route để test nhanh cộng tiền thủ công (Gõ link này trên trình duyệt để giả lập ngân hàng chuyển khoản)
@app.route('/test_pay/<path:memo>')
def test_pay(memo):
    if memo in payment_orders:
        payment_orders[memo]['status'] = 'SUCCESS'
        session['balance'] = session.get('balance', 0) + payment_orders[memo]['points']
        return f"<h3>Thành công! Đã giả lập ngân hàng chuyển khoản cho đơn: {memo}. Số dư hiện tại: {session['balance']}</h3><a href='/'>Quay lại trang chủ</a>"
    return "Không tìm thấy mã đơn!"

# -------------------------------------------------------------
# CÁC ROUTE KHÁC
# -------------------------------------------------------------
@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

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
    return render_template('deposit.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    
