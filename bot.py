from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Yo! I'm alive.")

app = ApplicationBuilder().token("8166651042:AAH4PGznpoauA7TWIXga2VWgQHgw9cIsXg0").build()
app.add_handler(CommandHandler("start", start))

app.run_polling()
