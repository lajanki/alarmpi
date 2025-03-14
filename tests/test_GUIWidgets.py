import os.path
import pytest

from alarmpi.core import apconfig, GUIWidgets


@pytest.fixture
def settings_window():
    PATH_TO_CONFIG = os.path.join(os.path.dirname(__file__), "test_alarm.yaml")
    config = apconfig.AlarmConfig(PATH_TO_CONFIG)
    return GUIWidgets.SettingsWindow(config)


def test_hour_update_alarm_display_time(settings_window):
    """Does update_input_alarm_display write the correct time value to the
    settings window's set alarm time label?
    """
    # pytest.mark.parametrize doesn't seem to preserve order, use manual
    # asserts instead

    # Manually empty the label and add the first digit
    settings_window.input_alarm_time_label.setText(GUIWidgets.Status.EMPTY.value)
    settings_window.update_input_alarm_display("0")
    assert settings_window.input_alarm_time_label.text() == "0 :  "

    settings_window.update_input_alarm_display("7")
    assert settings_window.input_alarm_time_label.text() == "07:  "

    settings_window.update_input_alarm_display("1")
    assert settings_window.input_alarm_time_label.text() == "07:1 "

    settings_window.update_input_alarm_display("8")
    assert settings_window.input_alarm_time_label.text() == "07:18"

    # 5th call should start from the beginning
    settings_window.update_input_alarm_display("1")
    assert settings_window.input_alarm_time_label.text() == "1 :  "

def test_validate_alarm_input_rejects_invalid_input(settings_window):
    """Does validate_alarm_input reject invalid input format and set user
    information labels accordingly?
    """
    # set the label to an invalid value and call the method
    settings_window.input_alarm_time_label.setText("25:01")
    settings_window.validate_alarm_input()

    # check labels contain expected error values
    alarm_time_value = settings_window.input_alarm_time_label.text()

    assert "ERROR: Invalid time" in settings_window.alarm_time_status_label.text()
    assert alarm_time_value == "  :  "

def test_validate_alarm_input_returns_valid_input(settings_window):
    """Does validate_alarm_input accept valid input?"""
    # set the label to an invalid value and call the method
    settings_window.input_alarm_time_label.setText("16:34")
    assert settings_window.validate_alarm_input() == "16:34"


def test_clear_alarm_changes_current_alarm_time(settings_window):
    """Does clear_alarm process the correct cleanup tasks:
        * set user information labels
        * set active alarm time to empty string
    """
    settings_window.clear_alarm()
    assert settings_window.input_alarm_time_label.text() == "  :  "
    assert settings_window.alarm_time_status_label.text() == "Alarm cleared"
    assert settings_window.current_alarm_time == ""

