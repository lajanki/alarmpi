from unittest.mock import mock_open, patch

import requests

from alarmpi.handlers.get_weather import WeatherContent
from tests.test_clients import WEATHER_CONFIG, WEATHER_RESPONSE


def test_weather_speech_does_not_download_icon():
    with (
        patch("builtins.open", mock_open(read_data="test-api-key")),
        patch("requests.get") as get,
    ):
        get.return_value.json.return_value = WEATHER_RESPONSE
        content = WeatherContent(WEATHER_CONFIG)
        content.build()
    speech = content.get()
    assert speech is not None
    assert "clear sky" in speech
    assert "12 degrees" in speech
    get.assert_called_once()


def test_weather_speech_reports_failure(caplog):
    with patch("requests.get", side_effect=requests.Timeout("offline")):
        with patch("builtins.open", mock_open(read_data="test-api-key")):
            content = WeatherContent(WEATHER_CONFIG)
            content.build()
    assert content.get() == "Failed to read openweathermap.org. "
    assert "offline" in caplog.text


def test_weather_high_wind_speech():
    response = {
        **WEATHER_RESPONSE, "wind": {"speed": 40},
    }
    with (
        patch("builtins.open", mock_open(read_data="test-api-key")),
        patch("requests.get") as get,
    ):
        get.return_value.json.return_value = response
        content = WeatherContent(WEATHER_CONFIG)
        content.build()
    speech = content.get()
    assert speech is not None
    assert "hurricane force winds at 144.0 kilometres per hour" in speech
