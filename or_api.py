# -*- coding: utf-8 -*-
import logging
import random
import asyncio
import aiohttp
import json
from config import OPENROUTER_API_KEY, OPENROUTER_API_URL, GROK_MODEL, GROK_INPUT_PRICE, GROK_OUTPUT_PRICE
from free_models import FREE_MODELS_LIST as FREE_MODELS
import database
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Меняем INFO на DEBUG
)

logger = logging.getLogger(__name__)

# ========== ПРОВЕРКА БАЛАНСА OPENROUTER ==========
async def check_or_balance():
    """Проверка баланса OpenRouter"""
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get("https://openrouter.ai/api/v1/auth/key", headers=headers, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    balance = float(data.get("data", {}).get("balance", 0))
                    return balance
                else:
                    return 0.0
    except:
        return 0.0

# ========== GROK PREMIUM ==========
async def call_grok(user_id, prompt):
    """Вызывает Grok 2 Mini через OpenRouter (OpenAI-совместимый формат)"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/your_bot",
        "X-Title": "Grok Premium Bot"
    }
    
    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": "Ты Grok, полезный ассистент. Отвечай кратко и по делу на русском языке."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=30) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Grok API error: {response.status} - {error_text}")
                    return None, f"API Error: {response.status}"
                
                data = await response.json()
                
                prompt_tokens = data.get("usage", {}).get("prompt_tokens", 0)
                completion_tokens = data.get("usage", {}).get("completion_tokens", 0)
                total_tokens = data.get("usage", {}).get("total_tokens", prompt_tokens + completion_tokens)
                
                input_cost = (prompt_tokens / 1000) * GROK_INPUT_PRICE
                output_cost = (completion_tokens / 1000) * GROK_OUTPUT_PRICE
                our_cost_usd = input_cost + output_cost
                
                reply_text = data["choices"][0]["message"]["content"]
                
                return {
                    "text": reply_text,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "our_cost_usd": our_cost_usd
                }, None
                
    except Exception as e:
        logger.error(f"Error in call_grok: {e}")
        return None, str(e)

# ========== БЕСПЛАТНЫЕ МОДЕЛИ ==========
async def call_free_model(user_id, prompt, model_id):
    """Вызывает бесплатную модель через OpenRouter"""
    
    # Находим название модели
    model_name = model_id
    for m in FREE_MODELS:
        if m["id"] == model_id:
            model_name = m["name"]
            break
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/your_bot",
        "X-Title": "Free Model Bot"
    }
    
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "Ты полезный ассистент. Отвечай кратко и по делу на русском языке."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=20) as response:
                if response.status == 429:
                    logger.error(f"Rate limit for {model_id}")
                    return None, "RATE_LIMIT"
                elif response.status == 402:
                    logger.error(f"Insufficient balance for {model_id}")
                    return None, "INSUFFICIENT_BALANCE"
                elif response.status == 404:
                    logger.error(f"Model not found {model_id}")
                    return None, "MODEL_NOT_FOUND"
                elif response.status != 200:
                    logger.error(f"Free model error {model_id}: {response.status}")
                    return None, "MODEL_FAILED"
                
                data = await response.json()
                
                prompt_tokens = data.get("usage", {}).get("prompt_tokens", 0)
                completion_tokens = data.get("usage", {}).get("completion_tokens", 0)
                total_tokens = data.get("usage", {}).get("total_tokens", prompt_tokens + completion_tokens)
                
                reply_text = data["choices"][0]["message"]["content"]
                
                return {
                    "text": reply_text,
                    "total_tokens": total_tokens,
                    "model_name": model_name,
                    "model_id": model_id
                }, None
                
    except asyncio.TimeoutError:
        logger.error(f"Timeout for {model_id}")
        return None, "TIMEOUT"
    except Exception as e:
        logger.error(f"Error in call_free_model {model_id}: {e}")
        return None, "UNKNOWN_ERROR"

# ========== УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ==========
async def call_free_with_retry(user_id, prompt, max_retries=3):
    """Пытается вызвать бесплатные модели по порядку"""
    
    errors = []
    
    for attempt, model in enumerate(FREE_MODELS[:max_retries]):
        logger.info(f"Trying {model['name']}...")
        
        result, error = await call_free_model(user_id, prompt, model["id"])
        
        if result:
            return result, None
        
        if error == "RATE_LIMIT":
            errors.append(f"⚠️ {model['name']}: слишком много запросов, подожди 1-2 минуты")
        elif error == "INSUFFICIENT_BALANCE":
            errors.append(f"⚠️ {model['name']}: технические проблемы на сервере")
        elif error == "MODEL_NOT_FOUND":
            errors.append(f"⚠️ {model['name']}: временно недоступна")
        elif error == "TIMEOUT":
            errors.append(f"⚠️ {model['name']}: долго не отвечает, попробуй другую")
        else:
            errors.append(f"⚠️ {model['name']}: ошибка соединения")
        
        await asyncio.sleep(1)
    
    error_message = "❌ **Не удалось получить ответ**\n\n"
    error_message += "Проблемы с моделями:\n" + "\n".join(errors)
    error_message += "\n\n💡 **Что делать?**\n"
    error_message += "• Выбрать другую модель: /select\n"
    error_message += "• Использовать Grok Premium: /grok\n"
    error_message += "• Попробовать через пару минут"
    
    return None, error_message