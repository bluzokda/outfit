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


GENDER_TEXT = {"male": "мужской", "female": "женский"}

STYLE_TEXT = {
    "casual": "повседневный",
    "classic": "классика",
    "sport": "спортивный",
    "streetwear": "стритвир",
    "minimal": "минимализм",
    "business": "деловой",
    "vintage": "винтаж",
    "cozy": "уютный/оверсайз",
}


def _profile_block(profile) -> str:
    """Текстовый блок с данными пользователя для промпта."""
    if not profile:
        return ""

    lines = []
    gender = GENDER_TEXT.get(profile.get("gender"))
    if gender:
        lines.append(f"- Пол: {gender}")
    if profile.get("age"):
        lines.append(f"- Возраст: {profile['age']}")
    styles = [STYLE_TEXT.get(k, k) for k in (profile.get("styles") or "").split(",") if k]
    if styles:
        lines.append(f"- Любимые стили: {', '.join(styles)}")
    if profile.get("notes"):
        lines.append(f"- Личные пожелания и ограничения: {profile['notes']}")

    if not lines:
        return ""

    block = "Профиль пользователя:\n" + "\n".join(lines) + "\n\n"
    block += (
        "СТРОГО учитывай профиль. Предлагай только те вещи, которые подходят "
        "пользователю по полу и возрасту"
    )
    if gender:
        block += (
            f" (пол — {gender}: не предлагай одежду, которую обычно носит "
            "противоположный пол, например юбки и платья мужчине)"
        )
    block += ". Следуй любимым стилям и обязательно соблюдай личные ограничения.\n\n"
    return block


def _apply_profile_filter(items, profile):
    """Жёсткая проверка в коде — на случай, если модель ошибётся."""
    if not profile:
        return items
    if profile.get("gender") == "male":
        return [i for i in items if i.get("category") != "dress"]
    return items


def _call_gemini(prompt: str, schema: dict) -> dict:
    """Запрос через актуальный Gemini Interactions API с защитой от ошибок (например, 503)."""
    try:
        response = requests.post(
            config.gemini_api_url,
            headers={
                "x-goog-api-key": config.gemini_api_key,
                "Content-Type": "application/json",
            },
            json={
                "model": "gemini-3.5-flash-lite",
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

    except requests.exceptions.HTTPError as e:
        print(f"Ошибка Gemini API (возможно, 503 Service Unavailable): {e}")
        # Безопасный возврат ответа, чтобы сайт не падал с ошибкой 500
        return {
            "explanation": "В данный момент ИИ-стилист перегружен (ошибка сервера Google 503). Пожалуйста, попробуйте сгенерировать образ ещё раз через несколько секунд.",
            "item_ids": [],
            "recommendations": ["Рекомендуем надеть удобную одежду, соответствующую погоде."]
        }
    except Exception as e:
        print(f"Непредвиденная ошибка при запросе к ИИ: {e}")
        return {
            "explanation": "Произошла временная ошибка при обращении к нейросети. Попробуйте повторить запрос.",
            "item_ids": [],
            "recommendations": []
        }


def build_outfit(occasion: str, weather: WeatherInfo, wardrobe_items, profile=None) -> OutfitResult:
    filtered = filter_items_by_weather(wardrobe_items, weather)
    filtered = _apply_profile_filter(filtered, profile)
    profile_text = _profile_block(profile)
    has_wardrobe = len(wardrobe_items) > 0

    base_context = (
        f"Ты — персональный стилист. Погода: {weather.temperature}°C "
        f"(ощущается как {weather.feels_like}°C), {weather.condition_text}, "
        f"ветер {weather.wind_speed} м/с. Повод: {occasion}.\n\n"
    ) + profile_text

    if has_wardrobe:
        prompt = base_context + (
            "Доступные вещи пользователя (уже отфильтрованы по погоде):\n"
            f"{_items_to_prompt_list(filtered)}\n\n"
            "Выбери набор вещей (по одной из подходящих категорий: outerwear/top/"
            "bottom/dress/shoes, плюс опционально accessory), которые вместе "
            "составляют цельный образ под повод и погоду. Если вещь по описанию "
            "или категории не подходит пользователю по полу или ограничениям — "
            "не выбирай её."
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
        
        # Если сработал перехват ошибки, возвращаем структуру с текстом-предупреждением
        if "recommendations" in result and not result.get("item_ids"):
            return OutfitResult(
                item_ids=[], 
                explanation=result.get("explanation", ""),
                generic_recommendations=result.get("recommendations", [])
            )

        # оставляем только id, реально присутствующие среди допустимых вещей
        valid_ids = {i["id"] for i in filtered}
        item_ids = [i for i in result.get("item_ids", []) if i in valid_ids]
        return OutfitResult(item_ids=item_ids, explanation=result.get("explanation", ""))

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
