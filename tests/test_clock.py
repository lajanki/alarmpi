import pytest
import os.path
import subprocess
from unittest.mock import patch, Mock, mock_open
from datetime import datetime

from freezegun import freeze_time

from alarmpi.core import clock, apconfig, alarm_builder



PATH_TO_CONFIG = os.path.join(os.path.dirname(__file__), "test_alarm.yaml")


#### Clock


def create_clock():
    """Create a dummy Clock instance using test_alarm.yaml"""
    dummy_clock = clock.Clock(PATH_TO_CONFIG)
    dummy_clock.setup()
    return dummy_clock

@pytest.mark.parametrize(
    "startup_volume,initial_volume,expected_volume",
    [(None, 46, 46), (0, 46, 0), (70, 46, 70)],
)
def test_startup_volume_is_optional_and_slider_matches(
    startup_volume, initial_volume, expected_volume
):
    dummy_clock = clock.Clock(PATH_TO_CONFIG)
    if startup_volume is not None:
        dummy_clock.config["alsa"]["startup_volume"] = startup_volume
    mixer_volume = [initial_volume]

    def read_mixer_volume(card):
        return mixer_volume[0]

    def write_mixer_volume(card, level):
        mixer_volume[0] = level

    with patch(
        "alarmpi.core.clock.utils.get_volume", side_effect=read_mixer_volume
    ):
        with patch(
            "alarmpi.core.clock.utils.set_volume", side_effect=write_mixer_volume
        ) as set_volume:
            dummy_clock.setup()
            assert dummy_clock.settings_window.volume_slider.value() == expected_volume
            if startup_volume is None:
                set_volume.assert_not_called()
            else:
                set_volume.assert_called_once_with(
                    dummy_clock.config["alsa"]["card"], startup_volume
                )
                dummy_clock.restore_volume()
                assert mixer_volume[0] == initial_volume

def test_volume_is_restored_after_startup_override_and_slider_change():
    dummy_clock = clock.Clock(PATH_TO_CONFIG)
    dummy_clock.config["alsa"]["startup_volume"] = 70
    mixer_volume = [46]

    def read_mixer_volume(card):
        return mixer_volume[0]

    def write_mixer_volume(card, level):
        mixer_volume[0] = level

    with patch(
        "alarmpi.core.clock.utils.get_volume", side_effect=read_mixer_volume
    ):
        with patch(
            "alarmpi.core.clock.utils.set_volume", side_effect=write_mixer_volume
        ):
            dummy_clock.setup()
            assert mixer_volume[0] == 70

            dummy_clock.set_volume(85)
            dummy_clock.restore_volume()

    assert mixer_volume[0] == 46
    assert not dummy_clock._volume_changed

def test_tts_checkbox_initializes_and_updates_config():
    dummy_clock = clock.Clock(PATH_TO_CONFIG)
    dummy_clock.config["main"]["TTS"]["enabled"] = False

    with patch("alarmpi.core.clock.utils.get_volume", return_value=46):
        with patch("alarmpi.core.clock.utils.set_volume"):
            dummy_clock.setup()

    assert not dummy_clock.settings_window.tts_checkbox.isChecked()

    dummy_clock.settings_window.tts_checkbox.setChecked(True)

    assert dummy_clock.config["main"]["TTS"]["enabled"] is True

@pytest.fixture(scope="class")
def dummy_clock():
    """Fixture for creating a Clock instance.
    Separate from create_clock to allow overriding the fixture in cases
    where a different configuration is required.
    """
    return create_clock()


