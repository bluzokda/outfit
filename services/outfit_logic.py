import requests
import json

from config import config
from services.weather import WeatherInfo


class OutfitResult:
    def __init__(self, item_ids, explanation, generic_recommendations=None):
        self.item_ids = item_ids
        self.explanation = explanation
        self.generic_recommendations = generic_recommendations


def filter_items_by_weather(items, weather: WeatherInfo):
    filtered = []
    for item in items:
        if item.get("min_temp") is not None and weather.temperature < item["min_temp"]:
            continue
        if item.get("max_temp") is not None and weather.temperature > item["max_temp"]:
            continue
        filtered.append(item)
    return filtered


def _items_to_prompt_list(items):
    lines = [
        f"- id={item['id']}, категория={item['category']}, описание: {item.get('description') or 'без описания'}"
        for item in items
    ]
    return "\n".join(lines) if lines else "(гардероб пуст)"


def _call_gemini(prompt: str, schema: dict) -> dict:
    """Запрос к Gemini через официальный API генерации контента с JSON-ответом."""
    # Используем стабильный стандартный эндпоинт актуальной модели gemini-2.5-flash
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={config.gemini_api_key}"
    
    response = requests.post(
        api_url,
        headers={
            "Content-Type": "application/json",
        },
        json={
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema
            }
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    try:
        # Достаем текст из стандартного ответа Gemini API
        text_content = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text_content)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise ValueError(f"Не удалось извлечь JSON-ответ от Gemini: {data}") from e


def build_outfit(occasion: str, weather: WeatherInfo, wardrobe_items) -> OutfitResult:
    filtered = filter_items_by_weather(wardrobe_items, weather)
    has_wardrobe = len(wardrobe_items) > 0

    base_context = (
        f"Ты — персональный стилист. Погода: {weather.temperature}°C "
        f"(ощущается как {weather.feels_like}°C), {weather.condition_text}, "
        f"ветер {weather.wind_speed} м/с. Повод: {occasion}.\n\n"
    )

    if has_wardrobe:
        prompt = base_context + (
            "Доступные вещи пользователя (уже отфильтрованы по погоде):\n"
            f"{_items_to_prompt_list(filtered)}\n\n"
            "Выбери набор вещей (по одной из подходящих категорий: outerwear/top/"
            "bottom/dress/shoes, плюс опционально accessory), которые вместе "
            "составляют цельный образ под повод и погоду."
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

    prompt = base_context + (
        "У пользователя нет сохранённого гардероба. Дай общие рекомендации по "
        "образу: какие типы вещей надеть (верх, низ, обувь, верхняя одежда, "
        "аксессуары) под эту погоду и повод."
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
