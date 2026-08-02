from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'casio_world_secret_key'

# -------------------------------------------------------------
# 1. Trang Chủ
# -------------------------------------------------------------
@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')

# -------------------------------------------------------------
# 2. Trang Đăng Nhập & Đăng Ký
# -------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        return redirect(url_for('login'))
    return render_template('register.html')

# -------------------------------------------------------------
# 3. Trang Cá Nhân & Chăm Sóc Khách Hàng
# -------------------------------------------------------------
@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/cskh')
def cskh():
    return render_template('cskh.html')

# -------------------------------------------------------------
# 4. Trang VIP & Chi Tiết VIP
# -------------------------------------------------------------
@app.route('/vip')
def vip():
    return render_template('vip.html')

@app.route('/vip_details')
def vip_details():
    return render_template('vip_details.html')

# -------------------------------------------------------------
# 5. Trang Nạp Tiền (Nhận điểm/tiền người dùng chọn)
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
        
        # Chuyển hướng sang trang hiển thị mã QR (/payment)
        return redirect(url_for('payment', amount=amount_vnd))
        
    return render_template('deposit.html')

# -------------------------------------------------------------
# 6. Trang Hiển Thị Mã QR Thanh Toán Techcombank
# -------------------------------------------------------------
@app.route('/payment')
def payment():
    # Lấy số tiền được chuyển tới
    amount_vnd = request.args.get('amount', 0, type=int)
    formatted_amount = "{:,}".format(amount_vnd).replace(",", ".")
    
    # Thông tin tài khoản Techcombank
    bank_info = {
        "bank_id": "TCB",
        "bank_name": "Ngân hàng Techcombank",
        "account_no": "8992362013",
        "account_name": "LỶ KIM HẰNG",
        "amount": amount_vnd,
        "amount_str": f"{formatted_amount} VND"
    }
    
    # Tự động tạo link mã QR VietQR khớp số tiền
    qr_url = f"https://img.vietqr.io/image/{bank_info['bank_id']}-{bank_info['account_no']}-compact2.png?amount={amount_vnd}&addInfo=NAP%20TIEN&accountName={bank_info['account_name']}"
    
    return render_template('payment.html', bank=bank_info, qr_url=qr_url)

# -------------------------------------------------------------
# Khởi Chạy Server
# -------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    
