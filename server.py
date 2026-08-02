from flask import Flask, render_template, redirect, url_for

app = Flask(__name__)

@app.route('/')
def index():
    balance = 50100000.0
    return render_template('index.html', balance=balance)

@app.route('/profile')
def profile():
    balance = 50100000.0
    username = "pphuc8386"
    return render_template('profile.html', balance=balance, username=username)

@app.route('/deposit')
def deposit():
    return render_template('deposit.html')

@app.route('/withdraw')
def withdraw():
    return "Trang Rút Tiền"

@app.route('/transaction-center')
def transaction_center():
    return "Trang Trung Tâm Giao Dịch"

@app.route('/cskh')
def cskh():
    return render_template('cskh.html')

@app.route('/vip')
def vip():
    return render_template('vip.html')

@app.route('/vip-details')
def vip_details():
    return render_template('vip_details.html')

@app.route('/promotions')
def promotions():
    return "Trang Khuyến Mãi"

@app.route('/referral')
def referral():
    return "Trang Giới Thiệu Bạn Bè"

@app.route('/mailbox')
def mailbox():
    return "Trang Hộp Thư"

@app.route('/bet-history')
def bet_history():
    return "Trang Chi Tiết Đặt Cược"

@app.route('/security')
def security():
    return "Trang Bảo Mật"

@app.route('/notifications')
def notifications():
    return "Trang Thông Báo"

@app.route('/rebate')
def rebate():
    return "Trang Hoàn Trả"

@app.route('/logout')
def logout():
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    
