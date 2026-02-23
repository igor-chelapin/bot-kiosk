import sqlite3
import logging
from datetime import datetime
from config import DATABASE_PATH, FREE_DAILY_LIMIT_TOKENS

logger = logging.getLogger(__name__)

def init_database():
    """Создает все таблицы в базе данных"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Таблица пользователей с колонкой для выбранной модели
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            agreed_to_tos BOOLEAN DEFAULT 0,
            agreed_at TIMESTAMP,
            balance_tokens INTEGER DEFAULT 0,
            total_spent_rub REAL DEFAULT 0,
            total_tokens_used INTEGER DEFAULT 0,
            selected_free_model TEXT DEFAULT 'openrouter/auto',
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP
        )
    ''')
    
    # Таблица транзакций (покупки)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount_rub REAL,
            tokens INTEGER,
            transaction_type TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица запросов к API (премиум)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            our_cost_usd REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица бесплатного использования
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS free_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            tokens_used INTEGER DEFAULT 0,
            requests_count INTEGER DEFAULT 0,
            model_used TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица логов баланса OpenRouter
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS or_balance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            balance_usd REAL,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

# ========== ПОЛЬЗОВАТЕЛИ ==========

def user_exists(user_id):
    """Проверяет, есть ли пользователь в базе"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def create_user(user_id, username=None, first_name=None):
    """Создает нового пользователя с моделью по умолчанию"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, username, first_name, agreed_to_tos, selected_free_model)
        VALUES (?, ?, ?, 0, 'openrouter/auto')
    ''', (user_id, username, first_name))
    conn.commit()
    conn.close()

def accept_tos(user_id):
    """Отмечает, что пользователь принял соглашение"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET agreed_to_tos = 1, agreed_at = ? 
        WHERE user_id = ?
    ''', (datetime.now(), user_id))
    conn.commit()
    conn.close()

def check_tos_accepted(user_id):
    """Проверяет, принял ли пользователь соглашение"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT agreed_to_tos FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

# ========== ПРЕМИУМ БАЛАНС ==========

def get_user_balance(user_id):
    """Получает баланс пользователя в токенах"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT balance_tokens FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def add_tokens(user_id, tokens, amount_rub, description=""):
    """Добавляет токены пользователю (после покупки)"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users 
        SET balance_tokens = balance_tokens + ?,
            total_spent_rub = total_spent_rub + ?
        WHERE user_id = ?
    ''', (tokens, amount_rub, user_id))
    
    cursor.execute('''
        INSERT INTO transactions (user_id, amount_rub, tokens, transaction_type, description)
        VALUES (?, ?, ?, 'purchase', ?)
    ''', (user_id, amount_rub, tokens, description))
    
    conn.commit()
    conn.close()

def deduct_tokens(user_id, tokens, our_cost_usd, prompt_tokens, completion_tokens):
    """Списывает токены за использование премиум"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance_tokens FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    
    if balance < tokens:
        conn.close()
        return False
    
    cursor.execute('''
        UPDATE users 
        SET balance_tokens = balance_tokens - ?,
            total_tokens_used = total_tokens_used + ?,
            last_activity = ?
        WHERE user_id = ?
    ''', (tokens, tokens, datetime.now(), user_id))
    
    cursor.execute('''
        INSERT INTO api_calls (user_id, model, prompt_tokens, completion_tokens, total_tokens, our_cost_usd)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, "grok-2-mini", prompt_tokens, completion_tokens, tokens, our_cost_usd))
    
    conn.commit()
    conn.close()
    return True

# ========== ВЫБОР МОДЕЛИ ==========

def set_user_free_model(user_id, model_id):
    """Сохраняет выбранную пользователем бесплатную модель"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users SET selected_free_model = ? WHERE user_id = ?
    ''', (model_id, user_id))
    
    conn.commit()
    conn.close()

def get_user_free_model(user_id):
    """Получает выбранную пользователем бесплатную модель"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT selected_free_model FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result and result[0] else "openrouter/auto"

# ========== БЕСПЛАТНЫЙ РЕЖИМ ==========

def get_free_usage_today(user_id):
    """Сколько токенов использовано сегодня в бесплатном режиме"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT SUM(tokens_used) FROM free_usage 
        WHERE user_id = ? AND date = ?
    ''', (user_id, today))
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result and result[0] else 0

