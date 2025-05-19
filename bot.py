import os
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

# Обработка кнопки Help
async def handle_help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Здесь будет:\n"
        "- 🔄 Смена модели (Gemini / GPT / Gemini Pro)\n"
        "- 🤖 Другие мои боты\n"
        "- 💡 Как пользоваться\n\n"
        "⏳ В разработке."
    )

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Help$"), handle_help_button))

    app.run_polling()

if __name__ == "__main__":
    main()
