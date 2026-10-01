import json
import time

import requests

from config import config
from services.weather import WeatherInfo


SLOT_CATEGORIES = ("outerwear", "top", "bottom", "dress", "shoes", "accessory")

GENERATE_CONTENT_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Модели для текстового стилиста: первая доступная побеждает
TEXT_MODELS = [
    config.gemini_text_model,
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]


class OutfitResult:
    def __init__(self, item_ids, explanation, generic_recommendations=None, slots=None, mode="wardrobe"):
        self.item_ids = item_ids
        self.explanation = explanation
        self.generic_recommendations = generic_recommendations
        self.slots = slots or []
        self.mode = mode  # "wardrobe" — вещи с фото, "generic" — манекен без фото


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
    if not profile:
        return items
    if profile.get("gender") == "male":
        return [i for i in items if i.get("category") != "dress"]
    return items


def _fallback_result(text: str) -> dict:
    """Безопасный фолбэк со всеми ключами сразу — подходит и для режима
    'с гардеробом', и для режима 'с нуля'."""
    return {
        "explanation": text,
        "item_ids": [],
        "slots": [],
        "recommendations": [],
    }


def _call_gemini(prompt: str, schema: dict) -> dict:
    """Запрос к Gemini через стандартный generateContent API
    (работает на обычном Developer API-ключе, Interactions API не нужен).
    С ретраями на 429/503 и перебором моделей."""
    if not config.gemini_api_key:
        print("Gemini API key не задан")
        return _fallback_result("ИИ-стилист не настроен: не задан GEMINI_API_KEY.")

    for model in TEXT_MODELS:
        if not model:
            continue
        url = GENERATE_CONTENT_URL.format(model=model)
        for attempt in range(3):
            try:
                response = requests.post(
                    url,
                    headers={
                        "x-goog-api-key": config.gemini_api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "responseMimeType": "application/json",
                            "responseSchema": schema,
                            "temperature": 0.7,
                        },
                    },
                    timeout=45,
                )

                if response.status_code == 404:
                    print(f"Gemini text: модель {model} недоступна (404), пробую следующую")
                    break  # следующая модель

                if response.status_code in RETRYABLE_STATUS:
                    wait = 3 * (2 ** attempt)
                    print(f"Gemini text ({model}): {response.status_code}, ретрай {attempt + 1}/3 через {wait}с")
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                data = response.json()

                for candidate in data.get("candidates", []):
                    for part in (candidate.get("content") or {}).get("parts", []):
                        text = part.get("text")
                        if text:
                            return json.loads(text)

                print(f"Gemini text ({model}): ответ без текста, пробую следующую модель")
                break  # следующая модель

            except json.JSONDecodeError as e:
                print(f"Gemini text ({model}): не удалось распарсить JSON: {e}")
                break  # следующая модель
            except requests.exceptions.RequestException as e:
                wait = 3 * (2 ** attempt)
                print(f"Gemini text ({model}): сетевая ошибка {e}, ретрай {attempt + 1}/3 через {wait}с")
                time.sleep(wait)

    return _fallback_result(
        "В данный момент ИИ-стилист перегружен. Попробуйте сгенерировать образ ещё раз через несколько секунд."
    )


def _build_wardrobe_slots(filtered_items, picked_ids):
    """Группирует вещи по категориям для интерактивного редактора образа.
    В каждый слот попадает категория только если стилист выбрал из неё вещь,
    а вариантами для замены служат ВСЕ вещи пользователя этой категории
    (уже отфильтрованные по погоде) — не выдуманные, реальные."""
    by_cat: dict[str, list] = {}
    for item in filtered_items:
        by_cat.setdefault(item["category"], []).append(item)

    picked_set = set(picked_ids)
    slots = []
    for cat in SLOT_CATEGORIES:
        cat_items = by_cat.get(cat)
        if not cat_items:
            continue
        picked_in_cat = [i for i in cat_items if i["id"] in picked_set]
        if not picked_in_cat:
            continue
        recommended_id = picked_in_cat[0]["id"]
        options = [
            {
                "id": i["id"],
                "photo_path": i["photo_path"],
                "description": i.get("description") or "",
                "recommended": i["id"] == recommended_id,
            }
            for i in cat_items
        ]
        options.sort(key=lambda o: not o["recommended"])
        slots.append({"category": cat, "options": options})
    return slots


def _sanitize_generic_slots(raw_slots):
    clean = []
    for s in raw_slots or []:
        cat = s.get("category")
        options = [o.strip() for o in (s.get("options") or []) if isinstance(o, str) and o.strip()]
        if cat in SLOT_CATEGORIES and options:
            clean.append({"category": cat, "options": options[:3]})
    return clean


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

        valid_ids = {i["id"] for i in filtered}
        item_ids = [i for i in result.get("item_ids", []) if i in valid_ids]
        slots = _build_wardrobe_slots(filtered, item_ids) if item_ids else []

        return OutfitResult(
            item_ids=item_ids,
            explanation=result.get("explanation", ""),
            slots=slots,
            mode="wardrobe",
        )

    # --- режим "с нуля": гардероба нет, показываем манекен ---
    prompt = base_context + (
        "У пользователя нет сохранённого гардероба. Для каждой уместной категории "
        "(outerwear/top/bottom либо dress/shoes/accessory — используй ЛИБО dress, "
        "ЛИБО пару top+bottom, не оба сразу, и включай только реально нужные "
        "категории под этот повод и погоду) предложи 2-3 конкретных коротких "
        "варианта вещи (например: 'Худи оверсайз', 'Рубашка свободного кроя'). "
        "Первый вариант в списке — твоя основная рекомендация."
    )
    schema = {
        "type": "object",
        "properties": {
            "slots": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": list(SLOT_CATEGORIES),
                        },
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["category", "options"],
                },
            },
            "explanation": {"type": "string"},
        },
        "required": ["slots", "explanation"],
    }
    result = _call_gemini(prompt, schema)
    slots = _sanitize_generic_slots(result.get("slots"))

    return OutfitResult(
        item_ids=[],
        explanation=result.get("explanation", ""),
        slots=slots,
        mode="generic",
    )
