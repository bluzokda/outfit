import os
import uuid
import gc
import urllib.parse
import requests
from config import config

def generate_imagen_look(gender: str = None, age: int = None, items_description: list[str] = None, occasion: str = "") -> str | None:
    """Генерирует фото образа через надежный и стабильный сервис генерации картинок."""
    try:
        clothes_str = ", ".join(items_description) if items_description else "stylish modern aesthetic streetwear outfit"
        gender_str = "male" if gender == "male" else ("female" if gender == "female" else "person")
        age_str = f"{age}-year-old" if age else "young adult"

        prompt = (
            f"Full-body fashion editorial photograph of a {age_str} {gender_str} model wearing {clothes_str}. "
            f"Vibe: {occasion}. Minimalist photo studio background, highly detailed fabric texture, realistic lighting, 4k."
        )

        # Кодируем промпт для URL
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Формируем URL к стабильному генератору (Flux/Pollinations)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1024&nologo=true&model=flux"

        # Скачиваем сгенерированное изображение
        response = requests.get(image_url, timeout=40)
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
