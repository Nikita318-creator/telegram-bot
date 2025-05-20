import os
import asyncio
import time
from collections import defaultdict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)
from model_manager import AIModelManager, AIModelType

ai_model_manager = AIModelManager()

RATE_LIMIT_SECONDS = 1
user_last_message_time = defaultdict(lambda: 0)

MAX_CONCURRENT_API_CALLS = 10
MAX_QUEUE_SIZE = 200

api_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)

async def process_api_queue(worker_id):
    while True:
        user_id, user_text, update = await api_queue.get()
        try:
            print(f"[Worker {worker_id}] Processing request from {user_id}")
            start = time.time()
            response = await ai_model_manager.query_api_async(user_text)  # ← async вариант
            elapsed = time.time() - start
            print(f"[Worker {worker_id}] Response in {elapsed:.2f}s")
            await update.message.reply_text(response)
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {str(e)}")
        finally:
            api_queue.task_done()

async def monitor_queue():
    while True:
        print(f"[Queue Monitor] Queue size: {api_queue.qsize()}")
        await asyncio.sleep(10)

async def start_queue_processing(application: ContextTypes.DEFAULT_TYPE):
    for i in range(MAX_CONCURRENT_API_CALLS):
        asyncio.create_task(process_api_queue(i))
    asyncio.create_task(monitor_queue())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Help"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Yo! I'm alive.", reply_markup=reply_markup)

async def models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "\n".join(
        f"{model.name}: {'Доступна' if ai_model_manager.model_limits[model] else 'Лимит исчерпан'}"
        for model in ai_model_manager.model_limits
    )
    await update.message.reply_text(
        f"Текущая модель: {ai_model_manager.current_model.name}\nСтатус моделей:\n{status}"
    )

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
    await update.message.reply_text("Выбери, что хочешь узнать 👇", reply_markup=reply_markup)

async def handle_inline_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    responses = {
        "change_model": "🔄 Здесь будет выбор модели: Gemini / Mistral / Pro (ещё не подключено)",
        "other_bots": "🤖 Здесь появятся ссылки на других твоих ботов",
        "how_to_use": "💡 Просто пиши мне, а я отвечаю — как чат с ИИ. Остальное появится позже.",
    }
    await query.edit_message_text(responses.get(query.data, "Что-то пошло не так 😕"))

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    current_time = time.time()

    if current_time - user_last_message_time[user_id] < RATE_LIMIT_SECONDS:
        await update.message.reply_text("Слишком много сообщений! Подожди секунду.")
        return
    user_last_message_time[user_id] = current_time

    if not any(ai_model_manager.get_api_key(model) for model in ai_model_manager.model_limits):
        await update.message.reply_text("API ключи не настроены.")
        return

    if api_queue.full():
        await update.message.reply_text("Сервер на пределе, подожди чуть-чуть 😰")
        return

    await update.message.chat.send_action(action="typing")
    await api_queue.put((user_id, user_text, update))

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("models", models))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Help$"), handle_help_button))
    app.add_handler(CallbackQueryHandler(handle_inline_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.Regex("(?i)^help$"), handle_user_message))

    app.post_init = start_queue_processing

    app.run_polling()

if __name__ == "__main__":
    main()
