import pytest
import os.path

from unittest.mock import patch

from src import apconfig



@pytest.fixture
def dummy_config():
    """Create a AlarmConfig from the config file."""
    PATH_TO_CONFIG = os.path.join(os.path.dirname(__file__), "test_alarm.yaml")
    return apconfig.AlarmConfig(PATH_TO_CONFIG)

def test_invalid_config_file_raises_error():
    """Does trying to create an AlarmConfig with a non-existing configuration file
    raise FileNotFoundError?
    """
    with pytest.raises(FileNotFoundError):
        config = apconfig.AlarmConfig("no_such_file.yaml")

def test_validate_on_invalid_brightness(dummy_config):
    """Does validate_config raise AssertionError on invalid brightness?"""
    dummy_config.config["main"]["low_brightness"] = 300
    with pytest.raises(AssertionError):
        dummy_config.validate()

def test_validate_on_too_many_tts(dummy_config):
    """Does validate_config raise AssertionError on multiple enabled TTS engines?"""
    dummy_config.config["TTS"]["GCP"]["enabled"] = True
    dummy_config.config["TTS"]["festival"]["enabled"] = True
    with pytest.raises(AssertionError):
        dummy_config.validate()

def test_read_content_sections(dummy_config):
    """Does get_enabled_sections return enabled 'content' section names?"""
    dummy_config.config["content"]["openweathermap.org"]["enabled"] = True

    assert set(dummy_config.get_enabled_sections("content").keys()) == {"BBC_news", "openweathermap.org"}
