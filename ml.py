import numpy as np
from sklearn.ensemble import RandomForestRegressor
import logging
from api import SUPPORTED_COINS, get_historical_data
from utils import main_keyboard  # Импортируем main_keyboard из utils.py

logger = logging.getLogger(__name__)

def calculate_features(prices, volumes):
    prices = np.array(prices)
    volumes = np.array(volumes)
    sma_7 = np.convolve(prices, np.ones(7)/7, mode='valid')  # Скользящее среднее
    delta = np.diff(prices)  # Изменения цены
    return np.column_stack((
        range(len(prices)),
        volumes,
        np.pad(sma_7, (len(prices) - len(sma_7), 0), 'edge'),
        np.pad(delta, (1, 0), 'constant')
    ))

async def forecast(update, context, investment):
    prices = context.bot_data.get("prices", {})
    if not prices:
        await update.message.reply_text(
            "❌ Ошибка получения цен. Попробуйте позже.",
            reply_markup=main_keyboard()  # Используем импортированную main_keyboard
        )
        return
    recommendations = []
    for coin, info in SUPPORTED_COINS.items():
        current_price = prices.get(coin)
        if not current_price:
            logger.warning(f"Нет цены для {coin}")
            continue
        try:
            prices_hist, volumes_hist = await get_historical_data(info["id"], 30)
            if len(prices_hist) < 7:
                future_price = current_price * 1.05
                logger.info(f"Мало данных для {coin}, используем fallback")
            else:
                X = calculate_features(prices_hist, volumes_hist)
                y = np.array(prices_hist)
                model = RandomForestRegressor(n_estimators=100, random_state=42)
                model.fit(X, y)
                future_X = calculate_features(
                    prices_hist + [current_price] * 7,
                    volumes_hist + [volumes_hist[-1]] * 7
                )[-1:]
                future_price = model.predict(future_X)[0]
                logger.info(f"Прогноз для {coin} успешен")
        except Exception as e:
            logger.error(f"Ошибка ML для {coin}: {e}")
            future_price = current_price * 1.05
        profit = (future_price - current_price) * (investment / current_price)
        if profit >= 10:
            recommendations.append({
                "coin": coin.upper(), "emoji": info["emoji"],
                "profit": profit, "future_price": future_price,
                "current_price": current_price
            })
    recommendations.sort(key=lambda x: x["profit"], reverse=True)
    if recommendations:
        response = "📈 *Рекомендации для инвестиций:*\n\n"
        for rec in recommendations:
            response += (
                f"{rec['emoji']} {rec['coin']}\nПрогноз прибыли: ${rec['profit']:.2f}\n"
                f"Текущая цена: ${rec['current_price']:.2f}\n"
                f"Цена через 7 дней: ${rec['future_price']:.2f}\n\n"
            )
    else:
        response = "❌ Нет подходящих монет для прогноза."
    await update.message.reply_text(response, reply_markup=main_keyboard(), parse_mode="Markdown")