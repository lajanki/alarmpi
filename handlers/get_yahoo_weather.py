#!/usr/bin/env python
# -*- coding: utf-8 -*-


import requests
import datetime

import apcontent


class YahooWeatherClient(apcontent.AlarmpiContent):
    """Fetches weather data for the woeid set in the config file using YQL and Yahoo Weather service."""

    def __init__(self, section_data):
        super().__init__(section_data)
        try:
            self.build()
        except KeyError as e:
            print("Error: missing key {} in configuration file.".format(e))

    def build(self):
        location = self.section_data['location']
        unit = self.section_data["unit"]

        url = "https://query.yahooapis.com/v1/public/yql"
        params = {
            "q": "env 'store://datatables.org/alltableswithkeys'; SELECT * FROM weather.forecast WHERE u='{}' AND woeid={}".format(unit, location),
            "format": "json",
            "env": "env=store://datatables.org/alltableswithkeys"
        }

        try:
            r = requests.get(url, params=params)
            response_dictionary = r.json()

            today_temp = response_dictionary['query']['results']['channel']['item']['condition']['temp']
            today_low = response_dictionary['query']['results']['channel']['item']['forecast'][0]['low']
            today_high = response_dictionary['query']['results']['channel']['item']['forecast'][0]['high']
            conditions = response_dictionary['query']['results']['channel']['item']['condition']['text']
            forecast_conditions = response_dictionary['query']['results']['channel']['item']['forecast'][0]['text']
            wind = response_dictionary['query']['results']['channel']['wind']['speed']
            wind_chill = response_dictionary['query']['results']['channel']['wind']['chill']
            # TODO: change syntax from 8.5 pm to 20:50
            sunrise = response_dictionary['query']['results']['channel']['astronomy']['sunrise']
            sunset = response_dictionary['query']['results']['channel']['astronomy']['sunset']

            if wind:
                wind = round(float(wind), 1)

            if conditions != forecast_conditions:
                conditions = conditions + ' becoming ' + forecast_conditions
            weather_yahoo = 'Weather for today is {}. It is currently {} degrees '.format(
                conditions, today_temp)

            # Wind uses the Beaufort scale
            if self.section_data['wind'] == "1":
                if wind < 1:
                    gust = 'and calm'
                if wind > 1:
                    gust = 'with light air'
                if wind > 5:
                    gust = 'with a light breeze'
                if wind > 12:
                    gust = 'with a gentle breeze'
                if wind > 20:
                    gust = 'with a moderate breeze'
                if wind > 29:
                    gust = 'with a fresh breeze'
                if wind > 39:
                    gust = 'with a strong breeze'
                if wind > 50:
                    gust = 'with high winds at ' + wind + 'kilometres per hour'
                if wind > 62:
                    gust = 'with gale force winds at ' + wind + 'kilometres per hour'
                if wind > 75:
                    gust = 'with a strong gale at ' + wind + 'kilometres per hour'
                if wind > 89:
                    gust = 'with storm winds at ' + wind + 'kilometres per hour'
                if wind > 103:
                    gust = 'with violent storm winds at ' + wind + 'kilometres per hour'
                if wind > 118:
                    gust = 'with hurricane force winds at ' + wind + 'kilometres per hour'
                if not wind:
                    gust = ''
                weather_yahoo += " {}. ".format(gust)

            # Add wind chill effect for November - March period
            month = datetime.datetime.today().month
            if self.section_data['wind_chill'] == "1" and wind > 5 and (month < 4 or month > 10):
                weather_yahoo += ' And a windchill of {}. '.format(wind_chill)

            weather_yahoo += "The high for today is {} and the low at {} degrees.".format(
                today_high, today_low)
            weather_yahoo += " The sun rises at {} and sets at {}.".format(sunrise, sunset)

        except requests.exceptions.HTTPError:
            weather_yahoo = 'Failed to connect to Yahoo Weather.  '
        # API response doesn't contain the path listed above
        except TypeError:
            weather_yahoo = "Failed to read Yahoo Weather. "

        self.content = weather_yahoo