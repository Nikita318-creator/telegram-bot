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
from model_manager import AIModelManager, AIModelType

# Инициализация менеджера моделей
ai_model_manager = AIModelManager()

# Команда /start с кнопкой Help
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Help"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Yo! I'm alive.", reply_markup=reply_markup
    )

# Команда /models для отображения текущей модели и статуса лимитов
async def models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "\n".join(
        f"{model.name}: {'Доступна' if ai_model_manager.model_limits[model] else 'Лимит исчерпан'}"
        for model in ai_model_manager.model_limits
    )
    await update.message.reply_text(
        f"Текущая модель: {ai_model_manager.current_model.name}\nСтатус моделей:\n{status}"
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
    await query.answer()

    if query.data == "change_model":
        await query.edit_message_text("🔄 Здесь будет выбор модели: Gemini / Mistral / Pro (ещё не подключено)")
    elif query.data == "other_bots":
        await query.edit_message_text("🤖 Здесь появятся ссылки на других твоих ботов")
    elif query.data == "how_to_use":
        await query.edit_message_text("💡 Просто пиши мне, а я отвечаю — как чат с ИИ. Остальное появится позже.")
    else:
        await query.edit_message_text("Что-то пошло не так 😕")

# Асинхронный хендлер сообщений
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not any(ai_model_manager.get_api_key(model) for model in ai_model_manager.model_limits):
        await update.message.reply_text("API ключи не настроены.")
        return

    await update.message.chat.send_action(action="typing")

    response = await asyncio.to_thread(ai_model_manager.query_api_sync, user_text)
    await update.message.reply_text(response)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("models", models))  # Регистрация команды /models
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Help$"), handle_help_button))
    app.add_handler(CallbackQueryHandler(handle_inline_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.Regex("(?i)^help$"), handle_user_message))
    
    app.run_polling()

if __name__ == "__main__":
    main()
