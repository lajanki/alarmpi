import pytest
import os.path
import subprocess
import pydub
from unittest.mock import call, patch, Mock

from freezegun import freeze_time

from alarmpi.core import apconfig, alarm_builder, aptts
from alarmpi.handlers import get_handler
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


def test_handler_registry_resolves_stable_ids():
    assert get_handler("tts", "piper") is get_piper_tts.PiperTTSManager
    assert get_handler("tts", "gcp") is get_gcp_tts.GoogleCloudTTS
    assert get_handler("content", "greeting") is get_greeting.Greeting
    assert get_handler("content", "bbc_news") is get_bbc_news.NewsParser
    assert get_handler("content", "weather") is get_weather.WeatherContent


def test_handler_registry_rejects_unknown_ids():
    with pytest.raises(ValueError, match="Unknown tts handler: missing"):
        get_handler("tts", "missing")


def test_content_handler_is_inferred_from_section_name(dummy_alarm_builder):
    class ContentParser:
        def __init__(self, section_data):
            self.section_data = section_data

        def build(self):
            pass

        def get(self):
            return "News content"

    dummy_alarm_builder.config["main"]["TTS"] = None
    dummy_alarm_builder.generate_greeting = Mock(return_value="Good morning")

    with patch(
        "alarmpi.core.alarm_builder.get_handler", return_value=ContentParser
    ) as handler_lookup:
        with patch.object(
            dummy_alarm_builder,
            "_load_beep_audio",
            return_value=pydub.AudioSegment.silent(duration=100),
        ):
            dummy_alarm_builder.build()

    handler_lookup.assert_called_once_with("content", "bbc_news")


def test_no_tts_client_chosen_when_none_set(dummy_alarm_builder):
    dummy_alarm_builder.config["main"]["TTS"] = None

    assert dummy_alarm_builder.get_tts_client() is None


def test_farewell_text_is_appended_to_tts_content(dummy_alarm_builder):
    dummy_alarm_builder.config["content"]["BBC_news"]["enabled"] = False
    dummy_alarm_builder.config["content"]["farewell"] = {
        "enabled": True,
        "text": "That's all for now.",
    }
    dummy_alarm_builder.generate_greeting = Mock(return_value="Good morning")
    dummy_alarm_builder.config["main"]["TTS"] = {"engine": "piper"}
    tts_client = Mock()
    tts_client.setup.return_value = pydub.AudioSegment.silent(duration=100)

    with patch.object(dummy_alarm_builder, "get_tts_client", return_value=tts_client):
        dummy_alarm_builder.build()

    assert tts_client.setup.call_args_list == [
        call("Good morning"),
        call("That's all for now."),
    ]
    assert [name for name, _ in dummy_alarm_builder.audio_segments] == [
        "greeting",
        "farewell",
    ]


def test_config_to_tts_content_pipeline():
    config_path = os.path.join(os.path.dirname(__file__), "test_alarm.yaml")
    config = apconfig.AlarmConfig(config_path)
    config["content"]["BBC_news"]["enabled"] = False
    builder = alarm_builder.AlarmBuilder(config)
    expected_content = (
        "Good morning. It's Thursday January second. The time is 07:02 AM.\n\n\n"
        "Thats all for now. Have a nice day."
    )

    with freeze_time("2025-01-02 10:00:00"):
        with patch(
            "alarmpi.handlers.get_piper_tts.PiperVoice.load"
        ) as load_voice:
            with patch.object(get_piper_tts.PiperTTSManager, "setup") as setup:
                setup.return_value = pydub.AudioSegment.silent(duration=100)
                builder.build()

    load_voice.assert_called_once_with("voices/en_US-lessac-medium.onnx")
    assert isinstance(builder.tts_client, get_piper_tts.PiperTTSManager)
    assert setup.call_args_list == [
        call("Good morning. It's Thursday January second. The time is 07:02 AM.\n\n"),
        call("Thats all for now. Have a nice day."),
    ]
    assert len(builder.audio_segments) == 2
    assert len(builder.audio) > sum(len(audio) for _, audio in builder.audio_segments)