class TestClock():
    """Test cases for logic functions for determining alarm time in Clock."""

    @patch("alarmpi.core.GUIWidgets.SettingsWindow.validate_alarm_input")
    @patch("PyQt5.QtWidgets.QLCDNumber.display")
    def test_set_alarm_updates_screen_and_sets_timers(self, mock_display, mock_validate_alarm_input, dummy_clock):
        """Does 'Set alarm' button start timers for alarm build and play and update
        main window and settings window labels?
        """
        mock_validate_alarm_input.return_value = "00:10"  # Mock validating a not-set alarm time
        dummy_clock.settings_window.numpad_buttons["set"].click()

        assert dummy_clock.alarm_timer.isActive()
        assert dummy_clock.alarm_build_timer.isActive()

        mock_display.assert_called_with("00:10")

        settings_window_value = dummy_clock.settings_window.alarm_time_status_label.text()
        assert settings_window_value == "Alarm set for 00:10"

        # Also check get_current_active_alarm returns a value
        active_alarm = dummy_clock.get_current_active_alarm()
        assert active_alarm is not None

    @patch("PyQt5.QtWidgets.QLCDNumber.display")
    def test_clear_alarm_clears_screen_and_stops_timers(self, mock_display, dummy_clock):
        """Does 'Clearm alarm' button stop timers for alarm build and play and clear
        main window and settings window labels?
        """
        dummy_clock.settings_window.numpad_buttons["clear"].click()
        assert not dummy_clock.alarm_timer.isActive()
        assert not dummy_clock.alarm_build_timer.isActive()

        mock_display.assert_called_with("")

        settings_window_value = dummy_clock.settings_window.alarm_time_status_label.text()
        assert settings_window_value == "Alarm cleared"

    @patch("PyQt5.QtWidgets.QLCDNumber.display")
    @patch("alarmpi.utils.rpi_utils.set_display_backlight_brightness")
    def test_play_alarm_starts_alarm_play_thread(self, mock_set_display_backlight_brightness, mock_display, dummy_clock):
        """Does the timer slot function for playing the alarm set window brightness,
        clearn main window label and start the alarm play thread?
        """
        dummy_clock.alarm_play_thread.start = Mock()
        dummy_clock.enable_screen_and_show_control_buttons = Mock()

        dummy_clock.play_alarm()
        mock_display.assert_called_with("")
        mock_set_display_backlight_brightness.assert_called_with(255)
        dummy_clock.alarm_play_thread.start.assert_called()

    @patch("alarmpi.core.clock.Clock.play_radio")
    def test_finish_playing_alarm_starts_radio_if_enabled(self, mock_play_radio, dummy_clock):
        """Does the alarm finish callback call the radio thread when radio is enabled?"""
        dummy_clock.config["radio"]["enabled"] = True
        dummy_clock.main_window.control_buttons["Radio"] = Mock()

        dummy_clock.finish_playing_alarm()
        mock_play_radio.assert_called_with(url="www.example.com")

    def test_settings_window_keeps_previously_set_alarm(self, dummy_clock):
        """Does the settings window input label for set alarm time keep
        its value when the settings window is closed?
        """
        # Mock the actual window display calls
        dummy_clock.settings_window.show = Mock()
        dummy_clock.settings_window.close = Mock()
        dummy_clock.play_radio = Mock()

        dummy_clock.settings_window.set_alarm_input_time_label("07:16")
        dummy_clock.settings_button.click()

        # Test value when settings window is open
        label_time = dummy_clock.settings_window.input_alarm_time_label.text()
        assert label_time == "07:16"

        # Close the window and test the value again
        dummy_clock.settings_window.clear_labels_and_close()
        label_time = dummy_clock.settings_window.input_alarm_time_label.text()
        assert label_time == "07:16"

        # Simulate alarm play finish and test the value again
        dummy_clock.main_window.control_buttons["Radio"] = Mock()
        dummy_clock.finish_playing_alarm()
        label_time = dummy_clock.settings_window.input_alarm_time_label.text()
        assert label_time == "07:16"

    @patch("alarmpi.utils.rpi_utils.set_display_backlight_brightness")
    @patch("alarmpi.utils.rpi_utils._get_value")
    def test_brightness_toggle(self, mock_get_value, mock_set_brightness, dummy_clock):
        """Does the backlight toggle change brightness from low to high?"""
        mock_get_value.return_value = 12

        # Ensure the button is enabled before clicking it
        dummy_clock.settings_window.control_buttons["Toggle\nBrightness"].setEnabled(True)
        dummy_clock.settings_window.control_buttons["Toggle\nBrightness"].click()
        mock_set_brightness.assert_called_with(255)

        # Click again and check value is set back to low
        mock_get_value.return_value = 255
        dummy_clock.settings_window.control_buttons["Toggle\nBrightness"].click()
        mock_set_brightness.assert_called_with(12)

    def test_brightness_buttons_disabled_on_non_writable_configs(self):
        """Are the brightness buttons disabled when the undelying system configurations files
        are not writable?
        """
        # Since we want to intercept the AlarmConfig property rpi_brightness_write_access, create a
        # distinct Clock object separate from the fixture and force the value to False
        # before the button status is checked in setup()
        dummy_clock = create_clock()
        dummy_clock.config.rpi_brightness_write_access = False
        
        assert not dummy_clock.settings_window.control_buttons["Toggle\nBrightness"].isEnabled()
        assert not dummy_clock.main_window.control_buttons["Blank"].isEnabled()

    @pytest.mark.parametrize("time,start_dt,end_dt,is_active", [
        (
            "2021-07-30 09:00",
            datetime(2021, 7, 30, 22, 0),
            datetime(2021, 7, 31, 7, 0),
            False,
        ),
        (
            "2021-07-30 23:20",
            datetime(2021, 7, 30, 22, 0),
            datetime(2021, 7, 31, 7, 0),
            True,
        ),
        (
            "2021-07-30 00:32",
            datetime(2021, 7, 29, 22, 0),
            datetime(2021, 7, 30, 7, 0),
            True,
        ),
    ])
    def test_nighttime_hours(self, time, start_dt, end_dt, is_active):
        """Test nighttime range when Clock is created with different times with respect to
        nighttime start time.
        """
        # Create a new clock instance with the time specified and check nighttime range values
        with freeze_time(time):
            dummy_clock = create_clock()
            assert dummy_clock.config["main"]["nighttime"]["start_dt"] == start_dt
            assert dummy_clock.config["main"]["nighttime"]["end_dt"] == end_dt
            assert dummy_clock._nightmode_active() == is_active

    def test_nightime_update(self):
        """Test nighttime range update: is 1 day added to the range the first time the method is called?"""
        with freeze_time("2021-07-30 09:00"):
            dummy_clock = create_clock()

            # First call to _update_nighttime_range: is range incremented by 1 day?
            dummy_clock._update_nighttime_range()
            dummy_clock.config["main"]["nighttime"]["start_dt"] == datetime(2021, 7, 31, 22, 0)
            dummy_clock.config["main"]["nighttime"]["end_dt"] == datetime(2021, 8, 1, 7, 0)

            # Call again and assert range is not updated
            for _ in range(2):
                dummy_clock._update_nighttime_range()

            dummy_clock.config["main"]["nighttime"]["start_dt"] == datetime(2021, 7, 31, 22, 0)
            dummy_clock.config["main"]["nighttime"]["end_dt"] == datetime(2021, 8, 1, 7, 0)

    @patch("alarmpi.core.alarm_builder.subprocess.run")
    def test_wakeup_song_window(mock_subprocess_run, dummy_clock):
        """Is the media play window displayed when slot function called
        and closed on button press?
        (TODO: This does not test the actually signal being sent/received as 
        it requires a running event loop)
        """
        # Initially hidden
        assert dummy_clock.media_window.isHidden()

        dummy_clock.display_media_window()
        assert dummy_clock.media_window.isVisible()

        # Window should be closed on button press
        dummy_clock.media_window.button.click()
        assert dummy_clock.media_window.isHidden()

    def test_radio_process_exit_resets_radio_ui(self):
        dummy_clock = create_clock()
        process = Mock()
        process.poll.return_value = 1
        dummy_clock.radio.process = process
        radio_button = dummy_clock.main_window.control_buttons["Radio"]
        radio_button.setChecked(True)
        dummy_clock.main_window._show_radio_play_indicator("Radio Suomi")
        dummy_clock.radio_process_timer.start()

        dummy_clock._check_radio_process()

        assert dummy_clock.radio.process is None
        assert not radio_button.isChecked()
        assert dummy_clock.main_window.radio_play_indicator.text() == ""
        assert not dummy_clock.radio_process_timer.isActive()


