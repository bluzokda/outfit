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
    except Exception:
        return None

def get_weather(lat: float, lon: float, city: str | None = None) -> WeatherInfo:
    try:
        # Запрашиваем почасовые данные, так как они точнее отражают текущий час
        resp = requests.get(
            config.weather_api_url,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
                "temperature_unit": "celsius",
                "wind_speed_unit": "ms",
                "forecast_days": 1
            },
            timeout=10,
        )
        data = resp.json()
        if isinstance(data, dict) and "hourly" in data:
            hourly = data["hourly"]
            times = hourly.get("time", [])
            
            # Находим индекс текущего часа
            current_hour_str = datetime.datetime.now().strftime("%Y-%m-%dT%H:00")
            index = 0
            for i, t in enumerate(times):
                if t.startswith(datetime.datetime.now().strftime("%Y-%m-%dT%H")):
                    index = i
                    break

            code = int(hourly.get("weather_code", [0])[index])
            return WeatherInfo(
                temperature=float(hourly.get("temperature_2m", [15.0])[index]),
                feels_like=float(hourly.get("apparent_temperature", [15.0])[index]),
                wind_speed=float(hourly.get("wind_speed_10m", [3.0])[index]),
                precipitation=float(hourly.get("precipitation", [0.0])[index]),
                condition_code=code,
                condition_text=WEATHER_CODES.get(code, "ясно"),
                city=city,
            )
    except Exception:
        pass

    return WeatherInfo(
        temperature=11.0,
        feels_like=10.0,
        wind_speed=1.1,
        precipitation=0.0,
        condition_code=3,
        condition_text="пасмурно",
        city=city,
    )
