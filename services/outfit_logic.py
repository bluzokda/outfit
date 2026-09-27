import json

import requests

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
    """Запрос через актуальный Gemini Interactions API (generateContent + модели 1.5/2.x
    ограничены Google для новых проектов и возвращают 404)."""
    response = requests.post(
        config.gemini_api_url,
        headers={
            "x-goog-api-key": config.gemini_api_key,
            "Content-Type": "application/json",
        },
        json={
            "model": "gemini-3.8-flash",
            "input": prompt,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": schema,
            },
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    for step in data.get("steps", []):
        if step.get("type") == "model_output":
            for block in step.get("content", []):
                if block.get("type") == "text":
                    return json.loads(block["text"])

    raise ValueError(f"Не удалось извлечь ответ от Gemini: {data}")


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
