import os
import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ContextTypes, 
    filters
)

import config
import database
import or_api
from tos_text import TOS_TEXT
from free_models import FREE_MODELS_LIST, get_model_by_command, get_model_by_id, get_model_name

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
database.init_database()

# Хранилище сообщений с соглашением
tos_messages = {}

# ========== ПРОВЕРКА СОГЛАШЕНИЯ ==========

async def check_tos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, принял ли пользователь соглашение"""
    user_id = update.effective_user.id
    
    if not database.user_exists(user_id):
        database.create_user(
            user_id, 
            update.effective_user.username,
            update.effective_user.first_name
        )
    
    if not database.check_tos_accepted(user_id):
        await show_tos(update, context)
        return False
    return True

async def show_tos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает пользовательское соглашение"""
    keyboard = [
        [InlineKeyboardButton("✅ Принимаю", callback_data="accept_tos")],
        [InlineKeyboardButton("❌ Отказываюсь", callback_data="reject_tos")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await update.message.reply_text(
        TOS_TEXT,
        reply_markup=reply_markup
    )
    
    tos_messages[update.effective_user.id] = message.message_id

async def tos_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок соглашения"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data == "accept_tos":
        database.accept_tos(user_id)
        await query.edit_message_text(
            "✅ Спасибо! Соглашение принято. Теперь вы можете пользоваться ботом.\n\n"
            "Введите /start для начала работы."
        )
    else:
        await query.edit_message_text(
            "❌ Вы отказались от соглашения. Для использования бота необходимо принять условия.\n\n"
            "Если передумаете, отправьте /start еще раз."
        )

# ========== СТАРТ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    if not await check_tos(update, context):
        return
    
    user = update.effective_user
    balance = database.get_user_balance(user.id)
    free_remaining = database.get_free_remaining(user.id)
    current_model_id = database.get_user_free_model(user.id)
    model_name = get_model_name(current_model_id)
    
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        f"🎯 **Твоя бесплатная модель:** {model_name}\n"
        f"📊 Осталось токенов: {free_remaining}/{config.FREE_DAILY_LIMIT_TOKENS}\n\n"
        f"💎 **Premium баланс:** {balance} токенов\n\n"
        f"📱 **Команды:**\n"
        f"• /select - выбрать бесплатную модель\n"
        f"• /mode - переключить режим (Free/Premium)\n"
        f"• /grok <текст> - Grok Premium\n"
        f"• /buy - купить токены\n"
        f"• /balance - баланс"
    )
    
    await update.message.reply_text(welcome_text)

# ========== ВЫБОР РЕЖИМА ==========

async def mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор режима работы"""
    if not await check_tos(update, context):
        return
    
    # Определяем текущий режим
    current_mode = context.user_data.get('mode', 'free')
    mode_text = "💎 Premium" if current_mode == 'premium' else "🆓 Free"
    
    keyboard = [
        [InlineKeyboardButton("🆓 Бесплатный режим", callback_data="mode_free")],
        [InlineKeyboardButton("💎 Grok Premium", callback_data="mode_premium")]
    ]
    
    await update.message.reply_text(
        f"🎯 **Выбери режим работы:**\n\n"
        f"🆓 **Бесплатный:**\n"
        f"• Доступ к разным моделям\n"
        f"• Лимит {config.FREE_DAILY_LIMIT_TOKENS} токенов/день\n"
        f"• Можно выбрать модель: /select\n\n"
        f"💎 **Grok Premium:**\n"
        f"• Grok 2 Mini (мягкие фильтры!)\n"
        f"• Без лимитов\n"
        f"• Платно (токены покупаются)\n\n"
        f"Текущий режим: {mode_text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора режима"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "mode_free":
        context.user_data['mode'] = 'free'
        free_remaining = database.get_free_remaining(user_id)
        model_name = get_model_name(database.get_user_free_model(user_id))
        await query.edit_message_text(
            f"✅ **Режим: Бесплатный** 🆓\n\n"
            f"Твоя модель: {model_name}\n"
            f"Лимит сегодня: {free_remaining}/{config.FREE_DAILY_LIMIT_TOKENS} токенов\n\n"
            f"Просто пиши сообщения - я отвечу выбранной моделью!\n"
            f"Сменить модель: /select"
        )
    
    elif query.data == "mode_premium":
        # Проверяем, есть ли у пользователя токены
        balance = database.get_user_balance(user_id)
        
        if balance > 0:
            context.user_data['mode'] = 'premium'
            await query.edit_message_text(
                f"✅ **Режим: Grok Premium** 💎\n\n"
                f"Твой баланс: {balance} токенов\n\n"
                f"Используй /grok для запросов или просто пиши сообщения!"
            )
        else:
            # Если нет токенов, предлагаем купить
            keyboard = [[InlineKeyboardButton("💰 Купить токены", callback_data="back_to_buy")]]
            await query.edit_message_text(
                "❌ **Для Premium режима нужны токены!**\n\n"
                "У тебя пока 0 токенов.\n\n"
                "Купи пакет и наслаждайся Grok без ограничений!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

# ========== ВЫБОР БЕСПЛАТНОЙ МОДЕЛИ ==========

async def select_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает кнопки для выбора бесплатной модели"""
    if not await check_tos(update, context):
        return
    
    user_id = update.effective_user.id
    current_model_id = database.get_user_free_model(user_id)
    
    keyboard = []
    for model in FREE_MODELS_LIST:
        # Добавляем галочку к выбранной модели
        check = "✅ " if model["id"] == current_model_id else ""
        keyboard.append([
            InlineKeyboardButton(
                f"{check}{model['name']} - {model['description']}",
                callback_data=f"select_{model['command']}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎯 **Выбери бесплатную модель:**\n\n"
        f"После выбора просто пиши сообщения - бот будет использовать выбранную модель!",
        reply_markup=reply_markup
    )

async def select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора модели"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    command = query.data.replace("select_", "")
    
    model = get_model_by_command(command)
    
    # Сохраняем выбор
    database.set_user_free_model(user_id, model["id"])
    
    await query.edit_message_text(
        f"✅ **Модель изменена!**\n\n"
        f"Теперь выбрана: {model['name']}\n\n"
        f"Просто пиши сообщения - я буду использовать эту модель!"
    )

# ========== GROK PREMIUM ==========

async def grok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /grok"""
    if not await check_tos(update, context):
        return
    
    user_id = update.effective_user.id
    
    # Проверяем наличие вопроса
    if not context.args:
        await update.message.reply_text(
            "❓ **Как использовать Grok Premium:**\n\n"
            "Просто напиши: `/grok Привет, как дела?`\n\n"
            "Или просто пиши сообщения в Premium режиме!"
        )
        return
    
    # Проверяем баланс
    balance = database.get_user_balance(user_id)
    if balance <= 0:
        await update.message.reply_text(
            "❌ **У тебя закончились токены для Premium!**\n\n"
            "💰 Купи еще: /buy\n"
            "🆓 Или переключись на бесплатный режим: /mode"
        )
        return
    
    prompt = " ".join(context.args)
    
    # Отправляем статус
    status_msg = await update.message.reply_text("💎 Grok думает...")
    
    # Вызываем API
    result, error = await or_api.call_grok(user_id, prompt)
    
    if error:
        await status_msg.edit_text(f"❌ Ошибка: {error}\nПопробуй еще раз.")
        
    else:
        # Списываем токены с пользователя
        success = database.deduct_tokens(
            user_id,
            result["total_tokens"],
            result["our_cost_usd"],
            result["prompt_tokens"],
            result["completion_tokens"]
        )
        
        if success:
            new_balance = database.get_user_balance(user_id)
            
            response = (
                f"💎 **Grok Premium ответил:**\n\n"
                f"{result['text']}\n\n"
                f"---\n"
                f"📊 Потрачено: {result['total_tokens']} токенов\n"
                f"💰 Остаток: {new_balance} токенов"
            )
            
            await status_msg.edit_text(response)
        else:
            await status_msg.edit_text("❌ Ошибка при списании токенов")

# ========== БЕСПЛАТНЫЙ РЕЖИМ ==========

async def free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Бесплатный запрос с выбранной моделью"""
    if not await check_tos(update, context):
        return
    
    user_id = update.effective_user.id
    
    # Получаем текст сообщения
    if not context.args and not update.message.text.startswith('/'):
        # Если это обычное сообщение (не команда)
        prompt = update.message.text
    elif context.args:
        prompt = " ".join(context.args)
    else:
        return  # Просто игнорируем
    
    # Проверяем лимит
    if not database.can_use_free(user_id):
        remaining = database.get_free_remaining(user_id)
        await update.message.reply_text(
            f"⚠️ **Лимит бесплатного режима исчерпан!**\n\n"
            f"Сегодня ты использовал **{config.FREE_DAILY_LIMIT_TOKENS}** токенов.\n\n"
            f"💎 Купи Grok Premium: /buy"
        )
        return
    
    # Получаем выбранную модель
    selected_model_id = database.get_user_free_model(user_id)
    model = get_model_by_id(selected_model_id)
    
    # Отправляем статус
    status_msg = await update.message.reply_text(f"🤖 {model['name']} думает...")
    
    # Вызываем модель
    result, error = await or_api.call_free_model(user_id, prompt, model["id"])
    
    if error:
        # Если модель не сработала - пробуем Auto Router
        if model["id"] != "openrouter/auto":
            await status_msg.edit_text(f"⚠️ {model['name']} не отвечает, пробую Auto Router...")
            result, error = await or_api.call_free_model(user_id, prompt, "openrouter/auto")
    
    if error:
        await status_msg.edit_text(
            "❌ **Не удалось получить ответ**\n\n"
            "Попробуй другую модель: /select"
        )
        return
    
    if result:
        # Записываем использование
        database.add_free_usage(user_id, result["total_tokens"], result["model_name"])
        
        # Сколько осталось
        remaining = database.get_free_remaining(user_id)
        
        response = (
            f"✅ **{result['model_name']}**\n"
            f"📊 Токенов: {result['total_tokens']}\n"
            f"⏳ Осталось: {remaining}/{config.FREE_DAILY_LIMIT_TOKENS}\n\n"
            f"{result['text']}"
        )
        
        await status_msg.edit_text(response)

# ========== БАЛАНС ==========

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка баланса"""
    if not await check_tos(update, context):
        return
    
    user_id = update.effective_user.id
    premium_balance = database.get_user_balance(user_id)
    free_remaining = database.get_free_remaining(user_id)
    free_used = config.FREE_DAILY_LIMIT_TOKENS - free_remaining
    current_model = get_model_name(database.get_user_free_model(user_id))
    
    await update.message.reply_text(
        f"💰 **Твой баланс:**\n\n"
        f"🆓 **Бесплатный режим:**\n"
        f"• Модель: {current_model}\n"
        f"• Использовано сегодня: {free_used} токенов\n"
        f"• Осталось: {free_remaining} токенов\n\n"
        f"💎 **Premium:**\n"
        f"• {premium_balance} токенов\n"
        f"• ≈ {premium_balance * config.PRICE_PER_1K_TOKENS_RUB / 1000:.2f}₽\n\n"
        f"Купить Premium: /buy\n"
        f"Сменить модель: /select"
    )

# ========== ПОКУПКА ТОКЕНОВ ==========

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Покупка токенов через Stars"""
    if not await check_tos(update, context):
        return
    
    keyboard = []
    
    for pkg in config.PACKAGES:
        button_text = f"📦 {pkg['name']}: {pkg['tokens']} токенов — {pkg['price_rub']}₽ / {pkg['stars']}⭐️"
        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"buy_{pkg['tokens']}_{pkg['stars']}_{pkg['price_rub']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("❓ Как купить Stars?", callback_data="stars_help")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛒 **Купить токены для Grok Premium :**\n\n"
        "💎 Оплатите Telegram Stars⭐️ или напишите @kaneki_igor \n\n"
        "После покупки токены появятся на балансе сразу.",
        reply_markup=reply_markup
    )

async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора пакета"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "stars_help":
        help_text = (
            "❓ **Как купить Telegram Stars?**\n\n"
            "1️⃣ Открой Telegram на **iOS/Android**\n"
            "2️⃣ **Настройки** → **Telegram Stars**\n"
            "3️⃣ Купи нужное количество Stars (картой РФ)\n"
            "4️⃣ Вернись сюда и оплати пакет!\n\n"
            "⭐️ **Курс:** 1 Star ≈ 1.5₽"
        )
        await query.edit_message_text(help_text)
        
        keyboard = [[InlineKeyboardButton("◀️ Назад к покупке", callback_data="back_to_buy")]]
        await query.message.reply_text(
            "Нажми, чтобы вернуться:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    elif query.data == "back_to_buy":
        # Показываем кнопки с пакетами
        keyboard = []
        for pkg in config.PACKAGES:
            button_text = f"📦 {pkg['name']}: {pkg['tokens']} токенов — {pkg['price_rub']}₽ / {pkg['stars']}⭐️"
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"buy_{pkg['tokens']}_{pkg['stars']}_{pkg['price_rub']}"
                )
            ])
        await query.edit_message_text(
            "🛒 **Выбери пакет токенов:**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if query.data.startswith("buy_"):
        parts = query.data.split("_")
        tokens = int(parts[1])
        stars = int(parts[2])
        price_rub = int(parts[3])
        
        context.user_data['selected_package'] = {
            'tokens': tokens,
            'stars': stars,
            'price_rub': price_rub
        }
        
        title = f"📦 {tokens} токенов Grok"
        description = f"{tokens} токенов для Grok Premium"
        payload = f"buy_tokens_{tokens}_{stars}_{price_rub}"
        
        try:
            await context.bot.send_invoice(
                chat_id=user_id,
                title=title,
                description=description,
                payload=payload,
                provider_token=config.PROVIDER_TOKEN,
                currency="XTR",
                prices=[LabeledPrice(label="Оплата Stars", amount=stars)],
                start_parameter="grok_premium",
                need_email=False,
                need_phone_number=False,
                need_shipping_address=False,
                is_flexible=False
            )
            logger.info(f"Invoice sent to user {user_id} for {stars} Stars")
        except Exception as e:
            logger.error(f"Failed to send invoice: {e}")
            await query.edit_message_text(
                "❌ Ошибка при создании счета. Попробуй позже."
            )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка перед оплатой"""
    query = update.pre_checkout_query
    await query.answer(ok=True)
    logger.info(f"Pre-checkout approved for user {query.from_user.id}")

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка успешной оплаты"""
    user_id = update.effective_user.id
    payment = update.message.successful_payment
    
    logger.info(f"Successful payment from user {user_id}: {payment.total_amount} Stars")
    
    payload = payment.invoice_payload
    
    if payload.startswith("buy_tokens"):
        parts = payload.split("_")
        tokens = int(parts[2])
        stars = int(parts[3])
        price_rub = int(parts[4])
        
        database.add_tokens(
            user_id, 
            tokens, 
            amount_rub=price_rub,
            description=f"Оплата {stars}⭐️"
        )
        
        new_balance = database.get_user_balance(user_id)
        
        await update.message.reply_text(
            f"✅ **Оплата прошла успешно!**\n\n"
            f"💫 Тебе начислено: **{tokens} токенов**\n"
            f"💰 Текущий баланс: **{new_balance} токенов**\n\n"
            f"🔥 Теперь ты можешь задавать вопросы Grok!"
        )

# ========== ПОМОЩЬ ==========

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка"""
    if not await check_tos(update, context):
        return
    
    help_text = (
        "🔍 **Как пользоваться ботом:**\n\n"
        "1️⃣ **Выбрать бесплатную модель** — /select\n"
        "   GLM, Qwen или Auto Router\n\n"
        "2️⃣ **Выбрать режим** — /mode\n"
        "   🆓 Бесплатный или 💎 Grok Premium\n\n"
        "3️⃣ **Просто пиши сообщения** — бот ответит выбранной моделью!\n\n"
        "4️⃣ **Купить токены** — /buy\n"
        "   Оплата Telegram Stars ⭐️\n\n"
        "5️⃣ **Проверить баланс** — /balance\n\n"
        "💰 **Цены Premium:**\n"
        f"• {config.PRICE_PER_1K_TOKENS_RUB}₽ за 1000 токенов\n\n"
        "📞 **Поддержка:** @{}".format(config.ADMIN_USERNAME)
    )
    
    await update.message.reply_text(help_text)

# ========== АДМИН ПАНЕЛЬ ==========

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель"""
    user_id = update.effective_user.id
    
    if user_id != config.ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    
    # Проверяем баланс OpenRouter
    try:
        or_balance = await or_api.check_or_balance()
    except:
        or_balance = 0.0
    
    # Получаем статистику из БД
    stats = database.get_admin_stats()
    
    # Проверяем, нужно ли уведомление о низком балансе
    alert = ""
    if or_balance and or_balance < config.MIN_OR_BALANCE_ALERT:
        alert = (
            f"⚠️ **ВНИМАНИЕ!** Баланс OpenRouter ниже ${config.MIN_OR_BALANCE_ALERT}\n"
            f"💰 Текущий баланс: **${or_balance:.2f}**\n"
            f"🔗 Ссылка для пополнения: https://openrouter.ai/settings/balance\n\n"
        )
    
    # Расчет маржи
    profit_rub = stats['total_revenue_rub'] - (stats['total_or_cost_usd'] * 90)
    margin = (profit_rub / stats['total_revenue_rub'] * 100) if stats['total_revenue_rub'] > 0 else 0
    
    admin_text = (
        f"📊 **АДМИН-ПАНЕЛЬ**\n\n"
        f"{alert}"
        f"👥 **Пользователи:**\n"
        f"• Всего: {stats['total_users']}\n"
        f"• Приняли ToS: {stats['tos_accepted']}\n"
        f"• Активных сегодня: {stats['active_today']}\n\n"
        f"💰 **Финансы:**\n"
        f"• Выручка: {stats['total_revenue_rub']:.2f}₽\n"
        f"• Затраты OR: ${stats['total_or_cost_usd']:.4f}\n"
        f"• Прибыль: {profit_rub:.2f}₽\n"
        f"• Маржа: {margin:.1f}%\n\n"
        f"🪙 **Токены Premium:**\n"
        f"• Продано: {stats['total_user_balance'] + stats['total_tokens_used']}\n"
        f"• Использовано: {stats['total_tokens_used']}\n"
        f"• В балансах: {stats['total_user_balance']}\n\n"
        f"🆓 **Бесплатный режим сегодня:**\n"
        f"• Пользователей: {stats['free_users_today']}\n"
        f"• Токенов: {stats['free_tokens_today']}\n\n"
        f"💰 **OpenRouter:**\n"
        f"• Баланс: ${or_balance:.2f}\n"
        f"• Порог: ${config.MIN_OR_BALANCE_ALERT}\n\n"
        f"🔄 **Последние 5 покупок:**\n"
    )
    
    for i, purchase in enumerate(stats['recent_purchases'][:5]):
        admin_text += f"{i+1}. User {purchase[0]}: {purchase[2]} токенов за {purchase[1]}₽\n"
    
    await update.message.reply_text(admin_text)

# ========== УВЕДОМЛЕНИЯ ==========

async def notify_admin_balance_critical(context):
    """Отправляет уведомление админу о критическом балансе"""
    try:
        await context.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=(
                "🚨 **КРИТИЧЕСКОЕ УВЕДОМЛЕНИЕ!**\n\n"
                "Баланс OpenRouter закончился!\n"
                "Пользователи не могут отправлять запросы.\n\n"
                "🔗 **Ссылка для пополнения:**\n"
                "https://openrouter.ai/settings/balance"
            )
        )
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")

