import asyncio
import aiohttp
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_EXPIRY = 300  # 5 минут

SUPPORTED_COINS = {
    "ton": {"id": "the-open-network", "name": "TON", "emoji": "💎"},
    "ada": {"id": "cardano", "name": "Cardano", "emoji": "🐳"},
    "btc": {"id": "bitcoin", "name": "Bitcoin", "emoji": "₿"},
    "eth": {"id": "ethereum", "name": "Ethereum", "emoji": "⧫"},
    "sol": {"id": "solana", "name": "Solana", "emoji": "🔥"},
    "doge": {"id": "dogecoin", "name": "Dogecoin", "emoji": "🐶"},
}

# Мок контекста Telegram-бота
class MockContext:
    def __init__(self):
        self.bot_data = {}

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def fetch_price(session, coin, symbol):
    url = "https://api.bybit.com/v5/market/tickers"
    params = {"category": "spot", "symbol": symbol}
    try:
        async with session.get(url, params=params, timeout=10) as response:
            logger.info(f"Запрос для {coin} ({symbol}): статус {response.status}")
            if response.status != 200:
                text = await response.text()
                logger.error(f"Ошибка API: {text}")
                raise Exception(f"Ошибка API для {coin}: {response.status}")
            data = await response.json()
            logger.debug(f"Ответ API для {coin}: {data}")
            if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                price = float(data["result"]["list"][0]["lastPrice"])
                logger.info(f"Цена для {coin}: {price}")
                return coin, price
            logger.warning(f"Нет данных для {coin} в ответе API")
            return coin, None
    except Exception as e:
        logger.error(f"Ошибка получения цены {coin}: {e}")
        raise

async def get_prices(context):
    now = datetime.now().timestamp()
    cached_prices = context.bot_data.get("prices", {})
    last_update = context.bot_data.get("last_price_update", 0)

    if now - last_update < CACHE_EXPIRY and cached_prices:
        logger.info("Используем кэшированные цены")
        return cached_prices

    symbols = {
        "ton": "TONUSDT", "ada": "ADAUSDT", "btc": "BTCUSDT",
        "eth": "ETHUSDT", "sol": "SOLUSDT", "doge": "DOGEUSDT"
    }

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_price(session, coin, symbol) for coin, symbol in symbols.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    prices = {}
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Ошибка в запросе: {result}")
        elif result[1] is not None:
            prices[result[0]] = result[1]

    if prices:
        context.bot_data["prices"] = prices
        context.bot_data["last_price_update"] = now
        logger.info(f"Цены обновлены: {prices}")
    elif cached_prices and (now - last_update < CACHE_EXPIRY * 2):
        logger.warning("Используем устаревшие данные")
        return cached_prices
    else:
        logger.error("Не удалось получить цены, кэш пуст или устарел")

    return prices

async def get_historical_data(coin_id, days=30):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                logger.info(f"Запрос исторических данных для {coin_id}: статус {response.status}")
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"Ошибка API CoinGecko: {text}")
                    return [], []
                data = await response.json()
                prices = [p[1] for p in data.get("prices", [])[-days:]]
                volumes = [v[1] for v in data.get("total_volumes", [])[-days:]]
                logger.info(f"Получены исторические данные для {coin_id}")
                return prices, volumes
    except Exception as e:
        logger.error(f"Ошибка получения исторических данных: {e}")
        return [], []

# Тестовый запуск
if __name__ == "__main__":
    context = MockContext()
    prices = asyncio.run(get_prices(context))
    print("\nАктуальные цены:")
    for coin, price in prices.items():
        info = SUPPORTED_COINS[coin]
        print(f"{info['emoji']} {info['name']} ({coin.upper()}): ${price:.4f}")
