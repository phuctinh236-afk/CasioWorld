from flask import Flask, render_template, redirect, url_for

app = Flask(__name__)

# Route Trang cá nhân
@app.route('/profile')
def profile():
    # Đảm bảo truyền đủ biến balance (kiểu số) và username
    balance = 50100000.0
    username = "pphuc8386"
    return render_template('profile.html', balance=balance, username=username)

# Bổ sung các route đang bị thiếu để tránh lỗi 500 khi click:
@app.route('/withdraw')
def withdraw():
    return "Trang Rút Tiền (Đang cập nhật)"

@app.route('/transaction-center')
def transaction_center():
    return "Trang Trung Tâm Giao Dịch"

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

@app.route('/vip')
def vip():
    return "Trang VIP"

@app.route('/cskh')
def cskh():
    return "Trang Chăm Sóc Khách Hàng"

@app.route('/deposit')
def deposit():
    return "Trang Nạp Tiền"

@app.route('/promotions')
def promotions():
    return "Trang Khuyến Mãi"

@app.route('/logout')
def logout():
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
    
