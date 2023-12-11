"""PyQt5 QWidgets for main and settings windows."""


import time
import os.path
import logging
from functools import partial
from collections import namedtuple
from enum import Enum

from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QLCDNumber,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QSizePolicy,
    QDesktopWidget,
    QCheckBox,
    QComboBox,
    QSlider
)
from pyqtspinner import WaitingSpinner

from src import utils


# Create namedtuples for storing button and label configurations
ButtonConfig = namedtuple(
    "ButtonConfig", ["text", "position", "slot", "icon", "size_policy"]
)
ButtonConfig.__new__.__defaults__ = (
    None,
    None,
    None,
    None,
    (QSizePolicy.Preferred, QSizePolicy.Preferred),
)

logger = logging.getLogger("eventLogger")


class AlarmWindow(QWidget):
    """QWidget subclass for main window."""

    def __init__(self):
        super().__init__()
        # setup a dict for tracking control buttons
        self.control_buttons = {}
        self.initUI()

    def initUI(self):
        # Setup base and subgrids for layouting
        base_layout = QGridLayout(self)
        alarm_grid = QVBoxLayout()
        left_grid_container = QVBoxLayout()
        right_grid_container = QVBoxLayout()
        bottom_grid = QHBoxLayout()
        self.setAutoFillBackground(True)

        # Left hand sidebar: subgrids for plugin (trains) and a small loader icon
        loader_indicator_grid = QVBoxLayout()
        loader_indicator = QLabel(self, objectName="loader_indicator")
        self.waiting_spinner = WaitingSpinner(
            loader_indicator,
            roundness=70.0,
            fade=70.0,
            radius=5,
            lines=12,
            line_length=10,
            line_width=5,
            speed=1.0,
            color=(255, 20, 20),
        )
        loader_indicator_grid.addWidget(
            loader_indicator, alignment=Qt.AlignBottom | Qt.AlignLeft
        )

        # Force a minimum width to keep left alignment from covering part of the spinner
        loader_indicator.setMinimumWidth(
            50
        )  

        self.left_plugin_grid = QVBoxLayout()
        left_grid_container.addLayout(self.left_plugin_grid)
        left_grid_container.addLayout(loader_indicator_grid)

        # ** Center grid: current and alarm time displays **
        self.date_label = QLabel(self, objectName="date_label")
        alarm_grid.addWidget(self.date_label, alignment=Qt.AlignHCenter)

        self.clock_lcd = QLCDNumber(8, self)
        self.clock_lcd.setSegmentStyle(QLCDNumber.Flat)
        alarm_grid.addWidget(self.clock_lcd)
        alarm_grid.setStretch(1, 2)

        self.alarm_time_lcd = QLCDNumber(8, self)
        self.alarm_time_lcd.display("")
        self.alarm_time_lcd.setMinimumHeight(30)
        self.alarm_time_lcd.setSegmentStyle(QLCDNumber.Flat)
        alarm_grid.addWidget(self.alarm_time_lcd, alignment=Qt.AlignTop)
        alarm_grid.setStretch(2, 3)

        # ** Bottom grid: main UI control buttons **
        # Note: handlers are defined and set in clock.py
        button_configs = [
            ButtonConfig(text="Settings", icon="settings.png"),
            ButtonConfig(text="Blank", icon="moon64x64.png"),
            ButtonConfig(text="Radio", icon="radio_bw64x64.png"),
            ButtonConfig(text="Close")
        ]

        bottom_grid.setSpacing(0)
        for config in button_configs:
            button = QPushButton(config.text, self)
            button.setSizePolicy(*config.size_policy)
            # store a reference to the button
            self.control_buttons[config.text] = button 

            if config.icon:
                button.setIcon(
                    QIcon(os.path.join(utils.BASE, "resources", "icons", config.icon))
                )
                button.setIconSize(QSize(28, 28))

            bottom_grid.addWidget(button)

        # Right hand sidebar: subgrids for plugin (weather) and a smaller radio play indicator
        radio_station_grid = QGridLayout()
        self.radio_play_indicator = QLabel(self)
        radio_station_grid.addWidget(
            self.radio_play_indicator, 0, 0, Qt.AlignRight | Qt.AlignBottom
        )

        # QGridLayout for setting weather/DHT22 plugin items to fixed rows
        self.right_plugin_grid = (
            QGridLayout()
        ) 
        right_grid_container.addLayout(self.right_plugin_grid)
        right_grid_container.addLayout(radio_station_grid)

        base_layout.addLayout(alarm_grid, 0, 1)
        base_layout.addLayout(left_grid_container, 0, 0)
        base_layout.addLayout(right_grid_container, 0, 2)
        base_layout.addLayout(bottom_grid, 1, 0, 1, 3)

        # Set row strech so the bottom bar doesn't take too much vertical space
        base_layout.setRowStretch(0, 2)
        base_layout.setRowStretch(1, 1)

        self.setLayout(base_layout)
        self.resize(620, 420)
        self.center()

        self.setWindowTitle("Alarmpi")
        self.setup_clock_polling()
        self.show()

    def setup_clock_polling(self):
        """Set the main LCD display to the current time and start polling for
        with 1 second intervals.
        """

        def tick():
            self.clock_lcd.display(time.strftime("%H:%M:%S"))
            self.date_label.setText(time.strftime("%a %d.%m.%Y"))

        tick()  # Call tick once to set the initial time
        _timer = QTimer(self)
        _timer.timeout.connect(tick)
        _timer.start(1000)

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def _show_radio_play_indicator(self, station_name):
        html = "<html><img src='resources/icons/radio64x64.png' height='28'><span style='font-size:14px'> {}</span></html>".format(
            station_name
        )
        self.radio_play_indicator.setText(html)

    def _hide_radio_play_indicator(self):
        self.radio_play_indicator.setText("")


