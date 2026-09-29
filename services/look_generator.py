import os
import uuid
import gc
import re
import urllib.parse
import requests
from config import config

# Расширенный словарь перевода
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
    """Переводит описания на английский и строго вычищает всю оставшуюся кириллицу."""
    translated_items = []
    
    for item in (items_description or []):
        text = str(item).lower()
        # Заменяем известные русские фразы
        for ru, en in TRANSLATIONS.items():
            text = text.replace(ru, en)
        # Если остались непереведенные кириллические слова — вычищаем их, чтобы не ломать API
        text = re.sub(r'[а-яА-ЯёЁ]+', '', text).strip()
        if text:
            translated_items.append(text)

    result = ", ".join(translated_items)
    return result if result else "stylish modern casual streetwear outfit"

def generate_imagen_look(gender: str = None, age: int = None, items_description: list[str] = None, occasion: str = "") -> str | None:
    """Генерирует фото образа с гарантированной очисткой промпта."""
    try:
        clean_clothes = clean_and_translate_prompt(items_description)
        
        gender_str = "male" if gender == "male" else ("female" if gender == "female" else "person")
        age_str = f"{age}-year-old" if age else "young adult"

        prompt = (
            f"Full body fashion editorial photograph of a {age_str} {gender_str} model wearing {clean_clothes}. "
            f"Minimalist photo studio background, highly detailed fabric texture, realistic lighting, 4k"
        )

        encoded_prompt = urllib.parse.quote(prompt)
        
        # Используем проверенный публичный зеркальный сервер
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1024&nologo=true&seed={uuid.uuid4().int % 100000}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        }

        response = requests.get(image_url, headers=headers, timeout=35)
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
