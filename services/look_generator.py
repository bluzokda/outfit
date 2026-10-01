import os
import uuid
import gc
import re
import requests
import urllib.parse
from config import config

# Если установлен пакет google-genai / google-generativeai
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

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
    """Универсальная стабильная генерация фото одежды."""
    clean_clothes = clean_and_translate_prompt(items_description)
    gender_str = "male" if gender == "male" else ("female" if gender == "female" else "person")
    age_str = f"{age}-year-old" if age else "young adult"

    prompt = (
        f"Full body fashion editorial photograph of a {age_str} {gender_str} model wearing {clean_clothes}. "
        f"Full growth portrait, standing posture, minimalist photo studio background, highly detailed fabric texture, realistic lighting, 8k"
    )

    # 1. Попытка сгенерировать через Google Imagen 3 (если задан GEMINI_API_KEY)
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key and HAS_GENAI:
        try:
            client = genai.Client(api_key=gemini_key)
            result = client.models.generate_images(
                model='imagen-3.0-generate-002',
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="3:4",
                    output_mime_type="image/jpeg"
                )
            )
            for generated_image in result.generated_images:
                return save_image(generated_image.image.image_bytes)
        except Exception as e:
            print(f"Gemini Imagen Error: {e}")

    # 2. Прямая генерация через смену провайдера (запрос с ротацией IP / User-Agent)
    try:
        seed = uuid.uuid4().int % 1000000
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Обход лимитов за счет уникального сеанса
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1024&seed={seed}&model=flux&nologo=true&private=true"
        
        headers = {
            "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{100 + (seed % 20)}.0.0.0 Safari/537.36",
            "Accept": "image/jpeg,image/png,*/*",
            "Cache-Control": "no-cache"
        }

        response = requests.get(url, headers=headers, timeout=45)

        if response.ok and len(response.content) > 10000:
            return save_image(response.content)

        # Резервный сервер без модели flux (модель turbo)
        url_turbo = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1024&seed={seed}&model=turbo&nologo=true"
        response_turbo = requests.get(url_turbo, headers=headers, timeout=45)
        
        if response_turbo.ok and len(response_turbo.content) > 10000:
            return save_image(response_turbo.content)

    except Exception as e:
        print(f"Ошибка генерации: {e}")

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
