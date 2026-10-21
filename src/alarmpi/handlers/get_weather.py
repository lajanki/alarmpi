"""Spoken weather content, using the same data client as the GUI."""

import datetime
import logging

from alarmpi import clients
from alarmpi.clients import weather
from alarmpi.core import apcontent


event_logger = logging.getLogger("eventLogger")


class WeatherContent(apcontent.AlarmpiContent):
    def build(self):
        try:
            reading = weather.OpenWeatherMapClient(self.section_data).fetch()
        except (
            clients.SourceError, OSError, ValueError, KeyError, TypeError,
        ) as e:
            event_logger.error("Failed to build weather content: %s", e)
            self.content = "Failed to read openweathermap.org. "
            return

        wind_kmh = reading.wind_speed_kmh
        gust = ""
        if 0 < wind_kmh <= 1:
            gust = "and calm"
        elif wind_kmh > 1:
            gust = "with light air"
        for threshold, description in (
            (5, "a light breeze"),
            (12, "a gentle breeze"),
            (20, "a moderate breeze"),
            (29, "a fresh breeze"),
            (39, "a strong breeze"),
            (50, "high winds"),
            (62, "gale force winds"),
            (75, "a strong gale"),
            (89, "storm winds"),
            (103, "violent storm winds"),
            (118, "hurricane force winds"),
        ):
            if wind_kmh > threshold:
                gust = f"with {description}"
                if threshold >= 50:
                    gust += f" at {wind_kmh} kilometres per hour"

        text = (
            f"Weather for today is {reading.conditions}. "
            f"It is currently {int(reading.temp)} degrees  {gust}. "
        )
        month = datetime.datetime.today().month
        if reading.wind_speed_ms > 5 and (month < 4 or month > 10):
            text += f" There is a wind chill of {reading.wind_chill} degrees. "
        text += (
            f" The sun rises at {reading.sunrise}"
            f" and sets at {reading.sunset}."
        )
        self.content = text
