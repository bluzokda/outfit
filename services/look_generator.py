import os
import uuid
import base64
import requests
from config import config

def generate_imagen_look(gender: str = None, age: int = None, items_description: list[str] = None, occasion: str = "") -> str | None:
    """Генерирует фото образа через Imagen 3 REST API (для обычных ключей AI Studio)."""
    if not config.gemini_api_key:
        print("GEMINI_API_KEY не установлен в переменных окружения.")
        return None

    try:
        clothes_str = ", ".join(items_description) if items_description else "stylish modern aesthetic streetwear outfit"
        gender_str = "male" if gender == "male" else ("female" if gender == "female" else "person")
        age_str = f"{age}-year-old" if age else "young adult"

        prompt = (
            f"Full-body aesthetic fashion editorial photograph of a {age_str} {gender_str} model. "
            f"Wearing: {clothes_str}. "
            f"Occasion / Vibe: {occasion}. "
            f"Minimalist studio background, clean ambient lighting, highly detailed clothing fabric textures, realistic fit, high quality, 4k."
        )

        # Прямой REST API эндпоинт Google AI Studio для Imagen 3
        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={config.gemini_api_key}"
        
        payload = {
            "instances": [
                {"prompt": prompt}
            ],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": "3:4",
                "outputMimeType": "image/jpeg"
            }
        }

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        predictions = data.get("predictions", [])
        if not predictions:
            print("Imagen API не вернул изображение:", data)
            return None

        # Декодируем картинку из Base64
        image_b64 = predictions[0].get("bytesBase64Encoded")
        if not image_b64:
            return None

        image_bytes = base64.b64decode(image_b64)

        # Сохраняем в static/collages/
        os.makedirs(config.collages_dir, exist_ok=True)
        filename = f"imagen_{uuid.uuid4().hex}.jpg"
        file_path = os.path.join(config.collages_dir, filename)

        with open(file_path, "wb") as f:
            f.write(image_bytes)

        return "/" + file_path.replace(os.sep, "/")

    except Exception as e:
        print(f"Ошибка при генерации изображения через Imagen 3 REST API: {e}")
        return None
