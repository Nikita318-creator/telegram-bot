import os
import requests
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)
from telegram import Update, ReplyKeyboardMarkup

# Команда /start с кнопкой Help
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Help"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Yo! I'm alive.", reply_markup=reply_markup
    )

# Обработка кнопки Help — теперь с inline-кнопками
async def handle_help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🔄 Сменить модель", callback_data="change_model"),
            InlineKeyboardButton("🤖 Другие боты", callback_data="other_bots"),
        ],
        [
            InlineKeyboardButton("💡 Как пользоваться", callback_data="how_to_use"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Выбери, что хочешь узнать 👇", reply_markup=reply_markup
    )

# Обработка inline-кнопок Help
async def handle_inline_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # чтобы Telegram не показывал загрузку бесконечно

    if query.data == "change_model":
        await query.edit_message_text("🔄 Здесь будет выбор модели: Gemini / GPT / Pro (ещё не подключено)")
    elif query.data == "other_bots":
        await query.edit_message_text("🤖 Здесь появятся ссылки на других твоих ботов")
    elif query.data == "how_to_use":
        await query.edit_message_text("💡 Просто пиши мне, а я отвечаю — как чат с ИИ. Остальное появится позже.")
    else:
        await query.edit_message_text("Что-то пошло не так 😕")

# Синхронный запрос к Gemini API через requests с OAuth-токеном
def query_gemini_api_sync(prompt: str, oauth_token: str) -> str:
    url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-lite:generateContent"
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "Content-Type": "application/json"
    }
    json_data = {
        "prompt": {
            "text": prompt
        },
        "temperature": 0.7,
        "maxOutputTokens": 256
    }

    try:
        resp = requests.post(url, headers=headers, json=json_data, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("candidates", [{}])[0].get("output", "Нет ответа от Gemini")
    except Exception as e:
        return f"Ошибка при запросе к Gemini API: {e}"

# Асинхронный хендлер сообщений — запускает sync функцию в отдельном потоке
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    oauth_token = os.getenv("GEMINI_OAUTH_TOKEN")
    if not oauth_token:
        await update.message.reply_text("OAuth токен Gemini не настроен в переменных окружения.")
        return

    await update.message.chat.send_action(action="typing")

    response = await asyncio.to_thread(query_gemini_api_sync, user_text, oauth_token)
    await update.message.reply_text(response)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Help$"), handle_help_button))
    app.add_handler(CallbackQueryHandler(handle_inline_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.Regex("(?i)^help$"),handle_user_message))
    
    app.run_polling()

if __name__ == "__main__":
    main()

