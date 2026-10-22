import pytest
import os.path

from unittest.mock import patch

from alarmpi.core import apconfig



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

@pytest.mark.parametrize("startup_volume", [-1, 101, "70", True])
def test_validate_on_invalid_startup_volume(dummy_config, startup_volume):
    dummy_config["alsa"]["startup_volume"] = startup_volume

    with pytest.raises(AssertionError, match="startup_volume must be between 0 and 100"):
        dummy_config.validate()

def test_validate_on_tts_missing_handler(dummy_config):
    """Does validation reject a selected TTS config without a handler?"""
    dummy_config.config["main"]["TTS"] = {"model_path": "voices/voice.onnx"}
    with pytest.raises(AssertionError):
        dummy_config.validate()

def test_validate_on_unknown_tts_handler(dummy_config):
    dummy_config.config["main"]["TTS"]["handler"] = "not_registered"
    with pytest.raises(AssertionError, match="Unknown TTS handler"):
        dummy_config.validate()

def test_validate_on_unknown_content_section(dummy_config):
    dummy_config.config["content"]["not_registered"] = {"enabled": True}
    with pytest.raises(AssertionError, match="registered handler section"):
        dummy_config.validate()

def test_validate_rejects_content_handler_field(dummy_config):
    dummy_config["content"]["greeting"]["handler"] = "greeting"

    with pytest.raises(AssertionError, match="inferred from section name"):
        dummy_config.validate()

def test_read_content_sections(dummy_config):
    """Does get_enabled_sections return enabled 'content' section names?"""
    dummy_config.config["content"]["weather"]["enabled"] = True

    assert set(dummy_config.get_enabled_sections("content").keys()) == {
        "BBC_news",
        "farewell",
        "weather",
    }
