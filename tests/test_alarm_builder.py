import pytest
import os.path
import requests
from unittest.mock import patch, Mock

from freezegun import freeze_time

from alarmpi.core import apconfig, alarm_builder
from alarmpi.handlers import (
    get_google_translate_tts,
    get_festival_tts,
    get_bbc_news,
    get_gcp_tts,
    get_greeting,
    get_weather
)


@pytest.fixture
def dummy_alarm_builder():
    """Create an AlarmBuilder from the config file."""
    PATH_TO_CONFIG = os.path.join(os.path.dirname(__file__), "test_alarm.yaml")
    config = apconfig.AlarmConfig(PATH_TO_CONFIG)
    return alarm_builder.AlarmBuilder(config)

def test_enabled_tts_client_chosen(dummy_alarm_builder):
    """Does get_tts_client choose the enabled client?"""
    dummy_alarm_builder.config["TTS"]["GCP"]["enabled"] = False
    dummy_alarm_builder.config["TTS"]["google_translate"]["enabled"] = True
    dummy_alarm_builder.config["TTS"]["festival"]["enabled"] = False

    client = dummy_alarm_builder.get_tts_client()
    assert isinstance(client, get_google_translate_tts.GoogleTranslateTTSManager)

def test_default_TTS_client_chosen_when_none_set(dummy_alarm_builder):
    """Is the Festival client chosen in get_tts_client when none is explicitly enaled?"""
    dummy_alarm_builder.config["TTS"]["GCP"]["enabled"] = False
    dummy_alarm_builder.config["TTS"]["google_translate"]["enabled"] = False
    dummy_alarm_builder.config["TTS"]["festival"]["enabled"] = False

    client = dummy_alarm_builder.get_tts_client()
    assert isinstance(client, get_festival_tts.FestivalTTSManager)

def test_correct_content_parser_chosen(dummy_alarm_builder):
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
        created_class = dummy_alarm_builder.get_content_parser_class({"handler": module})
        assert created_class == class_

@patch("alarmpi.core.alarm_builder.AlarmBuilder.play_beep")
def test_beep_played_when_tts_fails(mock_play_beep, dummy_alarm_builder):
    """Is the beep played when a network error occurs?"""
    dummy_alarm_builder.tts_client = Mock()
    dummy_alarm_builder.tts_client.play.side_effect = requests.exceptions.HTTPError
    dummy_alarm_builder.audio = Mock()

    dummy_alarm_builder.play()
    mock_play_beep.assert_called()

@patch("alarmpi.core.alarm_builder.AlarmBuilder.play_beep")
def test_beep_played_when_tts_disabled(mock_play_beep, dummy_alarm_builder):
    """Is the beep played when TTS is disabled in the configuration?"""
    dummy_alarm_builder.config["main"]["TTS"] = False

    dummy_alarm_builder.play()
    mock_play_beep.assert_called()

def test_alarm_time_override(dummy_alarm_builder):
    """Is alarm time overridden when value specified in config?"""
    dummy_alarm_builder.config["main"]["alarm_time"] = "20:21"
    greeting = dummy_alarm_builder.generate_greeting()
    assert "The time is 08:21" in greeting

def test_alarm_time_without_override(dummy_alarm_builder):
    """Is alarm time current time?"""
    greeting = dummy_alarm_builder.generate_greeting()
    assert "the time is 07:02" in greeting.lower()

@patch("alarmpi.core.alarm_builder.MediaPlayWorker")
def test_wakeup_song_played(mock_media_play_worker):
    """Is the wakeup song thread started as part of the alarm when enabled?"""

    # Create a builder with the mocked media worker
    PATH_TO_CONFIG = os.path.join(os.path.dirname(__file__), "test_alarm.yaml")
    config = apconfig.AlarmConfig(PATH_TO_CONFIG)
    builder = alarm_builder.AlarmBuilder(config)
    builder.config["main"]["TTS"] = False
    builder.config["media"]["enabled"] = True

    builder.play()
    builder.media_play_thread.start.assert_called()
