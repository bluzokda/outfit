import json
import requests
from config import config

class WeatherInfo:
    def __init__(self, temperature, feels_like, condition_text, wind_speed, precipitation):
        self.temperature = temperature
        self.feels_like = feels_like
        self.condition_text = condition_text
        self.wind_speed = wind_speed
        self.precipitation = precipitation

class OutfitResult:
    def __init__(self, item_ids, explanation, generic_recommendations=None):
        self.item_ids = item_ids
        self.explanation = explanation
        self.generic_recommendations = generic_recommendations or []

def filter_items_by_weather(items, weather: WeatherInfo):
    filtered = []
    for item in items:
        # Проверка температурного режима вещи (если поля min_temp / max_temp заданы)
        if hasattr(item, 'min_temp') and item.min_temp is not None and weather.temperature < item.min_temp:
            continue
        if hasattr(item, 'max_temp') and item.max_temp is not None and weather.temperature > item.max_temp:
            continue
        filtered.append(item)
    return filtered

def _items_to_prompt_list(items):
    lines = [
        f"- id={item.id}, категория={item.category}, описание: {getattr(item, 'description', 'без описания')}"
        for item in items
    ]
    return "\n".join(lines) if lines else "(гардероб пуст)"

def _call_gemini(prompt: str, schema: dict) -> dict:
    headers = {
        "x-goog-api-key": config.gemini_api_key,
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "gemini-2.5-flash",
        "input": prompt,
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": schema,
        },
    }
    
    response = requests.post(config.gemini_api_url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()

    # Разбор ответа под эндпоинт v1beta/interactions
    for step in data.get("steps", []):
        if step.get("type") == "model_output":
            for block in step.get("content", []):
                if block.get("type") == "text":
                    clean_text = block["text"].replace("```json", "").replace("```", "").strip()
                    return json.loads(clean_text)

    raise ValueError(f"Не удалось извлечь ответ от Gemini: {data}")

def build_outfit(occasion: str, weather: WeatherInfo, user_obj, wardrobe_items) -> OutfitResult:
    filtered_items = filter_items_by_weather(wardrobe_items, weather)
    has_wardrobe = len(wardrobe_items) > 0

    # Безопасное извлечение полей пользователя (если они есть в модели)
    gender = getattr(user_obj, 'gender', 'не указан')
    age = getattr(user_obj, 'age', 'не указан')
    style_pref = getattr(user_obj, 'style_preferences', 'нет')

    user_context = (
        f"👤 ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:\n"
        f"- Пол: {gender}\n"
        f"- Возраст: {age}\n"
        f"- Предпочтения в стиле: {style_pref}\n\n"
    )

    base_context = (
        f"Ты — профессиональный персональный стилист.\n"
        f"{user_context}"
        f"📍 МЕСТО И ПОВОД: {occasion} (образ должен строго соответствовать этому контексту, полу и возрасту! "
        f"Категорически запрещено предлагать вещи, не подходящие по полу, например, женские юбки или платья для мужчин).\n"
        f"🌡️ ПОГОДА: температура {weather.temperature}°C (ощущается как {weather.feels_like}°C), "
        f"описание: {weather.condition_text}, ветер {weather.wind_speed} м/с, осадки: {weather.precipitation} мм.\n\n"
    )

    if has_wardrobe:
        prompt = base_context + (
            "Доступные вещи пользователя в гардеробе (уже отфильтрованы по погоде):\n"
            f"{_items_to_prompt_list(filtered_items)}\n\n"
            "Выбери оптимальный набор вещей (по одной из подходящих категорий: outerwear/top/bottom/shoes), "
            "которые составляют стильный образ под указанный пол, возраст, повод и погоду."
        )
        schema = {
            "type": "object",
            "properties": {
                "item_ids": {"type": "array", "items": {"type": "integer"}},
                "explanation": {"type": "string"},
            },
            "required": ["item_ids", "explanation"],
        }
        result = _call_gemini(prompt, schema)
        return OutfitResult(item_ids=result.get("item_ids", []), explanation=result.get("explanation", ""))
    else:
        prompt = base_context + (
            "У пользователя пока нет сохранённого гардероба. Дай подробные рекомендации по стилю: "
            "что надеть (верх, низ, обувь, верхняя одежда) с учетом пола, возраста, погоды и повода."
        )
        schema = {
            "type": "object",
            "properties": {
                "recommendations": {"type": "array", "items": {"type": "string"}},
                "explanation": {"type": "string"},
            },
            "required": ["recommendations", "explanation"],
        }
        result = _call_gemini(prompt, schema)
        return OutfitResult(
            item_ids=[],
            explanation=result.get("explanation", ""),
            generic_recommendations=result.get("recommendations", []),
        )