def add_free_usage(user_id, tokens, model_used):
    """Добавляет использованные токены в статистику бесплатного режима"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Проверяем, есть ли запись за сегодня
    cursor.execute('''
        SELECT id, tokens_used FROM free_usage 
        WHERE user_id = ? AND date = ?
    ''', (user_id, today))
    
    result = cursor.fetchone()
    
    if result:
        # Обновляем существующую запись
        cursor.execute('''
            UPDATE free_usage 
            SET tokens_used = tokens_used + ?,
                requests_count = requests_count + 1,
                model_used = ?
            WHERE user_id = ? AND date = ?
        ''', (tokens, model_used, user_id, today))
    else:
        # Создаем новую запись
        cursor.execute('''
            INSERT INTO free_usage (user_id, date, tokens_used, requests_count, model_used)
            VALUES (?, ?, ?, 1, ?)
        ''', (user_id, today, tokens, model_used))
    
    conn.commit()
    conn.close()

def can_use_free(user_id):
    """Проверяет, может ли пользователь использовать бесплатный режим"""
    used_today = get_free_usage_today(user_id)
    return used_today < FREE_DAILY_LIMIT_TOKENS

def get_free_remaining(user_id):
    """Сколько токенов осталось на сегодня"""
    used = get_free_usage_today(user_id)
    remaining = FREE_DAILY_LIMIT_TOKENS - used
    return max(0, remaining)

# ========== OPENROUTER ЛОГИ ==========

def log_or_balance(balance_usd):
    """Логирует баланс OpenRouter"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO or_balance_log (balance_usd)
        VALUES (?)
    ''', (balance_usd,))
    conn.commit()
    conn.close()

# ========== АДМИН СТАТИСТИКА ==========

def get_admin_stats():
    """Получает статистику для админа"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    stats = {}
    
    # Количество пользователей
    cursor.execute("SELECT COUNT(*) FROM users")
    stats['total_users'] = cursor.fetchone()[0]
    
    # Пользователи с согласием
    cursor.execute("SELECT COUNT(*) FROM users WHERE agreed_to_tos = 1")
    stats['tos_accepted'] = cursor.fetchone()[0]
    
    # Общий баланс токенов у пользователей
    cursor.execute("SELECT SUM(balance_tokens) FROM users")
    stats['total_user_balance'] = cursor.fetchone()[0] or 0
    
    # Всего потрачено (выручка)
    cursor.execute("SELECT SUM(amount_rub) FROM transactions WHERE transaction_type = 'purchase'")
    stats['total_revenue_rub'] = cursor.fetchone()[0] or 0
    
    # Всего использовано токенов премиум
    cursor.execute("SELECT SUM(total_tokens) FROM api_calls")
    stats['total_tokens_used'] = cursor.fetchone()[0] or 0
    
    # Затраты на OpenRouter
    cursor.execute("SELECT SUM(our_cost_usd) FROM api_calls")
    stats['total_or_cost_usd'] = cursor.fetchone()[0] or 0
    
    # Активные сегодня
    cursor.execute('''
        SELECT COUNT(*) FROM users 
        WHERE last_activity > date('now', '-1 day')
    ''')
    stats['active_today'] = cursor.fetchone()[0] or 0
    
    # Использование бесплатного режима сегодня
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT COUNT(DISTINCT user_id), SUM(tokens_used) 
        FROM free_usage 
        WHERE date = ?
    ''', (today,))
    free_stats = cursor.fetchone()
    stats['free_users_today'] = free_stats[0] or 0
    stats['free_tokens_today'] = free_stats[1] or 0
    
    # Последние 10 покупок
    cursor.execute('''
        SELECT user_id, amount_rub, tokens, created_at 
        FROM transactions 
        WHERE transaction_type = 'purchase'
        ORDER BY created_at DESC LIMIT 10
    ''')
    stats['recent_purchases'] = cursor.fetchall()
    
    conn.close()
    return stats