#### AlarmWorker

class TestAlarmWorker():

    @freeze_time("2021-07-30 21:03")
    @patch("alarmpi.core.clock.AlarmWorker._play")
    def test_build_and_play_alarm_time_override(self, mock_play, capsys):
        """Does build_and_play task type temporarily override alarm_time in config
        with current time?
        """
        config = apconfig.AlarmConfig(PATH_TO_CONFIG)
        builder = alarm_builder.AlarmBuilder(config)
        builder.get_tts_client = Mock()

        worker = clock.AlarmWorker(builder, task="build_and_play")
        worker.run()
        assert builder.config["main"]["alarm_time"] == "07:02"

        # Check the overriden time is present in the output generated by the alarm build
        captured = capsys.readouterr()
        assert "09:03" in captured.out

    def test_build_and_play_signals_emit_when_steps_fail(self):
        config = apconfig.AlarmConfig(PATH_TO_CONFIG)
        builder = alarm_builder.AlarmBuilder(config)
        worker = clock.AlarmWorker(builder, task="build_and_play")
        worker._build = Mock(side_effect=RuntimeError("synthesis failed"))
        worker._play = Mock(side_effect=RuntimeError("beep failed"))
        build_finished = Mock()
        play_finished = Mock()
        worker.build_finished_signal.connect(build_finished)
        worker.play_finished_signal.connect(play_finished)
        original_alarm_time = config["main"]["alarm_time"]

        worker.run()

        assert config["main"]["alarm_time"] == original_alarm_time
        build_finished.assert_called_once_with(1)
        play_finished.assert_called_once_with(1)


