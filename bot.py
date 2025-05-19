import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

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
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Выбери, что хочешь узнать 👇", reply_markup=reply_markup
    )
    
async def handle_inline_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # чтобы Telegram не крутил бесконечно "loading..."
    
    if query.data == "change_model":
        await query.edit_message_text("🔄 Здесь будет выбор модели: Gemini / GPT / Pro (ещё не подключено)")
    elif query.data == "other_bots":
        await query.edit_message_text("🤖 Здесь появятся ссылки на других твоих ботов")
    elif query.data == "how_to_use":
        await query.edit_message_text("💡 Просто пиши мне, а я отвечаю — как чат с ИИ. Остальное появится позже.")
    else:
        await query.edit_message_text("Что-то пошло не так 😕")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Help$"), handle_help_button))
    app.add_handler(CallbackQueryHandler(handle_inline_buttons))

    app.run_polling()

if __name__ == "__main__":
    main()
