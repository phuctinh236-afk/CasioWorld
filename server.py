from flask import Flask, render_template

app = Flask(__name__)

# Trang chủ (Lobby game)
@app.route('/')
def index():
    return render_template('index.html')

# Trang tài khoản / cá nhân
@app.route('/profile')
def profile():
    return render_template('profile.html')

# Trang nạp tiền
@app.route('/deposit')
def deposit():
    return render_template('deposit.html')

# Trang chăm sóc khách hàng (CSKH)
@app.route('/cskh')
def cskh():
    return render_template('cskh.html')

# Trang khuyến mãi
@app.route('/promotions')
def promotions():
    return render_template('promotions.html')

# Trang đặc quyền VIP
@app.route('/vip')
def vip():
    return render_template('vip.html')

# Trang chi tiết VIP (có bảng tổng cược, tổng nạp, thưởng tháng...)
@app.route('/vip-details')
def vip_details():
    return render_template('vip_details.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
    
