import pytest
import os.path
from unittest.mock import patch

from src import apconfig
from src import alarm_builder
from src.handlers import (
    get_google_translate_tts,
    get_festival_tts,
    get_bbc_news,
    get_gcp_tts,
    get_greeting,
    get_weather
)


@pytest.fixture
@patch("src.apconfig.AlarmConfig.get_config_file_path")
def dummy_alarm(mock_get_config_file_path):
    """Create a dummy alarm from test_alarm.conf"""
    mock_get_config_file_path.return_value = os.path.join(os.path.dirname(__file__), "test_alarm.yaml")

    config = apconfig.AlarmConfig("")
    return alarm_builder.Alarm(config)

def test_enabled_tts_client_chosen(dummy_alarm):
    """Does get_tts_client choose the enabled client?"""
    dummy_alarm.config["TTS"]["GCP"]["enabled"] = False
    dummy_alarm.config["TTS"]["google_translate"]["enabled"] = True
    dummy_alarm.config["TTS"]["festival"]["enabled"] = False

    client = dummy_alarm.get_tts_client()
    assert isinstance(client, get_google_translate_tts.GoogleTranslateTTSManager)

def test_default_TTS_client_chosen_when_none_set(dummy_alarm):
    """Is the Festival client chosen in get_tts_client when none is explicitly enaled?"""
    dummy_alarm.config["TTS"]["GCP"]["enabled"] = False
    dummy_alarm.config["TTS"]["google_translate"]["enabled"] = False
    dummy_alarm.config["TTS"]["festival"]["enabled"] = False

    client = dummy_alarm.get_tts_client()
    assert isinstance(client, get_festival_tts.FestivalTTSManager)

def test_correct_content_parser_chosen(dummy_alarm):
    """Given a content section, is the correct class chosen in get_content_parser_class?"""
    handler_map = {
        "get_bbc_news.py": get_bbc_news.NewsParser,
        "get_festival_tts.py": get_festival_tts.FestivalTTSManager,
        "get_gcp_tts.py": get_gcp_tts.GoogleCloudTTS,
        "get_google_translate_tts.py": get_google_translate_tts.GoogleTranslateTTSManager,
        "get_greeting.py":  get_greeting.Greeting,
        "get_weather.py": get_weather.OpenWeatherMapClient
    }

    for module, class_ in handler_map.items():
        created_class = dummy_alarm.get_content_parser_class({"handler": module})
        assert created_class == class_

@patch("src.apconfig.AlarmConfig._testnet")
@patch("src.alarm_builder.Alarm.play_beep")
def test_beep_played_when_no_network(mock_play_beep, mock_testnet, dummy_alarm):
    """Is the beep played when no network connection is detected?"""
    mock_testnet.return_value = False

    dummy_alarm.play("dummy_content")
    mock_play_beep.assert_called()


@patch("src.alarm_builder.Alarm.play_beep")
def test_beep_played_when_tts_disabled(mock_play_beep, dummy_alarm):
    """Is the beep played when TTS is disabled in the configuration?"""
    dummy_alarm.config["main"]["TTS"] = False

    dummy_alarm.play("dummy_content")
    mock_play_beep.assert_called()
