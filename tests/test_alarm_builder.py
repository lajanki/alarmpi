import pytest
import os.path
import subprocess
import pydub
from unittest.mock import patch, Mock

from freezegun import freeze_time

from alarmpi.core import apconfig, alarm_builder, aptts
from alarmpi.handlers import (
    get_bbc_news,
    get_gcp_tts,
    get_piper_tts,
    get_greeting,
    get_weather
)


@pytest.fixture
def dummy_alarm_builder():
    """Create an AlarmBuilder from the config file."""
    PATH_TO_CONFIG = os.path.join(os.path.dirname(__file__), "test_alarm.yaml")
    config = apconfig.AlarmConfig(PATH_TO_CONFIG)
    return alarm_builder.AlarmBuilder(config)

def test_no_tts_client_chosen_when_none_set(dummy_alarm_builder):
    dummy_alarm_builder.config["main"]["TTS"] = None

    assert dummy_alarm_builder.get_tts_client() is None


def test_piper_tts_client_chosen(dummy_alarm_builder):
    dummy_alarm_builder.config["main"]["TTS"] = {
        "handler": "get_piper_tts.py",
        "model_path": "voices/en_US-lessac-medium.onnx",
    }

    with patch(
        "alarmpi.handlers.get_piper_tts.PiperVoice.load"
    ) as load_voice:
        client = dummy_alarm_builder.get_tts_client()

    load_voice.assert_called_once_with("voices/en_US-lessac-medium.onnx")
    assert isinstance(client, get_piper_tts.PiperTTSManager)


def test_piper_tts_setup_returns_audio_segment():
    voice = Mock()

    def synthesize_wav(text, wav_file):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x00" * 100)

    voice.synthesize_wav.side_effect = synthesize_wav
    with patch(
        "alarmpi.handlers.get_piper_tts.PiperVoice.load", return_value=voice
    ):
        client = get_piper_tts.PiperTTSManager(
            config={"model_path": "voices/en_US-lessac-medium.onnx"}
        )

    audio = client.setup("Hello")

    assert isinstance(audio, pydub.AudioSegment)
    assert len(audio) > 0


def test_tts_play_uses_managed_ffplay_process():
    audio = Mock()
    process = Mock()
    process.wait.return_value = 0

    with patch(
        "alarmpi.core.aptts.pydub.playback.get_player_name", return_value="ffplay"
    ):
        with patch(
            "alarmpi.core.aptts.subprocess.Popen", return_value=process
        ) as popen:
            aptts.AlarmpiTTS().play(audio)

    audio.export.assert_called_once()
    assert popen.call_args.args[0][:4] == [
        "ffplay",
        "-nodisp",
        "-autoexit",
        "-hide_banner",
    ]
    process.wait.assert_called_once_with()


def test_tts_play_raises_on_player_failure():
    audio = Mock()
    process = Mock()
    process.wait.return_value = 1

    with patch(
        "alarmpi.core.aptts.pydub.playback.get_player_name", return_value="ffplay"
    ):
        with patch("alarmpi.core.aptts.subprocess.Popen", return_value=process):
            with pytest.raises(subprocess.CalledProcessError):
                aptts.AlarmpiTTS().play(audio)


def test_tts_stop_terminates_active_ffplay_process():
    process = Mock()
    process.poll.return_value = None
    tts_client = aptts.AlarmpiTTS()
    tts_client._playback_process = process

    tts_client.stop()

    process.terminate.assert_called_once_with()
    process.wait.assert_called_once_with(timeout=1)


def test_alarm_builder_stop_stops_tts_client(dummy_alarm_builder):
    dummy_alarm_builder.tts_client = Mock()

    dummy_alarm_builder.stop()

    dummy_alarm_builder.tts_client.stop.assert_called_once_with()


def test_correct_content_parser_chosen(dummy_alarm_builder):
    """Given a content section, is the correct class chosen in get_content_parser_class?"""
    handler_map = {
        "get_bbc_news.py": get_bbc_news.NewsParser,
        "get_gcp_tts.py": get_gcp_tts.GoogleCloudTTS,
        "get_piper_tts.py": get_piper_tts.PiperTTSManager,
        "get_greeting.py":  get_greeting.Greeting,
        "get_weather.py": get_weather.WeatherContent
    }

    for module, class_ in handler_map.items():
        created_class = dummy_alarm_builder.get_content_parser_class({"handler": module})
        assert created_class == class_

@patch("alarmpi.core.alarm_builder.AlarmBuilder.play_beep")
def test_beep_played_when_tts_fails(mock_play_beep, dummy_alarm_builder):
    """Is the beep played when TTS playback fails?"""
    dummy_alarm_builder.tts_client = Mock()
    dummy_alarm_builder.tts_client.play.side_effect = RuntimeError("player failed")
    dummy_alarm_builder.audio = Mock()

    dummy_alarm_builder.play()
    mock_play_beep.assert_called()


@patch("alarmpi.core.alarm_builder.AlarmBuilder.play_beep")
def test_beep_played_when_tts_setup_fails(mock_play_beep, dummy_alarm_builder):
    dummy_alarm_builder.config["content"]["BBC_news"]["enabled"] = False
    dummy_alarm_builder.generate_greeting = Mock(return_value="Good morning")

    with patch.object(dummy_alarm_builder, "get_tts_client", side_effect=RuntimeError):
        dummy_alarm_builder.build()
    dummy_alarm_builder.play()

    mock_play_beep.assert_called_once()


@patch("alarmpi.core.alarm_builder.AlarmBuilder.play_beep")
def test_beep_played_when_no_tts_engine_is_enabled(
    mock_play_beep, dummy_alarm_builder
):
    dummy_alarm_builder.config["content"]["BBC_news"]["enabled"] = False
    dummy_alarm_builder.generate_greeting = Mock(return_value="Good morning")
    dummy_alarm_builder.config["main"]["TTS"] = None

    dummy_alarm_builder.build()
    dummy_alarm_builder.play()

    mock_play_beep.assert_called_once()

@patch("alarmpi.core.alarm_builder.AlarmBuilder.play_beep")
def test_beep_played_when_no_engine_or_wakeup_track_enabled(
    mock_play_beep, dummy_alarm_builder
):
    dummy_alarm_builder.config["main"]["TTS"] = None
    dummy_alarm_builder.config["media"]["enabled"] = False

    dummy_alarm_builder.play()
    mock_play_beep.assert_called()


def test_no_beep_when_no_engine_but_wakeup_track_enabled(dummy_alarm_builder):
    dummy_alarm_builder.config["main"]["TTS"] = None
    dummy_alarm_builder.config["media"]["enabled"] = True

    with patch.object(dummy_alarm_builder.media_play_thread, "start") as start:
        with patch.object(dummy_alarm_builder.media_play_thread, "wait"):
            with patch.object(dummy_alarm_builder.media_play_thread, "stop"):
                with patch(
                    "alarmpi.core.alarm_builder.AlarmBuilder.play_beep"
                ) as play_beep:
                    dummy_alarm_builder.play()

    start.assert_called_once()
    play_beep.assert_not_called()

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
    builder.config["main"]["TTS"] = None
    builder.config["media"]["enabled"] = True

    builder.play()
    builder.media_play_thread.start.assert_called()
