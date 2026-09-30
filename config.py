import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    db_path: str = os.getenv("DB_PATH", "outfit.db")
    upload_dir: str = os.getenv("UPLOAD_DIR", "static/uploads")
    collages_dir: str = os.getenv("COLLAGES_DIR", "static/collages")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")  # оставлено на случай отката
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_text_model: str = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
    gemini_image_model: str = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    weather_api_url: str = "https://api.open-meteo.com/v1/forecast"  # больше не используется, оставлено для справки
    geocoding_api_url: str = "https://geocoding-api.open-meteo.com/v1/search"  # больше не используется
    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    openweather_geocoding_url: str = "http://api.openweathermap.org/geo/1.0/direct"
    openweather_current_url: str = "https://api.openweathermap.org/data/2.5/weather"
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")


config = Config()
