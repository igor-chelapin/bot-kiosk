# free_models.py

# Список доступных бесплатных моделей
FREE_MODELS_LIST = [
    {
        "id": "z-ai/glm-4.5-air:free",
        "name": "🧪 GLM-4.5 Air",
        "description": "Модель от Z-AI",
        "command": "glm"
    },
    {
        "id": "arcee-ai/trinity-large-preview:free",
        "name": "🔮 Trinity",
        "description": "самая быстрая  ",
        "command": "qwen"
    },
    {
        "id": "openrouter/auto",
        "name": "🤖 Auto Router",
        "description": "Автоматический выбор лучшей модели",
        "command": "auto"
    }
]

def get_model_by_command(command):
    """Возвращает модель по команде"""
    for model in FREE_MODELS_LIST:
        if model["command"] == command:
            return model
    return FREE_MODELS_LIST[2]  # auto по умолчанию

def get_model_by_id(model_id):
    """Возвращает модель по ID"""
    for model in FREE_MODELS_LIST:
        if model["id"] == model_id:
            return model
    return FREE_MODELS_LIST[2]

def get_model_name(model_id):
    """Возвращает название модели по ID"""
    for model in FREE_MODELS_LIST:
        if model["id"] == model_id:
            return model["name"]
    return "Auto Router"