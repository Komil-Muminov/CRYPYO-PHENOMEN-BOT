import json
import os
import logging
from api import SUPPORTED_COINS
from datetime import datetime

logger = logging.getLogger(__name__)
DATA_FILE = "portfolio.json"

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"purchases": []}

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        logger.error(f"Ошибка сохранения данных: {e}")

async def show_portfolio(query, context, prices):
    purchases = context.bot_data["purchases"]
    if not purchases:
        await query.edit_message_text("💼 Портфель пуст", reply_markup=back_keyboard())
        return
    coins = {}
    total_invested = total_current = 0
    for purchase in purchases:
        coin = purchase["coin"].lower()
        coins[coin] = coins.get(coin, {"amount": 0, "cost": 0})
        coins[coin]["amount"] += purchase["amount"]
        coins[coin]["cost"] += purchase["cost"]
        total_invested += purchase["cost"]
    response = "📊 *Ваш портфель:*\n"
    for coin, info in coins.items():
        coin_emoji = SUPPORTED_COINS[coin]["emoji"]
        price = prices.get(coin, 0.0)
        if price == 0.0:
            logger.warning(f"Цена для {coin.upper()} не найдена, используется 0.0")
        current_value = info["amount"] * price
        profit = current_value - info["cost"]
        profit_percent = (profit / info["cost"]) * 100 if info["cost"] > 0 else 0
        total_current += current_value
        response += (
            f"{coin_emoji} *{coin.upper()}*\nКол-во: {info['amount']:.2f}\n"
            f"Вложено: ${info['cost']:.2f}\nТекущая стоимость: ${current_value:.2f}\n"
            f"Прибыль: {profit:+.2f}$ ({profit_percent:+.2f}%)\n\n"
        )
    total_profit = total_current - total_invested
    total_percent = (total_profit / total_invested) * 100 if total_invested > 0 else 0
    response += (
        f"💰 *Итого:*\nВложено: ${total_invested:.2f}\n"
        f"Текущая стоимость: ${total_current:.2f}\n"
        f"Прибыль: {total_profit:+.2f}$ ({total_percent:+.2f}%)"
    )
    await query.edit_message_text(response, reply_markup=back_keyboard(), parse_mode="Markdown")

async def show_history(query, context):
    purchases = context.bot_data["purchases"]
    if not purchases:
        await query.edit_message_text("📜 История пуста", reply_markup=back_keyboard())
        return
    history = [
        f"{i}. {p['date']} - {SUPPORTED_COINS[p['coin'].lower()]['emoji']} "
        f"{p['amount']} {p['coin']} за ${p['cost']:.2f}"
        for i, p in enumerate(purchases, 1)
    ]
    response = "📖 *История покупок:*\n" + "\n".join(history)
    await query.edit_message_text(response, reply_markup=back_keyboard(), parse_mode="Markdown")

def back_keyboard():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back")]])