from unittest.mock import Mock, mock_open, patch

import pytest
import requests

from alarmpi.clients import SourceError
from alarmpi.clients.trains import TrainClient
from alarmpi.clients.weather import OpenWeatherMapClient


WEATHER_CONFIG = {"credentials": "test-key", "city_id": 123, "units": "metric"}
WEATHER_RESPONSE = {
    "main": {"temp": 12.5},
    "wind": {"speed": 3},
    "weather": [{"description": "clear sky", "icon": "01d"}],
    "sys": {"sunrise": 1700000000, "sunset": 1700030000},
}


@pytest.fixture
def weather_client():
    with patch("builtins.open", mock_open(read_data="test-api-key")):
        return OpenWeatherMapClient(WEATHER_CONFIG)


@pytest.mark.parametrize("failure", [
    requests.ConnectionError("offline"),
    requests.Timeout("timed out"),
    requests.HTTPError("500 Server Error"),
])
def test_failing_train_api_request(failure):
    client = TrainClient({"station_code": "XYZ"})
    with patch("requests.get") as get:
        if isinstance(failure, requests.HTTPError):
            get.return_value.raise_for_status.side_effect = failure
        else:
            get.side_effect = failure
        with pytest.raises(SourceError, match=str(failure)):
            client.fetch()
        assert get.call_args.kwargs["timeout"] == (5, 10)


@pytest.mark.parametrize("failure", [
    requests.ConnectionError("offline"),
    requests.Timeout("timed out"),
    requests.HTTPError("500 Server Error"),
])
def test_failing_weather_api_request(weather_client, failure):
    with patch("requests.get") as get:
        if isinstance(failure, requests.HTTPError):
            get.return_value.raise_for_status.side_effect = failure
        else:
            get.side_effect = failure
        with pytest.raises(SourceError, match=str(failure)):
            weather_client.fetch()
        assert get.call_args.kwargs["timeout"] == (5, 10)


def test_weather_icon_failure_preserves_reading(weather_client):
    weather_client.include_icon = True
    response = Mock()
    response.json.return_value = WEATHER_RESPONSE
    responses = [response, requests.Timeout("icon offline")]
    with patch("requests.get", side_effect=responses) as get:
        reading = weather_client.fetch()
    assert reading.temp == 12.5
    assert reading.icon is None
    assert "icon offline" in reading.icon_error
    assert all(
        call.kwargs["timeout"] == (5, 10) for call in get.call_args_list
    )


def test_weather_icon_http_failure(weather_client):
    weather_client.include_icon = True
    response = Mock()
    response.json.return_value = WEATHER_RESPONSE
    icon_response = Mock()
    icon_response.raise_for_status.side_effect = requests.HTTPError("404 icon")
    with patch("requests.get", side_effect=[response, icon_response]):
        reading = weather_client.fetch()
    assert "404 icon" in reading.icon_error


def test_weather_icon_success(weather_client):
    weather_client.include_icon = True
    response = Mock()
    response.json.return_value = WEATHER_RESPONSE
    icon_response = Mock(content=b"icon-data")
    with patch("requests.get", side_effect=[response, icon_response]):
        reading = weather_client.fetch()
    assert reading.icon == b"icon-data"
    assert reading.icon_error is None
