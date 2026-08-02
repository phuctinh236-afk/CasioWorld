from flask import Flask, render_template, request, session, redirect, url_for

app = Flask(__name__)
app.secret_key = 'super_secret_key_lobby'  # Khóa bí mật để quản lý session ví

@app.before_request
def init_session():
    # Khởi tạo ví lobby mặc định có 500,000 VND nếu chưa có
    if 'balance' not in session:
        session['balance'] = 500000.0

# Trang chủ (Lobby game)
@app.route('/')
def index():
    return render_template('index.html', balance=session['balance'])

# Trang tài khoản / cá nhân
@app.route('/profile')
def profile():
    return render_template('profile.html', balance=session['balance'])

# Trang nạp / rút tiền chung
@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    message = None
    msg_type = None  # 'success' hoặc 'error'
    
    if request.method == 'POST':
        action = request.form.get('action')  # 'deposit' (Nạp) hoặc 'withdraw' (Rút)
        try:
            amount = float(request.form.get('amount', 0))
            if amount <= 0:
                message = "Vui lòng nhập số tiền lớn hơn 0!"
                msg_type = 'error'
            else:
                if action == 'deposit':
                    session['balance'] += amount
                    message = f"Nạp thành công {amount:,.0f} VND vào Ví Lobby!"
                    msg_type = 'success'
                elif action == 'withdraw':
                    if session['balance'] >= amount:
                        session['balance'] -= amount
                        message = f"Rút thành công {amount:,.0f} VND từ Ví Lobby!"
                        msg_type = 'success'
                    else:
                        message = "Số dư Ví Lobby không đủ để thực hiện lệnh rút!"
                        msg_type = 'error'
        except ValueError:
            message = "Số tiền không hợp lệ!"
            msg_type = 'error'

    return render_template('deposit.html', balance=session['balance'], message=message, msg_type=msg_type)

# Trang chăm sóc khách hàng (CSKH)
@app.route('/cskh')
def cskh():
    return render_template('cskh.html', balance=session['balance'])

# Trang khuyến mãi
@app.route('/promotions')
def promotions():
    return render_template('promotions.html', balance=session['balance'])

# Trang đặc quyền VIP
@app.route('/vip')
def vip():
    return render_template('vip.html', balance=session['balance'])

# Trang chi tiết VIP
@app.route('/vip-details')
def vip_details():
    return render_template('vip_details.html', balance=session['balance'])

if __name__ == '__main__':
    app.run(debug=True, port=5000)
                        
