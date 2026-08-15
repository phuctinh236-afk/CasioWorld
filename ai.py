# ============================================
# File: ai.py
# Chức năng: Tạo máy chủ Flask riêng cho AI VIP.
# Có thể chạy độc lập trên Render bằng lệnh:
#   gunicorn ai:app
# Hoặc tích hợp vào server.py bằng cách thêm các route.
# ============================================

import numpy as np
from flask import Flask, request, jsonify, render_template_string
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

# ---------- Lớp AI VIP ----------
class AIVIP:
    def __init__(self):
        # Cơ sở tri thức ban đầu
        self.knowledge_base = [
            {"question": "bạn tên gì", "answer": "Tôi là AI VIP."},
            {"question": "bạn có khỏe không", "answer": "Tôi luôn hoạt động tốt."},
            {"question": "thời tiết hôm nay thế nào", "answer": "Tôi không có cảm biến thời tiết."},
            {"question": "ai tạo ra bạn", "answer": "Tôi được tạo ra bởi người dùng."},
            {"question": "tạm biệt", "answer": "Tạm biệt!"}
        ]
        self.questions = [item["question"] for item in self.knowledge_base]
        self.answers = [item["answer"] for item in self.knowledge_base]
        self.vectorizer = TfidfVectorizer()
        self.question_vectors = self.vectorizer.fit_transform(self.questions)

    def train(self, new_qa_pairs):
        # Thêm cặp câu hỏi - trả lời mới
        for q, a in new_qa_pairs:
            self.knowledge_base.append({"question": q, "answer": a})
        self.questions = [item["question"] for item in self.knowledge_base]
        self.answers = [item["answer"] for item in self.knowledge_base]
        self.question_vectors = self.vectorizer.fit_transform(self.questions)

    def respond(self, user_input):
        # Trả lời câu hỏi người dùng
        if not user_input.strip():
            return "Vui lòng nhập câu hỏi."
        user_vector = self.vectorizer.transform([user_input])
        similarities = cosine_similarity(user_vector, self.question_vectors).flatten()
        best_idx = int(np.argmax(similarities))
        if similarities[best_idx] > 0.2:
            return self.answers[best_idx]
        else:
            return "Tôi chưa hiểu. Hãy dạy tôi bằng lệnh: học|câu hỏi|câu trả lời"

    def learn_from_input(self, text):
        # Học từ cú pháp: học|câu hỏi|câu trả lời
        parts = text.split("|")
        if len(parts) == 3 and parts[0].strip().lower() == "học":
            q = parts[1].strip()
            a = parts[2].strip()
            self.train([(q, a)])
            return "Đã học xong."
        return None

ai_vip = AIVIP()

# ---------- Giao diện Web ----------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI VIP</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; }
        #chat-box { border: 1px solid #ccc; height: 400px; overflow-y: auto; padding: 10px; margin-bottom: 10px; background: #f9f9f9; }
        .user-msg { text-align: right; color: blue; margin: 5px 0; }
        .ai-msg { text-align: left; color: green; margin: 5px 0; }
        input[type="text"] { width: 80%; padding: 8px; }
        button { padding: 8px 16px; }
    </style>
</head>
<body>
    <h1>AI VIP</h1>
    <div id="chat-box"></div>
    <input type="text" id="user-input" placeholder="Nhập tin nhắn..." />
    <button onclick="sendMessage()">Gửi</button>

    <script>
        async function sendMessage() {
            const input = document.getElementById('user-input');
            const message = input.value.trim();
            if (!message) return;
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div class="user-msg">Bạn: ${message}</div>`;
            input.value = '';

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message })
                });
                const data = await response.json();
                chatBox.innerHTML += `<div class="ai-msg">AI VIP: ${data.reply}</div>`;
                chatBox.scrollTop = chatBox.scrollHeight;
            } catch (error) {
                chatBox.innerHTML += `<div class="ai-msg">Lỗi kết nối.</div>`;
            }
        }

        document.getElementById('user-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') sendMessage();
        });
    </script>
</body>
</html>
"""

# ---------- Các route ----------
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    learned = ai_vip.learn_from_input(user_message)
    if learned:
        reply = learned
    else:
        reply = ai_vip.respond(user_message)
    return jsonify({'reply': reply})

# ---------- Chạy máy chủ ----------
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ============================================
# HƯỚNG DẪN THÊM FILE VÀ TRIỂN KHAI TRÊN RENDER:
# 1. Tạo file `ai.py` với nội dung trên trong thư mục repo.
# 2. Cập nhật `requirements.txt` thêm dòng:
#       scikit-learn
# 3. Cập nhật `Procfile` thành:
#       web: gunicorn ai:app
# 4. Đẩy lên GitHub:
#       git add ai.py requirements.txt Procfile
#       git commit -m "Add AI VIP server"
#       git push origin main
# 5. Tạo Web Service mới trên Render trỏ vào repo này,
#    Render sẽ tự build và chạy AI VIP.
# ============================================
