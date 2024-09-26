import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Получаем токен из переменной окружения
TOKEN = os.getenv('ANYRUN_SB_API_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Привет! Я бот.')

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(update.message.text)

def setup_telegram_bot():
    if not TOKEN:
        raise EnvironmentError("Токен бота не найден. Убедитесь, что переменная окружения ANYRUN_SB_API_TOKEN установлена.")
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    return application

def run_telegram_bot(application):
    application.run_polling()
