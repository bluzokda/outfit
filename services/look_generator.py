import os
import uuid
import gc
from google import genai
from google.genai import types
from config import config

def generate_imagen_look(gender: str = None, age: int = None, items_description: list[str] = None, occasion: str = "") -> str | None:
    """Генерирует фото образа через generate_content с поддержкой вывода изображений."""
    if not config.gemini_api_key:
        print("GEMINI_API_KEY не установлен в переменных окружения.")
        return None

    try:
        client = genai.Client(api_key=config.gemini_api_key)

        clothes_str = ", ".join(items_description) if items_description else "stylish modern aesthetic streetwear outfit"
        gender_str = "male" if gender == "male" else ("female" if gender == "female" else "person")
        age_str = f"{age}-year-old" if age else "young adult"

        prompt = (
            f"Generate a high-quality, full-body fashion editorial photograph of a {age_str} {gender_str} model. "
            f"Wearing: {clothes_str}. "
            f"Occasion / Vibe: {occasion}. "
            f"Minimalist studio background, clean ambient lighting, highly detailed clothing fabric textures, realistic fit, high quality, 4k resolution."
        )

        # Запрос генерации через стандартный generate_content с модальностью IMAGE
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            )
        )

        # Перебираем части ответа в поисках сгенерированного изображения
        if response.candidates:
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                            image_bytes = part.inline_data.data

                            os.makedirs(config.collages_dir, exist_ok=True)
                            filename = f"imagen_{uuid.uuid4().hex}.jpg"
                            file_path = os.path.join(config.collages_dir, filename)

                            with open(file_path, "wb") as f:
                                f.write(image_bytes)

                            gc.collect()
                            return "/" + file_path.replace(os.sep, "/")

        print("Модель не вернула изображение в ответе.")
        return None

    except Exception as e:
        print(f"Ошибка при генерации изображения через Gemini generate_content: {e}")
        gc.collect()
        return None
