import asyncio
import logging
from dotenv import load_dotenv
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from api import get_prices, SUPPORTED_COINS
from portfolio import load_data, save_data, show_portfolio, show_history, back_keyboard
from utils import main_keyboard  # Импортируем main_keyboard из utils.py
from ml import forecast  # Импортируем функцию forecast

logging.basicConfig(
    filename="bot.log",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    encoding="utf-8"  # Явно указываем кодировку
)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CACHE_EXPIRY = 300

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Выберите действие:", reply_markup=main_keyboard())

def coin_selection_keyboard():
    keyboard = [
        [InlineKeyboardButton(f"{v['emoji']} {k.upper()}", callback_data=f"select_coin_{k}") 
         for k, v in SUPPORTED_COINS.items()]
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back":
        await query.edit_message_text("Главное меню:", reply_markup=main_keyboard())
    elif query.data == "add":
        await query.edit_message_text("Выберите монету:", reply_markup=coin_selection_keyboard())
    elif query.data.startswith("select_coin_"):
        coin = query.data.split("_")[2]
        context.user_data["selected_coin"] = coin
        await query.edit_message_text(
            f"Вы выбрали {coin.upper()}. Введите: КОЛИЧЕСТВО СУММА\nПример: 100 500",
            reply_markup=back_keyboard()
        )
        context.user_data["awaiting_add"] = True
    elif query.data == "forecast":
        await query.edit_message_text(
            "📈 *Прогноз прибыли за 7 дней*\n\nВведите сумму (USD):\nПример: `100`",
            reply_markup=back_keyboard(), parse_mode="Markdown"
        )
        context.user_data["awaiting_forecast"] = True
    elif query.data == "portfolio":
        prices = await get_prices(context)
        await show_portfolio(query, context, prices)
    elif query.data == "history":
        await show_history(query, context)
    elif query.data == "help":
        help_text = (
            "📚 *Справка:*\n➕ Добавить покупку 💰 - Новая транзакция\n"
            "📂 Мой портфель 📊 - Состояние инвестиций\n📖 История 📜 - Все операции\n"
            "📈 Прогноз прибыли за 7 дней 📈 - Анализ прибыли\n❓ Помощь ℹ️ - Инфо о боте\n"
            "Формат: `КОЛИЧЕСТВО СУММА`\nПример: `100 500` после выбора монеты"
        )
        await query.edit_message_text(help_text, reply_markup=back_keyboard(), parse_mode="Markdown")

async def add_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_add", False):
        return
    text = update.message.text.split()
    coin = context.user_data.get("selected_coin")
    if len(text) != 2 or not coin:
        await update.message.reply_text("❌ Неверный формат\nПример: 100 500", reply_markup=back_keyboard())
        return
    try:
        amount = float(text[0])
        cost = float(text[1])
        if amount <= 0 or cost < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Неверные значения\nПример: 100 500", reply_markup=back_keyboard())
        return
    coin_emoji = SUPPORTED_COINS[coin]["emoji"]
    context.bot_data["purchases"].append({
        "coin": coin.upper(), "amount": amount, "cost": cost,
        "date": datetime.now().strftime("%Y-%m-%d")
    })
    save_data(context.bot_data)
    await update.message.reply_text(
        f"{coin_emoji} ✅ Добавлено {amount} {coin.upper()} на ${cost:.2f}",
        reply_markup=main_keyboard()
    )
    context.user_data["awaiting_add"] = False
    context.user_data["selected_coin"] = None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_forecast", False):
        try:
            investment = float(update.message.text)
            if investment <= 0:
                raise ValueError
            await forecast(update, context, investment)
            context.user_data["awaiting_forecast"] = False
        except ValueError:
            await update.message.reply_text(
                "❌ Неверная сумма\nПример: `100`", reply_markup=back_keyboard(), parse_mode="Markdown"
            )
    elif context.user_data.get("awaiting_add", False):
        await add_purchase(update, context)
    else:
        await update.message.reply_text("Используйте кнопки для навигации.", reply_markup=main_keyboard())

async def update_prices_task(context: ContextTypes.DEFAULT_TYPE):
    while True:
        try:
            prices = await get_prices(context)
            logger.info(f"Цены успешно обновлены: {prices}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении цен: {e}")
        await asyncio.sleep(CACHE_EXPIRY)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    logger.info("Инициализация бота")
    context_data = load_data()
    app = ApplicationBuilder().token(TOKEN).build()
    app.bot_data.update(context_data)
    logger.info("Планирование фоновой задачи обновления цен")
    app.job_queue.run_repeating(update_prices_task, interval=CACHE_EXPIRY, first=0)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    logger.info("Запуск бота")
    app.run_polling()

if __name__ == "__main__":
    main()