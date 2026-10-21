import datetime
from dataclasses import dataclass

import requests

from alarmpi.clients import SourceError


@dataclass(frozen=True)
class WeatherReading:
    temp: float
    conditions: str
    wind_speed_ms: float
    wind_speed_kmh: float
    wind_chill: int
    sunrise: str
    sunset: str
    icon: bytes | None = None
    icon_error: str | None = None


class OpenWeatherMapClient:
    """Fetch weather independently of Qt and spoken alarm content."""

    def __init__(self, section_data, *, include_icon=False):
        self.city_id = section_data["city_id"]
        self.include_icon = include_icon
        try:
            with open(section_data["credentials"]) as f:
                self.credentials = f.read().strip()
        except (OSError, UnicodeError) as e:
            raise SourceError("Unable to read weather credentials") from e

    def fetch(self) -> WeatherReading:
        params = {
            "appid": self.credentials, "id": self.city_id, "units": "metric",
        }
        try:
            response = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params=params,
                timeout=(5, 10),
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise SourceError(f"Weather request failed: {e}") from e

        temperature = data["main"]["temp"]
        wind = data["wind"]["speed"]
        wind_kmh = self.ms_to_kmh(wind)
        icon = None
        icon_error = None
        if self.include_icon:
            try:
                icon = self.get_weather_icon(data["weather"][0]["icon"])
            except SourceError as e:
                icon_error = str(e)

        return WeatherReading(
            temp=temperature,
            conditions=data["weather"][0]["description"],
            wind_speed_ms=wind,
            wind_speed_kmh=wind_kmh,
            wind_chill=round(self.compute_wind_chill(temperature, wind_kmh)),
            sunrise=self.timesamp_to_time_str(data["sys"]["sunrise"]),
            sunset=self.timesamp_to_time_str(data["sys"]["sunset"]),
            icon=icon,
            icon_error=icon_error,
        )

    @staticmethod
    def get_weather_icon(icon_id) -> bytes:
        try:
            response = requests.get(
                f"https://openweathermap.org/img/wn/{icon_id}@2x.png",
                timeout=(5, 10),
            )
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            raise SourceError(f"Weather icon request failed: {e}") from e

    @staticmethod
    def ms_to_kmh(wind_speed):
        return wind_speed * 3.6

    @staticmethod
    def compute_wind_chill(temp, wind_speed):
        # Canadian/US wind chill index: temperature in Celsius, wind in km/h.
        # Defined for temperatures <= 10 C and wind speeds > 4.8 km/h.
        # https://en.wikipedia.org/wiki/Wind_chill#North_American_and_United_Kingdom_wind_chill_index
        return (
            13.12 + 0.6215 * temp - 11.37 * wind_speed ** 0.16
            + 0.3965 * temp * wind_speed ** 0.16
        )

    @staticmethod
    def timesamp_to_time_str(ts):
        return datetime.datetime.fromtimestamp(ts).strftime("%I:%M %p")

    def close(self):
        # No persistent resources to release.
        return
