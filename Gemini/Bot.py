import os
import threading
from flask import Flask
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from google import genai
from google.genai import types

# Tải biến môi trường từ file .env (nếu chạy ở máy cá nhân)
load_dotenv()

# Lấy các API Key từ biến môi trường
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Chat ID của nhóm PT Game [TX68] (Chỉ cho phép bot trả lời trong nhóm này)
ALLOWED_GROUP_ID = -1004374217260

# ==========================================
# 1. TẠO WEB SERVER KHỦNG GIẢ LẬP MỞ CỔNG CHO RENDER
# ==========================================
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot Telegram Gemini [CasioWorld] đang chạy online 24/7!"

def run_flask():
    # Lấy cổng do Render cấp (mặc định 10000)
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

# ==========================================
# 2. KHỞI TẠO AI GEMINI
# ==========================================
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = """
Bạn là Gemini - một trợ lý AI thân thiện, linh hoạt, ngắn gọn, đi thẳng vào vấn đề và dễ hiểu.
"""

chat_session = client.chats.create(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.7,
    )
)

# ==========================================
# 3. XỬ LÝ LỆNH /g TRONG TELEGRAM
# ==========================================
async def handle_g_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kiểm tra nếu lệnh được gửi từ đúng nhóm của bạn
    if update.effective_chat.id != ALLOWED_GROUP_ID:
        await update.message.reply_text("Bot này được cấu hình chỉ hoạt động riêng trong nhóm PT Game [TX68]!")
        return

    # Lấy nội dung câu hỏi sau lệnh /g
    user_query = " ".join(context.args)

    if not user_query:
        await update.message.reply_text("Bạn chưa nhập câu hỏi! Ví dụ: /g 1+1=?")
        return

    # Hiện trạng thái "đang gõ..." trong nhóm
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # Gửi câu hỏi cho Gemini
        response = chat_session.send_message(user_query)
        # Phản hồi lại tin nhắn trong nhóm
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(f"Có lỗi xảy ra: {str(e)}")

# ==========================================
# 4. CHẠY CHƯƠNG TRÌNH
# ==========================================
if __name__ == "__main__":
    # Chạy Flask Server ở 1 Thread riêng để Render cấp trạng thái "Live"
    threading.Thread(target=run_flask, daemon=True).start()

    # Khởi chạy Bot Telegram
    telegram_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("g", handle_g_command))

    print("Bot Telegram Gemini đang hoạt động...")
    telegram_app.run_polling()
    
