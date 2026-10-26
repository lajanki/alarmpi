import pytest
import os.path

from unittest.mock import patch

from alarmpi.core import apconfig
from alarmpi.core.apconfig import ConfigValidationError


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
    """Does validate_config raise ConfigValidationError on invalid brightness?"""
    dummy_config.config["main"]["low_brightness"] = 300
    with pytest.raises(ConfigValidationError):
        dummy_config.validate()

def test_constructor_reports_config_path(tmp_path):
    """Is the failure reported once, with the file path and no chained cause?"""
    import yaml
    path = os.path.join(os.path.dirname(__file__), "test_alarm.yaml")
    with open(path) as f:
        data = yaml.safe_load(f)
    data["main"]["low_brightness"] = 300
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(data))

    with pytest.raises(ConfigValidationError, match="bad.yaml.*Brightness") as exc:
        apconfig.AlarmConfig(str(bad))
    assert exc.value.__cause__ is None

def test_constructor_reports_missing_key(tmp_path):
    import yaml
    path = os.path.join(os.path.dirname(__file__), "test_alarm.yaml")
    with open(path) as f:
        data = yaml.safe_load(f)
    del data["main"]["low_brightness"]
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(data))

    with pytest.raises(ConfigValidationError, match="missing key"):
        apconfig.AlarmConfig(str(bad))

def test_validate_on_gcp_credentials_failure(dummy_config):
    dummy_config.config["main"]["TTS"]["engine"] = "gcp"
    with patch("google.auth.default", side_effect=Exception("no creds")):
        with pytest.raises(ConfigValidationError, match="unable to load credentials"):
            dummy_config.validate()

@pytest.mark.parametrize("startup_volume", [-1, 101, "70", True])
def test_validate_on_invalid_startup_volume(dummy_config, startup_volume):
    dummy_config["alsa"]["startup_volume"] = startup_volume

    with pytest.raises(ConfigValidationError, match="startup_volume must be between 0 and 100"):
        dummy_config.validate()

def test_validate_on_tts_missing_engine(dummy_config):
    """Does validation allow TTS with no selected engine?"""
    dummy_config.config["main"]["TTS"] = {"enabled": True}

    assert dummy_config.validate()

def test_validate_on_unknown_tts_engine(dummy_config):
    dummy_config.config["main"]["TTS"]["engine"] = "not_registered"
    with pytest.raises(ConfigValidationError, match="Unknown TTS engine"):
        dummy_config.validate()

def test_validate_on_unknown_content_section(dummy_config):
    dummy_config.config["content"]["not_registered"] = {"enabled": True}
    with pytest.raises(ConfigValidationError, match="registered handler section"):
        dummy_config.validate()

def test_read_content_sections(dummy_config):
    """Does get_enabled_sections return enabled 'content' section names?"""
    dummy_config.config["content"]["weather"]["enabled"] = True

    assert set(dummy_config.get_enabled_sections("content").keys()) == {
        "BBC_news",
        "farewell",
        "weather",
    }
