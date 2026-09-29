import os
import uuid
from google import genai
from config import config

def generate_imagen_look(gender: str = None, age: int = None, items_description: list[str] = None, occasion: str = "") -> str | None:
    """Генерирует фото образа в полный рост через Imagen 3 на основе выбранных вещей."""
    if not config.gemini_api_key:
        print("ОБРАТИТЕ ВНИМАНИЕ: GEMINI_API_KEY не установлен.")
        return None

    try:
        client = genai.Client(api_key=config.gemini_api_key)

        # Подготовка параметров для промпта
        clothes_str = ", ".join(items_description) if items_description else "stylish modern aesthetic streetwear outfit"
        gender_str = "male" if gender == "male" else ("female" if gender == "female" else "person")
        age_str = f"{age}-year-old" if age else "young adult"

        # Детализированный промпт для фотосессии
        prompt = (
            f"Full-body aesthetic fashion editorial photograph of a {age_str} {gender_str} model. "
            f"Wearing: {clothes_str}. "
            f"Occasion / Vibe: {occasion}. "
            f"Minimalist studio background, clean ambient lighting, highly detailed clothing fabric textures, realistic fit, high quality, 4k."
        )

        # Вызов модели Imagen 3
        result = client.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt=prompt,
            config=dict(
                number_of_images=1,
                aspect_ratio="3:4",  # Вертикальное соотношение для карточки
                output_mime_type="image/jpeg",
            )
        )

        os.makedirs(config.collages_dir, exist_ok=True)
        for generated_image in result.generated_images:
            filename = f"imagen_{uuid.uuid4().hex}.jpg"
            file_path = os.path.join(config.collages_dir, filename)

            with open(file_path, "wb") as f:
                f.write(generated_image.image.image_bytes)

            return "/" + file_path.replace(os.sep, "/")

    except Exception as e:
        print(f"Ошибка при генерации изображения через Imagen 3: {e}")
        return None
