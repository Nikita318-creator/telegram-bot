import os
import aiohttp
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

# Запрос к Gemini API (пример)
async def query_gemini_api(prompt: str, api_key: str) -> str:
    url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-lite:generateContent"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    json_data = {
        "prompt": {
            "text": prompt
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=json_data) as resp:
                if resp.status != 200:
                    return f"Ошибка API Gemini: {resp.status}"
                data = await resp.json()
                # В ответе ищем candidates[0].output
                return data.get("candidates", [{}])[0].get("output", "Нет ответа от Gemini")
    except Exception as e:
        return f"Ошибка при запросе к Gemini API: {e}"

# Обработка любых текстовых сообщений (кроме Help) — ответ Gemini
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        await update.message.reply_text("API ключ Gemini не настроен.")
        return

    await update.message.chat.send_action(action="typing")  # Показываем статус "печатает"

    response = await query_gemini_api(user_text, api_key)
    await update.message.reply_text(response)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Help$"), handle_help_button))
    app.add_handler(CallbackQueryHandler(handle_inline_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.Regex("^Help$"), handle_user_message))

    app.run_polling()

if __name__ == "__main__":
    main()

