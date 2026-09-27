from dataclasses import dataclass
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
    try:
        resp = requests.get(
            config.geocoding_api_url,
            params={"name": city_name, "count": 5, "language": "ru"},
            timeout=10,
        )
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
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None

def get_weather(lat: float, lon: float, city: str | None = None) -> WeatherInfo:
    try:
        resp = requests.get(
            config.weather_api_url,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,wind_speed_10m,precipitation,weather_code",
                "temperature_unit": "celsius",
                "wind_speed_unit": "ms",
            },
            timeout=10,
        )
        
        # Печатаем статус и ответ в консоль, чтобы увидеть причину
        print(f"Weather API status code: {resp.status_code}")
        data = resp.json()
        print(f"Weather API response: {data}")

        if not isinstance(data, dict) or "current" not in data:
            raise ValueError("Invalid response structure from weather API")

        current = data["current"]
        code = current.get("weather_code", 0)
        
        return WeatherInfo(
            temperature=float(current.get("temperature_2m", 20.0)),
            feels_like=float(current.get("apparent_temperature", 20.0)),
            wind_speed=float(current.get("wind_speed_10m", 3.0)),
            precipitation=float(current.get("precipitation", 0.0)),
            condition_code=int(code),
            condition_text=WEATHER_CODES.get(int(code), "ясно"),
            city=city,
        )
    except Exception as e:
        print(f"Weather API failed, fallback used. Error: {e}")
        return WeatherInfo(
            temperature=20.0,
            feels_like=20.0,
            wind_speed=3.0,
            precipitation=0.0,
            condition_code=0,
            condition_text="ясно",
            city=city,
        )
