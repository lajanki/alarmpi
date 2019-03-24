#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import datetime
import json

import apcontent


class OpenWeatherMapClient(apcontent.AlarmpiContent):
    """Fetch waether predictions from openweathermap.org
    https://openweathermap.org/api
    """

    def __init__(self, section_data):
        super().__init__(section_data)
        api_key_file = section_data["key_file"]
        self.city_id = section_data["city_id"]
        self.units = section_data["units"]

        with open(api_key_file) as f:
            self.API_KEY = json.load(f)["key"]

    def build(self):
        try:
            api_response = self.get_weather()
            weather = OpenWeatherMapClient.format_response(api_response)

            conditions = weather["conditions"]
            temperature = int(weather["temp"])
            wind_speed_kmh = weather["wind_speed_kmh"]
            wind = weather["wind_speed_ms"]
            wind_chill = weather["wind_chill"]
            sunrise = weather["sunrise"]
            sunset = weather["sunset"]

            weather_string = "Weather for today is {}. It is currently {} degrees ".format(
                conditions, temperature)

            # Wind uses the Beaufort scale
            if wind_speed_kmh < 1:
                gust = "and calm"
            if wind_speed_kmh > 1:
                gust = "with light air"
            if wind_speed_kmh > 5:
                gust = "with a light breeze"
            if wind_speed_kmh > 12:
                gust = "with a gentle breeze"
            if wind_speed_kmh > 20:
                gust = "with a moderate breeze"
            if wind_speed_kmh > 29:
                gust = "with a fresh breeze"
            if wind_speed_kmh > 39:
                gust = "with a strong breeze"
            if wind_speed_kmh > 50:
                gust = "with high winds at " + wind_speed_kmh + "kilometres per hour"
            if wind_speed_kmh > 62:
                gust = "with gale force winds at " + wind_speed_kmh + "kilometres per hour"
            if wind_speed_kmh > 75:
                gust = "with a strong gale at " + wind_speed_kmh + "kilometres per hour"
            if wind_speed_kmh > 89:
                gust = "with storm winds at " + wind_speed_kmh + "kilometres per hour"
            if wind_speed_kmh > 103:
                gust = "with violent storm winds at " + wind_speed_kmh + "kilometres per hour"
            if wind_speed_kmh > 118:
                gust = "with hurricane force winds at " + wind_speed_kmh + "kilometres per hour"
            if not wind_speed_kmh:
                gust = ""
            weather_string += " {}. ".format(gust)

            # Add wind chill effect for November - March period
            month = datetime.datetime.today().month
            if wind > 5 and (month < 4 or month > 10):
                weather_string += " There is a wind chill of {} degrees. ".format(wind_chill)

            weather_string += " The sun rises at {} and sets at {}.".format(sunrise, sunset)

        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
            weather_string = "Failed to connect to openweathermap.org. "
        # API response doesn"t contain the path listed above
        except TypeError:
            weather_string = "Failed to read openweathermap.org. "

        self.content = weather_string

    def get_weather(self):
        url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            "APPID": self.API_KEY,
            "id": self.city_id,
            "units": "metric"
        }

        r = requests.get(url, params=params)
        return r.json()

    @staticmethod
    def format_response(response):
        today_temp = response["main"]["temp"]
        conditions = response["weather"][0]["description"]
        wind = response["wind"]["speed"]  # wind speed in m/s

        # Convert wind speed to km/h
        wind_speed_kmh = OpenWeatherMapClient.ms_to_kmh(wind)
        wind_chill = OpenWeatherMapClient.compute_wind_chill(today_temp, wind_speed_kmh)
        wind_chill = round(wind_chill)

        sunrise = OpenWeatherMapClient.timesamp_to_time_str(response["sys"]["sunrise"])
        sunset = OpenWeatherMapClient.timesamp_to_time_str(response["sys"]["sunset"])

        formatted = {
            "temp": today_temp,
            "conditions": conditions,
            "wind_speed_ms": wind,
            "wind_speed_kmh": wind_speed_kmh,
            "wind_chill": wind_chill,
            "sunrise": sunrise,
            "sunset": sunset
        }

        return formatted

    @staticmethod
    def get_weather_icon(icon_id):
        """Get weather icon matching an id from the response.
        https://openweathermap.org/weather-conditions
        """
        url = "http://openweathermap.org/img/w/{}.png".format(icon_id)
        r = requests.get(url)
        return r.content  # return binary content

    @staticmethod
    def ms_to_kmh(wind_speed):
        """Convert wind speed measure from meters/second to kilometres/hour."""
        return wind_speed * 3.6

    @staticmethod
    def compute_wind_chill(temp, wind_speed):
        """Compute wind chill given a temperature in Celsius and wind speed in kilometres/hour.
        See https://en.wikipedia.org/wiki/Wind_chill
        """
        return 13.12 + 0.6215 * temp - 11.37 * wind_speed**(0.16) + 0.3965 * temp * wind_speed**(0.16)

    @staticmethod
    def timesamp_to_time_str(ts):
        """Convert a UNIX timestamp in seconds to a time string (ie. 8:43 am)."""
        dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime("%I:%M %p")

    @staticmethod
    def fahrenheit_to_celsius(temp):
        """Convert a temperature in Fahrenheit to Celsius."""
        return int((temp - 32) * 5.0/9)
