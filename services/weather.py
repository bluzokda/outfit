from dataclasses import dataclass
import datetime
import requests
from config import config

WEATHER_CODES = {
    0: "ясно",
    1: "преимущественно ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозь",
    51: "лёгкая морось",
    53: "морось",
    55: "сильная морось",
    61: "небольшой дождь",
    63: "дождь",
    65: "сильный дождь",
    71: "небольшой снег",
    73: "снег",
    75: "сильный снег",
    77: "снежная крупа",
    80: "ливень",
    81: "сильный ливень",
    82: "очень сильный ливень",
    85: "снегопад",
    86: "сильный снегопад",
    95: "гроза",
    96: "гроза с градом",
    99: "сильная гроза с градом",
}

@dataclass
class WeatherInfo:
    temperature: float
    feels_like: float
    wind_speed: float
    precipitation: float
    condition_code: int
    condition_text: str
    city: str | None = None

    @property
    def is_rainy(self) -> bool:
        return self.condition_code in range(51, 68) or self.condition_code in range(80, 83)

    @property
    def is_snowy(self) -> bool:
        return self.condition_code in range(71, 78) or self.condition_code in (85, 86)

def geocode_city(city_name: str) -> tuple[float, float, str] | None:
    resp = requests.get(
        config.geocoding_api_url,
        params={"name": city_name, "count": 5, "language": "ru"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results")
    if not results:
        return None

    best_r = results[0]
    for r in results:
        country = r.get("country", "")
        if country in ["Россия", "Russia", "Беларусь", "Kazakhstan", "Казахстан"]:
            best_r = r
            break

    full_name = f"{best_r['name']}, {best_r.get('country', '')}".strip(", ")
    return best_r["latitude"], best_r["longitude"], full_name

def get_weather(lat: float, lon: float, city: str | None = None) -> WeatherInfo:
    # ВАЖНО: указываем timezone=auto, иначе Open-Meteo отдаёт часы в GMT
    # и наш расчёт текущего часа (который считает в UTC+3) съезжает.
    resp = requests.get(
        config.weather_api_url,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "temperature_unit": "celsius",
            "wind_speed_unit": "ms",
            "forecast_days": 1,
            "timezone": "auto",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    if "hourly" not in data:
        raise ValueError(f"Open-Meteo не вернул почасовые данные. Ответ: {data}")

    hourly = data["hourly"]
    times = hourly.get("time", [])
    if not times:
        raise ValueError(f"Open-Meteo вернул пустой список времени. Ответ: {data}")

    # Locale-точное текущее время: Open-Meteo при timezone=auto отдаёт ещё и
    # смещение в секундах для этой точки, используем его вместо жёстко
    # зашитого UTC+3.
    offset_seconds = data.get("utc_offset_seconds", 0)
    now_local = datetime.datetime.utcnow() + datetime.timedelta(seconds=offset_seconds)
    now_local_hour = now_local.strftime("%Y-%m-%dT%H:00")

    index = 0
    for i, t in enumerate(times):
        if t >= now_local_hour:
            index = i
            break
    else:
        index = len(times) - 1

    code = int(hourly["weather_code"][index])
    return WeatherInfo(
        temperature=float(hourly["temperature_2m"][index]),
        feels_like=float(hourly["apparent_temperature"][index]),
        wind_speed=float(hourly["wind_speed_10m"][index]),
        precipitation=float(hourly["precipitation"][index]),
        condition_code=code,
        condition_text=WEATHER_CODES.get(code, "неизвестно"),
        city=city,
    )
