import os
import uuid
import gc
import urllib.parse
import requests
from config import config

# Простой словарь для перевода категорий/названий одежды на английский язык
TRANSLATIONS = {
    "Верхняя одежда": "outerwear jacket",
    "Верх (футболка/рубашка/свитер)": "top shirt sweater",
    "Низ (брюки/юбка)": "pants trousers",
    "Платье/комбинезон": "dress",
    "Обувь": "shoes sneakers",
    "Аксессуар": "accessory",
    "Ветровка на флисе": "fleece lined windbreaker jacket",
    "Худи оверсайз": "oversized hoodie",
    "Спортивные джоггеры": "sports jogger pants",
    "Удобные кроссовки": "comfortable sneakers",
    "Трикотажная шапка": "knit beanie hat",
}

def translate_to_en(text: str) -> str:
    """Переводит русские описания одежды на английский язык для стабильной генерации."""
    for ru, en in TRANSLATIONS.items():
        text = text.replace(ru, en)
    return text

def generate_imagen_look(gender: str = None, age: int = None, items_description: list[str] = None, occasion: str = "") -> str | None:
    """Генерирует фото образа через полностью бесплатную и стабильную модель."""
    try:
        # Переводим вещи на английский
        translated_items = [translate_to_en(str(item)) for item in (items_description or [])]
        clothes_str = ", ".join(translated_items) if translated_items else "stylish modern streetwear outfit"
        
        gender_str = "male" if gender == "male" else ("female" if gender == "female" else "person")
        age_str = f"{age}-year-old" if age else "young adult"

        prompt = (
            f"Full-body fashion editorial photograph of a {age_str} {gender_str} model wearing {clothes_str}. "
            f"Vibe: {occasion}. Minimalist photo studio background, highly detailed fabric texture, realistic lighting, 4k"
        )

        encoded_prompt = urllib.parse.quote(prompt)
        
        # Используем бесплатный эндпоинт по умолчанию (без параметра model=flux)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1024&nologo=true"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        response = requests.get(image_url, headers=headers, timeout=30)
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
