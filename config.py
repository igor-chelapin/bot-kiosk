import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_BALANCE_URL = "https://openrouter.ai/api/v1/auth/key"

# База данных
DATABASE_PATH = os.getenv("DATABASE_PATH", "./bot_database.db")

# Модель Grok 2 Mini
GROK_MODEL = "x-ai/grok-3-mini"
GROK_INPUT_PRICE = 0.0002  # $ за 1K токенов
GROK_OUTPUT_PRICE = 0.0002

# Бесплатные модели
# Бесплатные модели
# Бесплатные модели
# Бесплатные модели (актуальные на OpenRouter)
# Бесплатные модели (с GLM-4.5 Air)
FREE_MODELS = [
    {
        "id": "qwen/qwen3-next-80b-a3b-instruct:free",
        "name": "🐉 Qwen3 80B",
        "description": "⚡ Пробуем первую",
        "command": "qwen3"
    },
    {
        "id": "z-ai/glm-4.5-air:free",
        "name": "🧪 GLM-4.5 Air (резервная)",
        "description": "✅ Стабильная модель",
        "command": "glm"
    },
    {
        "id": "openrouter/auto",
        "name": "🤖 Auto Router",
        "description": "🎯 Последний шанс",
        "command": "auto"
    }
]
# Цены и лимиты
PRICE_PER_1K_TOKENS_RUB = float(os.getenv("PRICE_PER_1K_TOKENS_RUB", 7.5))
STARS_TO_RUB = float(os.getenv("STARS_TO_RUB", 1.5))
MIN_OR_BALANCE_ALERT = float(os.getenv("MIN_OR_BALANCE_ALERT", 5.0))
FREE_DAILY_LIMIT_TOKENS = int(os.getenv("FREE_DAILY_LIMIT_TOKENS", 5000))

# Пакеты токенов для премиум
PACKAGES = [
    {
        "tokens": 5000,
        "price_rub": 50,
        "stars": 35,
        "name": "Пробный",
        "description": "Попробуй Grok"
    },
    {
        "tokens": 25000,
        "price_rub": 200,
        "stars": 135,
        "name": "Базовый",
        "description": "Для первых диалогов"
    },
    {
        "tokens": 100000,
        "price_rub": 750,
        "stars": 500,
        "name": "ОПТИМАЛЬНЫЙ",
        "description": "300+ ответов"
    },
    {
        "tokens": 500000,
        "price_rub": 3000,
        "stars": 2000,
        "name": "Профи",
        "description": "Для активных"
    }
]