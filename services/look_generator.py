import os
import uuid
import gc
from google import genai
from config import config

def generate_imagen_look(gender: str = None, age: int = None, items_description: list[str] = None, occasion: str = "") -> str | None:
    """Генерирует фото образа с помощью нативных возможностей Gemini / Google GenAI."""
    if not config.gemini_api_key:
        print("GEMINI_API_KEY не установлен в переменных окружения.")
        return None

    try:
        client = genai.Client(api_key=config.gemini_api_key)

        clothes_str = ", ".join(items_description) if items_description else "stylish modern aesthetic streetwear outfit"
        gender_str = "male" if gender == "male" else ("female" if gender == "female" else "person")
        age_str = f"{age}-year-old" if age else "young adult"

        prompt = (
            f"Generate a full-body aesthetic fashion editorial photograph of a {age_str} {gender_str} model. "
            f"Wearing: {clothes_str}. "
            f"Occasion / Vibe: {occasion}. "
            f"Minimalist studio background, clean ambient lighting, highly detailed clothing fabric textures, realistic fit, high quality, 4k resolution."
        )

        # Используем актуальный метод генерации изображений через клиент Google GenAI
        result = client.models.generate_images(
            model='gemini-2.5-flash',
            prompt=prompt,
            config=dict(
                number_of_images=1,
                aspect_ratio="3:4",
                output_mime_type="image/jpeg",
            )
        )

        os.makedirs(config.collages_dir, exist_ok=True)
        
        for generated_image in result.generated_images:
            filename = f"imagen_{uuid.uuid4().hex}.jpg"
            file_path = os.path.join(config.collages_dir, filename)

            with open(file_path, "wb") as f:
                f.write(generated_image.image.image_bytes)

            gc.collect()
            return "/" + file_path.replace(os.sep, "/")

        return None

    except Exception as e:
        print(f"Ошибка при генерации изображения через Gemini SDK: {e}")
        gc.collect()
        return None
