import os
import uuid
import gc
import re
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

def generate_imagen_look(gender: str = None, age: int = None, items_description: list[str] = None, occasion: str = "") -> str | None:
    """Генерирует фото образа через актуальный Hugging Face Router API."""
    hf_token = os.getenv("HF_TOKEN") or getattr(config, "hf_token", None)
    
    if not hf_token:
        print("HF_TOKEN не найден в переменных окружения.")
        return None

    try:
        clean_clothes = clean_and_translate_prompt(items_description)
        gender_str = "male" if gender == "male" else ("female" if gender == "female" else "person")
        age_str = f"{age}-year-old" if age else "young adult"

        prompt = (
            f"Full body fashion editorial photograph of a {age_str} {gender_str} model wearing {clean_clothes}. "
            f"Minimalist photo studio background, highly detailed fabric texture, realistic lighting, 4k"
        )

        headers = {
            "Authorization": f"Bearer {hf_token}",
            "Content-Type": "application/json"
        }
        payload = {"inputs": prompt}

        # Рабочий URL роутера Hugging Face
        api_url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-dev"

        response = requests.post(api_url, headers=headers, json=payload, timeout=60)

        # Если первая модель недоступна, пробуем быстрый фоллбэк на FLUX.1-schnell
        if response.status_code in (503, 404, 500):
            fallback_url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
            response = requests.post(fallback_url, headers=headers, json=payload, timeout=60)

        if not response.ok:
            print(f"Ошибка Hugging Face API ({response.status_code}): {response.text}")
            response.raise_for_status()

        os.makedirs(config.collages_dir, exist_ok=True)
        filename = f"look_{uuid.uuid4().hex}.jpg"
        file_path = os.path.join(config.collages_dir, filename)

        with open(file_path, "wb") as f:
            f.write(response.content)

        gc.collect()
        return "/" + file_path.replace(os.sep, "/")

    except Exception as e:
        print(f"Ошибка при генерации изображения через Hugging Face: {e}")
        gc.collect()
        return None