async def periodic_or_check(context):
    """Периодическая проверка баланса OpenRouter (раз в час)"""
    try:
        or_balance = await or_api.check_or_balance()
        
        if or_balance and or_balance < config.MIN_OR_BALANCE_ALERT:
            await context.bot.send_message(
                chat_id=config.ADMIN_ID,
                text=(
                    f"⚠️ **Внимание!**\n\n"
                    f"Баланс OpenRouter упал ниже ${config.MIN_OR_BALANCE_ALERT}\n"
                    f"💰 Текущий баланс: **${or_balance:.2f}**\n\n"
                    f"🔗 **Ссылка для пополнения:**\n"
                    f"https://openrouter.ai/settings/balance"
                )
            )
        
        logger.info(f"Periodic OR balance check: ${or_balance:.2f}")
    except:
        pass

# ========== ОБРАБОТКА СООБЩЕНИЙ ==========

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка обычных сообщений"""
    if not await check_tos(update, context):
        return
    
    # Определяем текущий режим
    current_mode = context.user_data.get('mode', 'free')
    
    if current_mode == 'premium':
        # Для Premium режима
        prompt = update.message.text
        context.args = [prompt]
        await grok(update, context)
    else:
        # Для бесплатного режима
        await free(update, context)

# ========== ЗАПУСК ==========

def main():
    """Запуск бота"""
    
    # Создаем приложение
    app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
    
    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("grok", grok))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("mode", mode))
    app.add_handler(CommandHandler("select", select_model))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin))
    
    # Обработчики callback-кнопок
    app.add_handler(CallbackQueryHandler(tos_callback, pattern="^(accept|reject)_tos$"))
    app.add_handler(CallbackQueryHandler(mode_callback, pattern="^mode_"))
    app.add_handler(CallbackQueryHandler(select_callback, pattern="^select_"))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern="^buy_|^stars_help$|^back_to_buy$"))
    
    # Обработчики платежей
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    # Обработчик обычных сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Периодическая задача (проверка баланса каждый час)
    try:
        job_queue = app.job_queue
        if job_queue:
            job_queue.run_repeating(periodic_or_check, interval=3600, first=10)
    except:
        pass
    
    logger.info("🚀 Bot started with Free + Grok Premium modes")
    print("🤖 Бот запущен! Нажми Ctrl+C для остановки")
    
    # Запускаем
    app.run_polling()

if __name__ == "__main__":
    main()