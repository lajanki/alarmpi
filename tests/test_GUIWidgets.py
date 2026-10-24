import os.path
import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from alarmpi.core import apconfig, GUIWidgets


def test_alarm_window_is_visible_on_creation():
    window = GUIWidgets.AlarmWindow()

    assert window.isVisible()

    window.close()


def test_skip_area_icon_and_pressed_feedback_preserve_display_geometry():
    window = GUIWidgets.AlarmWindow()
    taps = []
    window.central_tapped.connect(lambda: taps.append(True))
    try:
        QApplication.processEvents()
        clock_geometry = window.clock_lcd.geometry()
        window.show_skip_area()
        QApplication.processEvents()
        assert window.skip_outline.objectName() == "skip_area"
        assert window.skip_outline.styleSheet() == ""
        assert not window.skip_icon.pixmap().isNull()
        assert window.skip_icon.isVisible()
        assert window.skip_icon.geometry().center().x() > window.skip_outline.width() / 2
        assert window.skip_icon.geometry().center().y() > window.skip_outline.height() / 2

        QTest.mousePress(window.clock_lcd, Qt.LeftButton)
        assert window.skip_outline.property("pressed") is True
        QTest.mouseRelease(window.clock_lcd, Qt.LeftButton)
        assert window.skip_outline.property("pressed") is False
        assert taps == [True]
        assert window.clock_lcd.geometry() == clock_geometry

        window.resize(800, 480)
        QApplication.processEvents()
        assert window.skip_outline.geometry() == window.alarm_grid.geometry()
        assert window.skip_outline.rect().contains(window.skip_icon.geometry())
        window.hide_skip_area()
        assert not window.skip_icon.isVisible()
    finally:
        window.close()


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

