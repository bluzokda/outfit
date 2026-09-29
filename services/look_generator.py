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
    """Генерирует качественный фото-образ с человеком в одежде."""
    hf_token = os.getenv("HF_TOKEN") or getattr(config, "hf_token", None)

    clean_clothes = clean_and_translate_prompt(items_description)
    gender_str = "male" if gender == "male" else ("female" if gender == "female" else "person")
    age_str = f"{age}-year-old" if age else "young adult"

    # Детальный промпт для SDXL
    prompt = (
        f"Full length body portrait photo of a realistic {age_str} {gender_str} model wearing {clean_clothes}. "
        f"Studio lighting, fashion magazine photography, clean minimalist background, ultra realistic, highly detailed, 8k"
    )

    # 1. Пробуем через Hugging Face (SDXL base - самая стабильная работающая модель)
    if hf_token:
        try:
            url = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"
            headers = {"Authorization": f"Bearer {hf_token}", "Content-Type": "application/json"}
            payload = {"inputs": prompt, "parameters": {"width": 768, "height": 1024}}

            res = requests.post(url, headers=headers, json=payload, timeout=40)
            if res.ok and len(res.content) > 5000:
                return save_image(res.content)
            else:
                print(f"HF SDXL returned {res.status_code}: {res.text}")
        except Exception as e:
            print(f"HF Error: {e}")

    # 2. Фоллбэк: Публичный безлимитный API от нейросети Prodia / Rapid
    try:
        encoded_prompt = requests.utils.quote(prompt)
        # Использование прямого генератора без странных заглушек
        fallback_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1024&model=turbo&nologo=true"
        
        res = requests.get(fallback_url, timeout=40)
        if res.ok and len(res.content) > 5000:
            return save_image(res.content)
    except Exception as e:
        print(f"Fallback Error: {e}")

    return None

def save_image(image_bytes: bytes) -> str:
    """Сохраняет полученное изображение во фреймворке."""
    os.makedirs(config.collages_dir, exist_ok=True)
    filename = f"look_{uuid.uuid4().hex}.jpg"
    file_path = os.path.join(config.collages_dir, filename)

    with open(file_path, "wb") as f:
        f.write(image_bytes)

    gc.collect()
    return "/" + file_path.replace(os.sep, "/")