class SettingsWindow(QWidget):
    """Settings window."""

    def __init__(self, config):
        """Args:
            config (apconfig.AlarmConfig): config object for the alarm.
        """
        self.config = config
        super().__init__()
        self.control_buttons = {}
        self.numpad_buttons = {}
        self.initUI()

    def initUI(self):
        base_layout = QGridLayout()

        # subgrids for positioning elements
        left_grid = QGridLayout()
        right_grid = QGridLayout()
        bottom_grid = QHBoxLayout()

        # ** Right grid: numpad for settings the alarm **
        numpad_button_config = [
            ButtonConfig(text="1", position=(0, 0), slot=True),
            ButtonConfig(text="2", position=(0, 1), slot=True),
            ButtonConfig(text="3", position=(0, 2), slot=True),
            ButtonConfig(text="4", position=(1, 0), slot=True),
            ButtonConfig(text="5", position=(1, 1), slot=True),
            ButtonConfig(text="6", position=(1, 2), slot=True),
            ButtonConfig(text="7", position=(2, 0), slot=True),
            ButtonConfig(text="8", position=(2, 1), slot=True),
            ButtonConfig(text="9", position=(2, 2), slot=True),
            ButtonConfig(text="0", position=(3, 1), slot=True),
            ButtonConfig(text="set", position=(4, 0)),
            ButtonConfig(text="clear", position=(4, 2))
        ]

        for config in numpad_button_config:
            button = QPushButton(config.text, self)
            button.setSizePolicy(
                QSizePolicy.Preferred,
                QSizePolicy.Expanding  # buttons should expand in vertical direction
            )
            self.numpad_buttons[config.text] = button

            # Assign a handler to numeric buttons updating the display with that value.
            # Control button handlers are set in clock.py
            if config.slot:
                slot = partial(self.update_input_alarm_display, config.text)
                button.clicked.connect(slot)

            right_grid.addWidget(button, *config.position)

        # Labels for displaying current active alarm time and time
        # set using the numpad controls.
        self.input_alarm_time_label = QLabel(Status.EMPTY.value, self)
        if self.config["main"].get("alarm_time"):
            self.input_alarm_time_label.setText(self.config["main"]["alarm_time"])

        self.input_alarm_time_label.setAlignment(Qt.AlignCenter)
        right_grid.addWidget(self.input_alarm_time_label, 4, 1)

        # ** Bottom level main buttons **
        control_button_config = [
            ButtonConfig(text="Play Now", icon="play64x64.png"),
            ButtonConfig(text="Toggle\nWindow", icon="window64x64.png"),
            ButtonConfig(text="Toggle\nBrightness", icon="brightness64x64.png"),
            ButtonConfig(text="Close", slot=self.clear_labels_and_close)
        ]

        for config in control_button_config:
            button = QPushButton(config.text, self)
            button.setSizePolicy(*config.size_policy)
            self.control_buttons[config.text] = button

            if config.slot:
                button.clicked.connect(config.slot)

            if config.icon:
                button.setIcon(
                    QIcon(os.path.join(utils.BASE, "resources", "icons", config.icon))
                )
                button.setIconSize(QSize(28, 28))

            bottom_grid.addWidget(button)

        # ** Left grid: misc settings **
        self.readaloud_checkbox = QCheckBox("Enable Text-to-Speech alarm", self)
        self.nightmode_checkbox = QCheckBox("Enable Nightmode", self)
        self.alarm_brightness_checkbox = QCheckBox("Full Brightness on alarm", self)

        # ComboBox for radio station, filled from config file
        self.radio_station_combo_box = QComboBox(self)
        self.radio_station_combo_box.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Expanding  # expand in vertical direction
        )

        self.alarm_time_status_label = QLabel(self)

        left_grid.addWidget(self.readaloud_checkbox, 0, 0)
        left_grid.addWidget(self.nightmode_checkbox, 1, 0)
        left_grid.addWidget(self.alarm_brightness_checkbox, 2, 0)

        volume_grid = QGridLayout()
        self.volume_slider = QSlider(Qt.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setFocusPolicy(Qt.NoFocus)
        self.volume_label = QLabel(self)

        volume_grid.addWidget(self.volume_slider, 0, 0)
        volume_grid.addWidget(self.volume_label, 0, 1)
        left_grid.addLayout(volume_grid, 3, 0)
        self.volume_slider.setMaximumWidth(180)
        volume_grid.setHorizontalSpacing(20)

        left_grid.addWidget(self.alarm_time_status_label, 4, 0)
        left_grid.addWidget(self.radio_station_combo_box, 5, 0)

        # Add grids to base layout
        base_layout.addLayout(left_grid, 0, 0)
        base_layout.addLayout(right_grid, 0, 1)
        base_layout.addLayout(bottom_grid, 1, 0, 1, 2)

        # Set stretch factors to rows so the button row doesn't take too much space
        base_layout.setRowStretch(0, 2)
        base_layout.setRowStretch(1, 1)

        self.setLayout(base_layout)
        self.resize(570, 420)
        self.center()

        self.setWindowTitle("Settings")

    def clear_labels_and_close(self):
        """Button callback - close window. Close the settings window and clear any
        temporary status messages."""
        if self.alarm_time_status_label.text() in (
            Status.ERROR.value,
            Status.CLEAR.value,
        ):
            self.alarm_time_status_label.setText("")

        logger.debug("Closing settings window")
        self.hide()

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def update_input_alarm_display(self, val):
        """Button callback - alarm input numpad. Updates the Label displaying
        the time corresponding to the input.
        Args:
            val (string): a single digit string to write as the next character
            to the label.
        """
        # Compute number of digits in the currently displayed value
        current_display_value = self.input_alarm_time_label.text()
        current_display_digits_num = sum(c.isdigit() for c in current_display_value)

        # Alarm time is in HH:MM format. Depending on the length
        # of the currently displayed value either set the next digit or start
        # building a new value from the first digit.
        new_value = list(current_display_value)
        if current_display_digits_num < 2:
            new_value[current_display_digits_num] = val

        elif current_display_digits_num < 4:
            new_value[current_display_digits_num + 1] = val

        else:
            new_value = list(val + Status.EMPTY.value[1:])

        new_value = "".join(new_value)
        self.input_alarm_time_label.setText(new_value)

    def validate_alarm_input(self):
        """Read current value from alarm time label and test it is in %H:%M format."""
        try:
            entry_time = self.input_alarm_time_label.text()
            time.strptime(entry_time, "%H:%M")
            return entry_time
        except ValueError:
            self.alarm_time_status_label.setText(Status.ERROR.value)
            self.input_alarm_time_label.setText(Status.EMPTY.value)
            return

    def clear_alarm(self):
        """Clear the time displayed on the alarm set label."""
        self.input_alarm_time_label.setText(Status.EMPTY.value)
        self.alarm_time_status_label.setText(Status.CLEAR.value)
        self.current_alarm_time = ""

    def set_alarm_input_success_message_with_time(self, time):
        """Helper function for setting the left pane alarm time info label."""
        msg = "Alarm set for {}".format(time)
        self.alarm_time_status_label.setText(msg)

    def set_alarm_input_time_label(self, time):
        """Helper function for setting the numpad label displaying selected time."""
        self.input_alarm_time_label.setText(time)


class Status(Enum):
    """Status messages to show in status label and input time label."""

    ERROR = "<font color='#FF1414'>ERROR: Invalid time</font>"
    CLEAR = "Alarm cleared"
    EMPTY = "  :  "