def test_piper_tts_client_chosen(dummy_alarm_builder):
    dummy_alarm_builder.config["main"]["TTS"] = {
        "engine": "piper",
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


def test_tts_stop_handles_process_that_exited_before_terminate():
    process = Mock()
    process.poll.return_value = None
    process.terminate.side_effect = ProcessLookupError
    tts_client = aptts.AlarmpiTTS()
    tts_client._playback_process = process

    tts_client.stop()

    process.terminate.assert_called_once_with()


def test_alarm_builder_stop_stops_tts_client(dummy_alarm_builder):
    dummy_alarm_builder.audio_player = Mock()

    dummy_alarm_builder.stop()

    dummy_alarm_builder.audio_player.stop.assert_called_once_with()


def test_media_play_worker_stop_terminates_its_process():
    worker = alarm_builder.MediaPlayWorker()
    process = Mock()
    process.poll.return_value = None
    worker.process = process

    worker.stop()

    process.terminate.assert_called_once_with()
    process.wait.assert_called_once_with(timeout=1)


def test_correct_content_parser_chosen(dummy_alarm_builder):
    """Are content handler IDs resolved to their expected classes?"""
    handler_map = {
        "bbc_news": get_bbc_news.NewsParser,
        "greeting": get_greeting.Greeting,
        "weather": get_weather.WeatherContent,
    }

    for handler_id, class_ in handler_map.items():
        assert get_handler("content", handler_id) is class_

def test_beep_queued_when_tts_setup_fails(dummy_alarm_builder):
    dummy_alarm_builder.config["content"]["BBC_news"]["enabled"] = False
    dummy_alarm_builder.generate_greeting = Mock(return_value="Good morning")
    beep_audio = pydub.AudioSegment.silent(duration=100)

    with patch.object(dummy_alarm_builder, "get_tts_client", side_effect=RuntimeError):
        with patch.object(
            dummy_alarm_builder, "_load_beep_audio", return_value=beep_audio
        ):
            dummy_alarm_builder.build()

    assert dummy_alarm_builder.audio_segments == [("beep", beep_audio)]


@pytest.mark.parametrize(
    "tts_config", [None, {"enabled": False, "engine": "piper"}, {"enabled": True}]
)
def test_missing_or_disabled_tts_queues_skippable_beep(
    tts_config, dummy_alarm_builder
):
    dummy_alarm_builder.config["main"]["TTS"] = tts_config
    dummy_alarm_builder.config["media"]["enabled"] = False
    beep_audio = pydub.AudioSegment.silent(duration=100)

    with patch.object(dummy_alarm_builder, "_load_beep_audio", return_value=beep_audio):
        dummy_alarm_builder.build()

    assert dummy_alarm_builder.audio_segments == [("beep", beep_audio)]


def test_skip_current_advances_to_next_content_segment(dummy_alarm_builder):
    greeting_audio, news_audio, farewell_audio = object(), object(), object()
    dummy_alarm_builder.audio_segments = [
        ("greeting", greeting_audio),
        ("bbc_news", news_audio),
        ("farewell", farewell_audio),
    ]
    played = []

    def play_segment(audio):
        played.append(audio)
        if audio is news_audio:
            dummy_alarm_builder.skip_current()

    dummy_alarm_builder.audio_player = Mock()
    dummy_alarm_builder.audio_player.play.side_effect = play_segment

    dummy_alarm_builder.play()

    assert played == [greeting_audio, news_audio, farewell_audio]
    dummy_alarm_builder.audio_player.stop.assert_called_once_with()


def test_skip_stops_fallback_beep(dummy_alarm_builder):
    beep_audio = object()
    dummy_alarm_builder.audio_segments = [("beep", beep_audio)]
    dummy_alarm_builder.audio_player = Mock()
    dummy_alarm_builder.audio_player.play.side_effect = (
        lambda audio: dummy_alarm_builder.skip_current()
    )

    dummy_alarm_builder.play()

    dummy_alarm_builder.audio_player.play.assert_called_once_with(beep_audio)
    dummy_alarm_builder.audio_player.stop.assert_called_once_with()


def test_stop_cancels_remaining_content_segments(dummy_alarm_builder):
    dummy_alarm_builder.audio_segments = [
        ("greeting", object()),
        ("bbc_news", object()),
    ]
    dummy_alarm_builder.audio_player = Mock()
    dummy_alarm_builder.audio_player.play.side_effect = (
        lambda audio: dummy_alarm_builder.stop()
    )

    dummy_alarm_builder.play()

    dummy_alarm_builder.audio_player.play.assert_called_once()

def test_alarm_time_override(dummy_alarm_builder):
    """Is alarm time overridden when value specified in config?"""
    dummy_alarm_builder.config["main"]["alarm_time"] = "20:21"
    greeting = dummy_alarm_builder.generate_greeting()
    assert "The time is 08:21" in greeting

def test_alarm_time_without_override(dummy_alarm_builder):
    """Is alarm time current time?"""
    greeting = dummy_alarm_builder.generate_greeting()
    assert "the time is 07:02" in greeting.lower()

def test_greeting_uses_configured_template(dummy_alarm_builder):
    dummy_alarm_builder.config["main"]["alarm_time"] = "07:00"
    dummy_alarm_builder.config["content"]["greeting"]["template"] = (
        "{time_of_day}|{weekday}|{month}|{day_of_month}|{alarm_time}"
    )

    with freeze_time("2025-01-02 10:00:00"):
        greeting = dummy_alarm_builder.generate_greeting()

    assert greeting == "morning|Thursday|January|second|07:00 AM"

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
