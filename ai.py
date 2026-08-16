# ============================================
# File: ai.py
# Chức năng: Máy chủ Flask cho "Code AI VIP" - trợ lý lập trình
# tự học bằng TF-IDF (không dùng API key của bên thứ ba).
# Giao diện chat lấy cảm hứng từ Claude (bong bóng chat, dark mode).
# Chạy độc lập trên Render bằng lệnh:
#   gunicorn ai:app
# ============================================

import os
import json
import numpy as np
from flask import Flask, request, jsonify, render_template_string
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

KB_FILE = "knowledge_base.json"  # nơi lưu dữ liệu học được, để không mất khi restart


class CodeAIVIP:
    def __init__(self):
        # Cơ sở tri thức ban đầu, thiên về lập trình
        self.default_kb = [
            {"question": "bạn tên gì", "answer": "Tôi là Code AI VIP, trợ lý lập trình của riêng bạn."},
            {"question": "bạn làm được gì", "answer": "Tôi có thể giải thích khái niệm lập trình, gỡ lỗi code, và học thêm kiến thức mới từ bạn."},
            {"question": "ai tạo ra bạn", "answer": "Tôi được tạo ra và huấn luyện bởi chính bạn, không dùng API key của ai khác."},
            {"question": "python là gì", "answer": "Python là ngôn ngữ lập trình bậc cao, cú pháp rõ ràng, dùng nhiều trong web, AI, khoa học dữ liệu."},
            {"question": "list và tuple khác nhau thế nào trong python", "answer": "List có thể thay đổi (mutable), dùng dấu [], còn tuple không thể thay đổi (immutable), dùng dấu ()."},
            {"question": "hàm là gì trong lập trình", "answer": "Hàm là một khối lệnh được đặt tên, có thể nhận tham số và trả về giá trị, giúp tái sử dụng code."},
            {"question": "vòng lặp for và while khác nhau thế nào", "answer": "For dùng khi biết trước số lần lặp hoặc duyệt qua tập hợp; while dùng khi lặp theo điều kiện chưa biết trước số lần."},
            {"question": "git là gì", "answer": "Git là hệ thống quản lý phiên bản, giúp theo dõi thay đổi code và làm việc nhóm qua các lệnh như commit, push, pull."},
            {"question": "api là gì", "answer": "API (Application Programming Interface) là giao diện cho phép các chương trình giao tiếp với nhau."},
            {"question": "flask là gì", "answer": "Flask là một web framework nhẹ của Python, dùng để xây dựng web server và API nhanh chóng."},
            {"question": "javascript là gì", "answer": "JavaScript là ngôn ngữ lập trình chạy chủ yếu trên trình duyệt, dùng để làm web tương tác."},
            {"question": "html là gì", "answer": "HTML là ngôn ngữ đánh dấu dùng để xây dựng cấu trúc nội dung trang web."},
            {"question": "css là gì", "answer": "CSS dùng để định dạng, tạo kiểu (màu sắc, bố cục) cho trang web."},
            {"question": "biến là gì trong lập trình", "answer": "Biến là nơi lưu trữ dữ liệu, có tên gọi, có thể thay đổi giá trị trong quá trình chạy chương trình."},
            {"question": "cách debug code", "answer": "Dùng print/log để kiểm tra giá trị biến, dùng breakpoint trong IDE, hoặc đọc kỹ thông báo lỗi (traceback) để tìm nguyên nhân."},
            {"question": "tạm biệt", "answer": "Tạm biệt! Hẹn gặp lại khi bạn cần hỏi thêm về lập trình."}
        ]
        self.knowledge_base = self._load_kb()
        self._rebuild_vectors()

    # ---------- Lưu / tải dữ liệu học ----------
    def _load_kb(self):
        if os.path.exists(KB_FILE):
            try:
                with open(KB_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        return data
            except Exception:
                pass
        return list(self.default_kb)

    def _save_kb(self):
        try:
            with open(KB_FILE, "w", encoding="utf-8") as f:
                json.dump(self.knowledge_base, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # nếu môi trường không cho ghi file (vd đĩa read-only) thì bỏ qua

    def _rebuild_vectors(self):
        self.questions = [item["question"] for item in self.knowledge_base]
        self.answers = [item["answer"] for item in self.knowledge_base]
        self.vectorizer = TfidfVectorizer()
        self.question_vectors = self.vectorizer.fit_transform(self.questions)

    # ---------- Học thêm ----------
    def train(self, new_qa_pairs):
        for q, a in new_qa_pairs:
            self.knowledge_base.append({"question": q, "answer": a})
        self._rebuild_vectors()
        self._save_kb()

    # ---------- Trả lời ----------
    def respond(self, user_input):
        if not user_input.strip():
            return "Vui lòng nhập câu hỏi."
        user_vector = self.vectorizer.transform([user_input])
        similarities = cosine_similarity(user_vector, self.question_vectors).flatten()
        best_idx = int(np.argmax(similarities))
        if similarities[best_idx] > 0.2:
            return self.answers[best_idx]
        else:
            return ("Tôi chưa có câu trả lời cho câu này. "
                    "Hãy dạy tôi theo cú pháp: học|câu hỏi|câu trả lời")

    def learn_from_input(self, text):
        parts = text.split("|")
        if len(parts) == 3 and parts[0].strip().lower() == "học":
            q = parts[1].strip()
            a = parts[2].strip()
            if q and a:
                self.train([(q, a)])
                return "Đã học xong, cảm ơn bạn!"
        return None


ai_vip = CodeAIVIP()

# ---------- Giao diện Web (phong cách giống Claude) ----------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Code AI VIP</title>
<style>
  :root {
    --bg: #1a1a19;
    --panel: #232322;
    --bubble-user: #3a3a38;
    --bubble-ai: #2b2b29;
    --accent: #d97757;
    --text: #ece9e6;
    --muted: #9a968f;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    height: 100vh;
    display: flex;
    flex-direction: column;
  }
  header {
    padding: 16px 20px;
    border-bottom: 1px solid #333;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  header .logo {
    width: 28px; height: 28px;
    border-radius: 8px;
    background: var(--accent);
    display: flex; align-items: center; justify-content: center;
    font-weight: bold; color: #1a1a19;
  }
  header h1 { font-size: 16px; margin: 0; font-weight: 600; }
  header span { font-size: 12px; color: var(--muted); margin-left: 4px; }

  #chat-box {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    max-width: 760px;
    width: 100%;
    margin: 0 auto;
  }
  .row { display: flex; margin-bottom: 18px; }
  .row.user { justify-content: flex-end; }
  .row.ai { justify-content: flex-start; }
  .bubble {
    max-width: 75%;
    padding: 12px 16px;
    border-radius: 14px;
    line-height: 1.5;
    font-size: 14.5px;
    white-space: pre-wrap;
  }
  .row.user .bubble { background: var(--bubble-user); border-bottom-right-radius: 4px; }
  .row.ai .bubble { background: var(--bubble-ai); border: 1px solid #333; border-bottom-left-radius: 4px; }
  .avatar {
    width: 26px; height: 26px; border-radius: 6px;
    background: var(--accent); color: #1a1a19;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: bold; margin-right: 10px; flex-shrink: 0;
  }

  #input-area {
    border-top: 1px solid #333;
    padding: 16px 20px 22px;
  }
  #input-inner {
    max-width: 760px;
    margin: 0 auto;
    display: flex;
    align-items: flex-end;
    gap: 10px;
    background: var(--panel);
    border: 1px solid #3a3a38;
    border-radius: 16px;
    padding: 10px 12px;
  }
  #user-input {
    flex: 1;
    resize: none;
    border: none;
    outline: none;
    background: transparent;
    color: var(--text);
    font-size: 14.5px;
    max-height: 140px;
    font-family: inherit;
  }
  button#send-btn {
    background: var(--accent);
    border: none;
    color: #1a1a19;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 10px;
    cursor: pointer;
    font-size: 13.5px;
  }
  button#send-btn:disabled { opacity: 0.5; cursor: default; }
  .hint { text-align: center; color: var(--muted); font-size: 11.5px; margin-top: 8px; }
