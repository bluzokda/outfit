import os
import uuid
import base64
import gc
import json
import requests
from config import config

def generate_imagen_look(gender: str = None, age: int = None, items_description: list[str] = None, occasion: str = "") -> str | None:
    """Генерирует фото образа через актуальный Interactions API с моделью gemini-3.8-flash."""
    if not config.gemini_api_key:
        print("GEMINI_API_KEY не установлен в переменных окружения.")
        return None

    try:
        clothes_str = ", ".join(items_description) if items_description else "stylish modern aesthetic streetwear outfit"
        gender_str = "male" if gender == "male" else ("female" if gender == "female" else "person")
        age_str = f"{age}-year-old" if age else "young adult"

        prompt = (
            f"Generate a high-quality, full-body fashion editorial photograph of a {age_str} {gender_str} model. "
            f"Wearing: {clothes_str}. "
            f"Occasion / Vibe: {occasion}. "
            f"Minimalist studio background, clean ambient lighting, highly detailed clothing fabric textures, realistic fit, high quality, 4k resolution."
        )

        # Используем проверенный Interactions API из вашего config.py
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
                    "type": "image"  # Запрашиваем генерацию изображения
                }
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        # Извлекаем байты изображения из шагов ответа Interactions API
        image_bytes = None
        for step in data.get("steps", []):
            if step.get("type") == "model_output":
                for block in step.get("content", []):
                    if block.get("type") == "image" and "data" in block:
                        image_bytes = base64.b64decode(block["data"])
                        break

        del data

        if not image_bytes:
            print("Interactions API не вернул изображение в ответе.")
            return None

        os.makedirs(config.collages_dir, exist_ok=True)
        filename = f"imagen_{uuid.uuid4().hex}.jpg"
        file_path = os.path.join(config.collages_dir, filename)

        with open(file_path, "wb") as f:
            f.write(image_bytes)

        del image_bytes
        gc.collect()

        return "/" + file_path.replace(os.sep, "/")

    except Exception as e:
        print(f"Ошибка при генерации изображения через Interactions API: {e}")
        gc.collect()
        return None
