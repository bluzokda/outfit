from dataclasses import dataclass

import requests

from config import config

# OpenWeatherMap отдаёт "id" погодного явления и готовое описание на нужном
# языке (через параметр lang=ru), поэтому свой словарь кодов не нужен —
# используем условный_id только для is_rainy / is_snowy.


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
        return 200 <= self.condition_code < 600

    @property
    def is_snowy(self) -> bool:
        return 600 <= self.condition_code < 700


def geocode_city(city_name: str) -> tuple[float, float, str] | None:
    resp = requests.get(
        config.openweather_geocoding_url,
        params={"q": city_name, "limit": 1, "appid": config.openweather_api_key},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None

    r = results[0]
    name = r.get("local_names", {}).get("ru", r.get("name", city_name))
    full_name = f"{name}, {r.get('country', '')}".strip(", ")
    return r["lat"], r["lon"], full_name


def get_weather(lat: float, lon: float, city: str | None = None) -> WeatherInfo:
    resp = requests.get(
        config.openweather_current_url,
        params={
            "lat": lat,
            "lon": lon,
            "appid": config.openweather_api_key,
            "units": "metric",
            "lang": "ru",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    main = data["main"]
    wind = data.get("wind", {})
    weather_block = data["weather"][0]
    # осадки за последний час, если есть (иначе 0)
    precipitation = data.get("rain", {}).get("1h", 0.0) + data.get("snow", {}).get("1h", 0.0)

    return WeatherInfo(
        temperature=main["temp"],
        feels_like=main["feels_like"],
        wind_speed=wind.get("speed", 0.0),
        precipitation=precipitation,
        condition_code=weather_block["id"],
        condition_text=weather_block["description"],
        city=city,
    )