</style>
</head>
<body>

<header>
  <div class="logo">C</div>
  <h1>Code AI VIP <span>trợ lý lập trình tự học, không dùng API ngoài</span></h1>
</header>

<div id="chat-box">
  <div class="row ai">
    <div class="avatar">C</div>
    <div class="bubble">Chào bạn! Mình là Code AI VIP. Hỏi mình về lập trình, hoặc dạy mình kiến thức mới bằng cú pháp:
học|câu hỏi|câu trả lời</div>
  </div>
</div>

<div id="input-area">
  <div id="input-inner">
    <textarea id="user-input" rows="1" placeholder="Nhắn cho Code AI VIP..."></textarea>
    <button id="send-btn" onclick="sendMessage()">Gửi</button>
  </div>
  <div class="hint">AI học từ chính bạn, dữ liệu lưu cục bộ trên server.</div>
</div>

<script>
const chatBox = document.getElementById('chat-box');
const input = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

function addBubble(text, who) {
  const row = document.createElement('div');
  row.className = 'row ' + who;
  if (who === 'ai') {
    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = 'C';
    row.appendChild(avatar);
  }
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  row.appendChild(bubble);
  chatBox.appendChild(row);
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendMessage() {
  const message = input.value.trim();
  if (!message) return;
  addBubble(message, 'user');
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;

  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });
    const data = await response.json();
    addBubble(data.reply, 'ai');
  } catch (error) {
    addBubble('Lỗi kết nối tới server.', 'ai');
  } finally {
    sendBtn.disabled = false;
  }
}

input.addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
input.addEventListener('input', function() {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 140) + 'px';
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
    data = request.get_json(silent=True) or {}
    user_message = data.get('message', '')
    learned = ai_vip.learn_from_input(user_message)
    reply = learned if learned else ai_vip.respond(user_message)
    return jsonify({'reply': reply})


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'so_luong_kien_thuc': len(ai_vip.knowledge_base)})


# ---------- Chạy máy chủ ----------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ============================================
# HƯỚNG DẪN TRIỂN KHAI TRÊN RENDER:
# 1. Đặt file này tên là ai.py trong repo.
# 2. requirements.txt cần có:
#       flask
#       scikit-learn
#       numpy
#       gunicorn
# 3. Procfile:
#       web: gunicorn ai:app
# 4. Đẩy lên GitHub rồi tạo Web Service trên Render trỏ vào repo.
# 5. Lưu ý: trên Render free tier, ổ đĩa có thể bị reset mỗi lần
#    deploy lại (không phải mỗi lần restart do sleep), nên kiến
#    thức học thêm qua "học|...|..." có thể mất sau mỗi lần deploy mới.
#    Muốn lưu vĩnh viễn, nên dùng database (vd SQLite + Render Disk,
#    hoặc PostgreSQL) thay vì file JSON.
# ============================================
