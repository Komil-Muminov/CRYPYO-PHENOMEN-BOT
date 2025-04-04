from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Добавить покупку 💰", callback_data="add")],
        [InlineKeyboardButton("📂 Мой портфель 📊", callback_data="portfolio")],
        [InlineKeyboardButton("📖 История 📜", callback_data="history")],
        [InlineKeyboardButton("📈 Прогноз прибыли за 7 дней 📈", callback_data="forecast")],
        [InlineKeyboardButton("❓ Помощь ℹ️", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)