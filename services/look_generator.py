import base64
import gc
import os
import re
import time
import urllib.parse
import uuid

import requests

from config import config

TRANSLATIONS = {
    "легкий пуховик": "light down jacket",
    "худи с начесом": "fleece hoodie",
    "спортивные брюки на флисе": "fleece sweatpants",
    "утепленные кроссовки": "insulated sneakers",
    "спортивная бейсболка": "sports baseball cap",
    "ветровка на флисе": "fleece windbreaker jacket",
    "худи оверсайз": "oversized hoodie",
    "спортивные джоггеры": "sports joggers",
    "удобные кроссовки": "comfortable sneakers",
    "трикотажная шапка": "knit beanie hat",
    "верхняя одежда": "outerwear jacket",
    "обувь": "shoes sneakers",
    "аксессуар": "accessory",
}

# Модели генерации изображений, доступные на обычном Gemini Developer API
# (НЕ Imagen 3/4 и НЕ Interactions API — они требуют платный тариф / Vertex).
# Порядок — по приоритету; недоступная модель (404) пропускается.
IMAGE_MODELS = [
    os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"),
    "gemini-2.5-flash-image-preview",
    "gemini-3.1-flash-image-preview",
]

GENERATE_CONTENT_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def clean_and_translate_prompt(items_description: list[str]) -> str:
    translated_items = []
    for item in (items_description or []):
        text = str(item).lower()
        for ru, en in TRANSLATIONS.items():
            text = text.replace(ru, en)
        text = re.sub(r'[а-яА-ЯёЁ]+', '', text).strip()
        if text:
            translated_items.append(text)

    result = ", ".join(translated_items)
    return result if result else "stylish modern casual streetwear outfit"


def _extract_image_bytes(data: dict) -> bytes | None:
    """Достаёт base64-картинку из ответа generateContent."""
    for candidate in data.get("candidates", []):
        for part in (candidate.get("content") or {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                try:
                    return base64.b64decode(inline["data"])
                except Exception:
                    continue
    return None


def _generate_with_gemini(prompt: str, api_key: str) -> bytes | None:
    """Генерация через Gemini generateContent (работает на Developer API,
    в т.ч. на бесплатном тарифе). С ретраями на 429/503."""
    for model in IMAGE_MODELS:
        if not model:
            continue
        url = GENERATE_CONTENT_URL.format(model=model)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {"aspectRatio": "3:4"},
            },
        }
        for attempt in range(3):
            try:
                resp = requests.post(
                    url,
                    headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                    json=payload,
                    timeout=90,
                )

                if resp.status_code == 404:
                    print(f"Gemini image: модель {model} недоступна (404), пробую следующую")
                    break  # следующая модель

                if resp.status_code == 400 and "imageConfig" in payload["generationConfig"]:
                    # Старая модель может не знать imageConfig — повтор без него
                    print(f"Gemini image ({model}): 400 на imageConfig, повтор без aspectRatio")
                    payload["generationConfig"].pop("imageConfig", None)
                    continue

                if resp.status_code in RETRYABLE_STATUS:
                    wait = 3 * (2 ** attempt)
                    print(f"Gemini image ({model}): {resp.status_code}, ретрай {attempt + 1}/3 через {wait}с")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                image_bytes = _extract_image_bytes(resp.json())
                if image_bytes:
                    print(f"Gemini image: успех на модели {model}")
                    return image_bytes

                print(f"Gemini image ({model}): ответ без картинки, пробую следующую модель")
                break  # следующая модель

            except requests.exceptions.RequestException as e:
                wait = 3 * (2 ** attempt)
                print(f"Gemini image ({model}): сетевая ошибка {e}, ретрай {attempt + 1}/3 через {wait}с")
                time.sleep(wait)

    return None


def _generate_with_pollinations(prompt: str) -> bytes | None:
    """Фолбэк на Pollinations с ретраями (flux -> turbo)."""
    encoded_prompt = urllib.parse.quote(prompt)

    for model in ("flux", "turbo"):
        for attempt in range(2):
            seed = uuid.uuid4().int % 1000000
            url = (
                f"https://image.pollinations.ai/prompt/{encoded_prompt}"
                f"?width=768&height=1024&seed={seed}&model={model}&nologo=true&private=true"
            )
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    f"(KHTML, like Gecko) Chrome/{100 + (seed % 20)}.0.0.0 Safari/537.36"
                ),
                "Accept": "image/jpeg,image/png,*/*",
                "Cache-Control": "no-cache",
            }
            try:
                response = requests.get(url, headers=headers, timeout=60)
                if response.ok and len(response.content) > 10000:
                    print(f"Pollinations ({model}): успех")
                    return response.content
                print(f"Pollinations ({model}): {response.status_code}, попытка {attempt + 1}/2")
            except requests.exceptions.RequestException as e:
                print(f"Pollinations ({model}): {e}, попытка {attempt + 1}/2")
            time.sleep(2 * (attempt + 1))

    return None


def generate_imagen_look(gender: str = None, age: int = None, items_description: list[str] = None, occasion: str = "") -> str | None:
    """Универсальная стабильная генерация фото одежды."""
    clean_clothes = clean_and_translate_prompt(items_description)
    gender_str = "male" if gender == "male" else ("female" if gender == "female" else "person")
    age_str = f"{age}-year-old" if age else "young adult"

    prompt = (
        f"Full body fashion editorial photograph of a {age_str} {gender_str} model wearing {clean_clothes}. "
        f"Full growth portrait, standing posture, minimalist photo studio background, highly detailed fabric texture, realistic lighting, 8k"
    )

    # 1. Gemini generateContent (Nano Banana) — работает на обычном API-ключе
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        image_bytes = _generate_with_gemini(prompt, gemini_key)
        if image_bytes:
            return save_image(image_bytes)

    # 2. Фолбэк: Pollinations
    image_bytes = _generate_with_pollinations(prompt)
    if image_bytes:
        return save_image(image_bytes)

    return None


def save_image(image_bytes: bytes) -> str | None:
    """Сохраняет полученные байты изображения в файл."""
    try:
        os.makedirs(config.collages_dir, exist_ok=True)
        filename = f"look_{uuid.uuid4().hex}.jpg"
        file_path = os.path.join(config.collages_dir, filename)

        with open(file_path, "wb") as f:
            f.write(image_bytes)

        gc.collect()
        return "/" + file_path.replace(os.sep, "/")
    except Exception as e:
        print(f"Ошибка сохранения файла: {e}")
        return None