#### RadioStreamer

@pytest.fixture
def dummy_radio():
    radio_args = {"args": "-playlist url", "url": ""}
    return clock.RadioStreamer(radio_args)

class TestRadioStreamer():
    """Test cases for RadioStreamer: does streaming radio work correctly?"""

    def test_radio_not_playing_on_empty_process(self, dummy_radio):
        """Does is_playing return False when the active process flag is not set?"""
        dummy_radio.process = None
        assert not dummy_radio.is_playing()

    def test_radio_is_playing_on_non_empty_process(self, dummy_radio):
        """Does is_playing return True when an active process flag is set?"""
        dummy_radio.process = True
        assert dummy_radio.is_playing()

    def test_stop_clears_active_process(self, dummy_radio):
        """Does stop clear the list of running processes?"""
        process = Mock(stdout=iter(()))
        with patch("builtins.open", mock_open()):
            with patch(
                "alarmpi.core.clock.subprocess.Popen", return_value=process
            ):
                dummy_radio.play("https://foo.bar")
                dummy_radio.output_thread.join(timeout=1)
                dummy_radio.stop()

        assert dummy_radio.process is None

    def test_stream_input_error_terminates_vlc(self, dummy_radio):
        process = Mock(
            stdout=iter(
                [
                    "[access] access stream error: HTTP 404 error\n",
                    "[main] Your input can't be opened\n",
                ]
            )
        )

        with patch("builtins.open", mock_open()):
            dummy_radio._monitor_output(process)

        process.terminate.assert_called_once_with()

    def test_stop_handles_process_that_already_exited(self, dummy_radio):
        process = Mock()
        process.terminate.side_effect = ProcessLookupError
        dummy_radio.process = process

        dummy_radio.stop()

        process.terminate.assert_called_once_with()
        assert dummy_radio.process is None
