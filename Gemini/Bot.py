import os
import threading
from flask import Flask
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from google import genai
from google.genai import types

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 1. TẠO CỔNG HTTP GIẢ LẬP ĐỂ CUNG CẤP CHO RENDER
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot Telegram Gemini đang chạy ngon lành!"

def run_flask():
    # Lấy PORT do Render cấp (mặc định là 10000)
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

# 2. CẤU HÌNH GEMINI BOT
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = "Bạn là Gemini - một trợ lý AI thân thiện, linh hoạt, ngắn gọn, đi thẳng vào vấn đề và dễ hiểu."

chat_session = client.chats.create(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.7,
    )
)

async def handle_g_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = " ".join(context.args)

    if not user_query:
        await update.message.reply_text("Bạn chưa nhập câu hỏi! Ví dụ: /g 1+1=?")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = chat_session.send_message(user_query)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(f"Có lỗi xảy ra: {str(e)}")

# 3. KHỞI CHẠY CẢ 2 CÙNG LÚC
if __name__ == "__main__":
    # Chạy Flask ở một luồng riêng (Thread) để mở Cổng cho Render nhận diện
    threading.Thread(target=run_flask, daemon=True).start()

    # Chạy Bot Telegram
    telegram_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("g", handle_g_command))
    
    print("Bot Telegram Gemini đang hoạt động...")
    telegram_app.run_polling()
                           
