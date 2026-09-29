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
    """Генерирует фото образа через прямой POST-запрос (без 402/410 ошибок)."""
    try:
        clean_clothes = clean_and_translate_prompt(items_description)
        gender_str = "male" if gender == "male" else ("female" if gender == "female" else "person")
        age_str = f"{age}-year-old" if age else "young adult"

        prompt = (
            f"Full body fashion editorial photograph of a {age_str} {gender_str} model wearing {clean_clothes}. "
            f"Minimalist photo studio background, highly detailed fabric texture, realistic lighting, 4k"
        )

        # Прямой рабочее API Pollinations через POST с обходом WAF/Cloudflare
        url = "https://image.pollinations.ai/prompt"
        payload = {
            "prompt": prompt,
            "width": 768,
            "height": 1024,
            "model": "flux",
            "seed": uuid.uuid4().int % 100000,
            "nologo": True
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        if not response.ok:
            # Резервный эндпоинт если основной выдал ошибку
            url_fallback = f"https://gen.pollinations.ai/image/{requests.utils.quote(prompt)}"
            response = requests.get(url_fallback, headers=headers, timeout=60)

        response.raise_for_status()

        os.makedirs(config.collages_dir, exist_ok=True)
        filename = f"look_{uuid.uuid4().hex}.jpg"
        file_path = os.path.join(config.collages_dir, filename)

        with open(file_path, "wb") as f:
            f.write(response.content)

        gc.collect()
        return "/" + file_path.replace(os.sep, "/")

    except Exception as e:
        print(f"Ошибка при генерации изображения: {e}")
        gc.collect()
        return None
