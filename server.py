from flask import Flask, render_template

# Khởi tạo ứng dụng Flask
app = Flask(__name__)

# Route cho sảnh chính (Trang chủ)
@app.route('/')
def index():
    return render_template('index.html')

# Các route mở rộng dựa theo thư mục templates của bạn
@app.route('/login')
def login():
    # Render file login.html (đảm bảo bạn đã tạo nội dung cho file này)
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/deposit')
def deposit():
    return render_template('deposit.html')

if __name__ == '__main__':
    # Chạy server ở chế độ debug để tự cập nhật mỗi khi bạn lưu file
    app.run(host='0.0.0.0', port=5000, debug=True)
    
