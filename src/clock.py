#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""A PyQt5 clock radio application."""


import time
import datetime
import os
import sys
import subprocess
import logging
import json
from functools import partial

from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPixmap

from src import alarmenv
from src import utils
from src import alarm_builder
from src import GUIWidgets
from src import rpi_utils
from src.handlers import get_open_weather, get_next_trains



logger = logging.getLogger("eventLogger")


class Clock:
    """Wrapper class for the clock itself. Defines interactions between
    UI elements and backend logic.
    """

    def __init__(self, config_file, **kwargs):
        """Setup GUI windows and various configuration objects.
        params
            config_file (str): name (not path!) of the configuration file in /configs to use.
            kwargs (dict): additional command line paramters passed from main.py
        """
        self.main_window = GUIWidgets.AlarmWindow()
        self.settings_window = GUIWidgets.SettingsWindow()

        # Read the alarm configuration file and initialize and alarmenv object
        self.config_file = config_file
        self.env = alarmenv.AlarmEnv(config_file)
        self.env.setup()

        # Setup a QThread and QTimers for building and playing the alarm
        self.alarm_play_thread = AlarmPlayThread(self.env)
        self.alarm_play_thread.signal.connect(self.finish_playing_alarm)

        self.alarm_timer = QTimer(self.main_window)
        self.alarm_timer.setSingleShot(True)
        self.alarm_timer.timeout.connect(self.play_alarm)

        self.alarm_build_timer = QTimer(self.main_window)
        self.alarm_build_timer.setSingleShot(True)
        self.alarm_build_timer.timeout.connect(self.alarm_play_thread.build)

        radio_conf = self.env.get_section("radio")
        self.radio = RadioStreamer(radio_conf)
        self.alarm_player = alarm_builder.Alarm(self.env)
        self.train_parser = get_next_trains.TrainParser()

        if self.env.get_value("openweathermap", "enabled", fallback="0") == "1":
            section = self.env.get_section("openweathermap")
            self.weather_parser = get_open_weather.OpenWeatherMapClient(section)

        if kwargs.get("fullscreen"):
            self.main_window.showFullScreen()
            self.main_window.setCursor(Qt.BlankCursor)
            self.settings_window.setCursor(Qt.BlankCursor)

        if kwargs.get("debug"):
            self.env.is_rpi = True  # fake Rpi environment so all buttons are enabled
            logger.debug("Debug mode detected, disabling train and weather polling")
            self.env.config.set("polling", "weather", "0")
            self.env.config.set("polling", "train", "0")
            self.main_window.keyPressEvent = self.debug_key_press_event

    def setup(self):
        """Setup various button handlers as well as weather and train data polling
        for the main windows side bar.
        """
        self.setup_button_handlers()

        weather_enabled = self.env.get_value("openweathermap", "enabled") == "1"
        weather_polling_enabled = self.env.get_value("polling", "weather", fallback=False) == "1"

        train_polling_enabled = self.env.get_value("polling", "train", fallback=False) == "1"

        if weather_enabled and weather_polling_enabled:
            self.setup_weather_polling()

        if train_polling_enabled:
            self.setup_train_polling()

        # Setup settings window's checkbox initial values:
        tts_enabled = self.env.config_has_match("main", "readaloud", "1")
        self.settings_window.readaloud_checkbox.setChecked(tts_enabled)

        # set nightmode as enabled if non zero offset specified in the config
        self.original_nightmode_offset = self.env.get_value(
            "alarm", "nightmode_offset", fallback="8")

        nightmode = (self.original_nightmode_offset != "0")
        self.settings_window.nightmode_checkbox.setChecked(nightmode)

        alarm_brightness_enabled = self.env.config_has_match("alarm", "set_brightness", "1")
        self.settings_window.alarm_brightness_checkbox.setChecked(alarm_brightness_enabled)

        # Set main window's alarm time display to currently active alarm time
        alarm_time = self.get_current_active_alarm()
        if alarm_time:
            self.main_window.alarm_time_lcd.display(alarm_time)

        self.screen_blank_timer = QTimer(self.main_window)
        self.screen_blank_timer.setSingleShot(True)
        self.screen_blank_timer.timeout.connect(self.blank_screen_and_hide_control_buttons)

        self.main_window.mouseReleaseEvent = self.on_release_event_handler

    def setup_button_handlers(self):
        """Setup button handlers for the main window and settings window."""
        # Setup references to main control buttons in both windows
        self.settings_button = self.main_window.control_buttons["Settings"]
        self.radio_button = self.main_window.control_buttons["Radio"]
        self.blank_button = self.main_window.control_buttons["Blank"]
        self.close_button = self.main_window.control_buttons["Close"]

        self.alarm_play_button = self.settings_window.control_buttons[0]
        window_button = self.settings_window.control_buttons[1]
        brightness_button = self.settings_window.control_buttons[2]

        alarm_set_button = self.settings_window.numpad_buttons["set"]
        alarm_clear_button = self.settings_window.numpad_buttons["clear"]

        # Disable blank and brightness buttons if host system is not a Raspberry Pi
        if not self.env.is_rpi:
            self.blank_button.setEnabled(False)
            brightness_button.setEnabled(False)

        # Set button handlers for buttons requiring interactions between helper classes
        # ** main window buttons **
        self.settings_button.clicked.connect(self.open_settings_window)

        # Set the radio button as an on/off toggle
        self.radio_button.setCheckable(True)
        radio_play_slot = partial(self.play_radio, url=None)
        self.radio_button.clicked.connect(radio_play_slot)

        self.blank_button.clicked.connect(self.blank_screen_and_hide_control_buttons)
        self.close_button.clicked.connect(self.cleanup_and_exit)

        # ** settings window buttons **
        brightness_button.clicked.connect(rpi_utils.toggle_display_backlight_brightness)
        self.alarm_play_button.clicked.connect(self.play_alarm)
        window_button.clicked.connect(self.toggle_display_mode)

        alarm_set_button.clicked.connect(self.set_alarm)
        alarm_clear_button.clicked.connect(self.clear_alarm)

        # Settings window checkbox callbacks
        self.settings_window.readaloud_checkbox.stateChanged.connect(self.enable_tts)
        self.settings_window.nightmode_checkbox.stateChanged.connect(self.enable_nightmode)
        self.settings_window.alarm_brightness_checkbox.stateChanged.connect(
            self.enable_alarm_brightness_change)

    def open_settings_window(self):
        """Callback for opening the settings window: clear screen blanking timer (if active)
        and dislpay the window.
        """
        self.screen_blank_timer.stop()
        self.settings_window.show()

    def on_release_event_handler(self, event):
        """Event handler for touching the screen: ensure screen is turned on
        and if an active alarm is set and it is currently nighttime,
        set a short timeout for blanking the screen.
        """
        # get screen state before the event occured and set it as enabled
        old_screen_state = rpi_utils.get_and_set_screen_state("on")
        self.show_control_buttons()

        alarm_time = self.get_current_active_alarm()  # HH:MM
        if alarm_time is None:
            return

        # set screen blanking timeout if the screen was blank before the event
        # and it is currently nightime.
        offset = int(self.env.get_value("alarm", "nightmode_offset", fallback="0"))
        if old_screen_state == "off" and utils.nighttime(alarm_time, offset):
            logger.info("Screen blank timer activated")
            self.screen_blank_timer.start(3*1000)  # 3 second timer

    def set_alarm(self):
        """Callback to 'Set alarm' button: starts timers for alarm build and play
        and updates main and settings window labels.
        """
        time_str = self.settings_window.validate_alarm_input()
        if time_str:
            # Update displayed alarm time settings and main window
            self.main_window.alarm_time_lcd.display(time_str)
            self.settings_window.set_alarm_input_success_message_with_time(time_str)

            # Set alarm play timer
            self.alarm_dt = utils.time_str_to_dt(time_str)
            now = datetime.datetime.now()
            alarm_wait_ms = (self.alarm_dt - now).seconds * 1000

            logger.info("Setting alarm for %s", time_str)
            self.alarm_timer.start(alarm_wait_ms)

            # Setup alarm build time for 5 minutes earlier (given large enough timer)
            ALARM_BUILD_DELTA = 5 * 60 * 1000
            alarm_build_wait_ms = max((0, alarm_wait_ms - ALARM_BUILD_DELTA)) # 0 if not enough time

            alarm_build_dt = self.alarm_dt - datetime.timedelta(minutes=5)
            logger.info("Setting alarm build for %s", alarm_build_dt.strftime("%H:%M"))
            self.alarm_build_timer.start(alarm_build_wait_ms)

            # Set screen brightness to low
            if self.env.config_has_match("alarm", "set_brightness", "1"):
                rpi_utils.set_display_backlight_brightness(rpi_utils.LOW_BRIGHTNESS)

    def clear_alarm(self):
        """Handler for settings window's 'clear' button. Stops any running
        alarm timers. Also clears both window's alarm displays.
        """
        self.alarm_timer.stop()
        self.alarm_build_timer.stop()
        logger.info("Alarm cleared")
        self.settings_window.clear_alarm()
        self.main_window.alarm_time_lcd.display("")

    def get_current_active_alarm(self):
        """Check for existing running alarm timers and return alarm time in HH:MM format."""
        active = self.alarm_timer.isActive()
        if active:
            return self.alarm_dt.strftime("%H:%M")

    def play_radio(self, url=None):
        """Callback to the 'Play radio' button: open or close the radio stream
        depending on the button state.
        Args:
            url (string): the url of the stream to play. If none, currently active
                stream from the settings window ComboBox is used.
        """
        button = self.main_window.control_buttons["Radio"]
        
        # If no stream url was passed, use currently active station from settings window
        # dropdown list.
        if url is None:
            current_radio_station = self.settings_window.radio_station_combo_box.currentText()
            self.radio.config["url"] = utils.RADIO_STATIONS[current_radio_station]

        else:
            self.radio.config["url"] = url
            # Look for station name from listed streams in stream config file
            current_radio_station = ""
            
            for k,v in utils.RADIO_STATIONS.items():
                if v == url:
                    current_radio_station = k
                    break
 
            
        # The radio button is a checkable (ie. a toggle): radio should start playing 
        # when the button gets checked and stop when state changes to not checked.
        # (The state change occurs before this callback runs.)
        if button.isChecked():
            self.main_window._show_radio_play_indicator(current_radio_station)
            self.radio.play()
        else:
            self.main_window._hide_radio_play_indicator()
            self.radio.stop()

    def play_alarm(self):
        """Callback to playing the alarm: runs the alarm play thread. Called when
        on alarm timeout signal and on 'Play now' button.
        """
        # Update main display
        self.main_window.alarm_time_lcd.display("")
        self.enable_screen_and_show_control_buttons()
        rpi_utils.set_display_backlight_brightness(rpi_utils.HIGH_BRIGHTNESS)

         # Clear 'Alarm set for ...' label in the settings window
        self.settings_window.alarm_time_status_label.setText("")

        self.alarm_play_thread.start()

    def finish_playing_alarm(self):
        """Slot function for finishing playing the alarm: re-enables the play button
        and, if activated, starts a separated mplayer process for the radio stream.
        Called when the alarm thread emits its finished signal.
        """
        self.alarm_play_button.setEnabled(True)

        if self.env.config_has_match("radio", "enabled", "1"):
            # Manually emit the radio buttons click signal. This will both
            # set the state of the button and start the playback.
            #self.main_window.control_buttons["Radio"].click()

            # Toggle the radio button and specify the stream to play as
            # the url parameter from the configuration file.
            # Note: we're assuming the button is untoggled before the call.
            self.main_window.control_buttons["Radio"].toggle()
            url = self.env.get_value("radio", "url")
            self.play_radio(url=url)

    def build_and_play_alarm(self):
        """Custom callback for the 'Play now' button: builds and plays an alarm."""
        self.alarm_play_thread.build() # Note: a new alarm is built every time the button is pressed
        self.alarm_play_thread.start()

    def setup_weather_polling(self):
        """Setup polling for updating the weather every 30 minutes."""
        self.update_weather()
        _timer = QTimer(self.main_window)
        _timer.timeout.connect(self.update_weather)
        _timer.start(30*60*1000)  # 30 minute interval

    def update_weather(self):
        """Update the weather labels on the main window. Makes an API request to
        openweathermap.org for current temperature and windspeed.
        """
        logger.debug("Updating weather")
        weather = self.weather_parser.fetch_and_format_weather()

        if weather is None:
            self.main_window.temperature_label.setText("ERR")
            self.main_window.wind_speed_label.setText("ERR")
            return

        temperature = weather["temp"]
        wind = weather["wind_speed_ms"]

        msg = "{}°C".format(round(temperature))
        self.main_window.temperature_label.setText(msg)

        msg = "{}m/s".format(round(wind))
        self.main_window.wind_speed_label.setText(msg)

        icon_id = weather["icon"]
        icon_binary = get_open_weather.OpenWeatherMapClient.get_weather_icon(icon_id)

        pixmap = QPixmap()
        pixmap.loadFromData(icon_binary)
        self.main_window.weather_container.setPixmap(pixmap)

    def setup_train_polling(self):
        """Setup polling for next train departure times every 12 minutes."""
        self.update_trains()
        _timer = QTimer(self.main_window)
        _timer.timeout.connect(self.update_trains)
        _timer.start(5*60*1000)

    def update_trains(self):
        """Fetch new train data from DigiTraffic API and display on the right sidebar."""
        logger.debug("Updating trains")
        trains = self.train_parser.run()

        if trains is None:
            for label in self.main_window.train_labels:
                label.setText("ERR")
            return

        for train, label in zip(trains, self.main_window.train_labels):
            line_id = train["commuterLineID"]
            scheduled_time = train["scheduledTime"].strftime("%H:%M")

            # If an estimate exists, display both values
            if train["liveEstimateTime"]:
                estimate_time = train["liveEstimateTime"].strftime("%H:%M")
                msg = "{} {} => {}".format(line_id, scheduled_time, estimate_time)

            else:
                msg = "{} {}".format(line_id, scheduled_time)

            if train["cancelled"]:
                msg = "{} {} CANCELLED".format(line_id, scheduled_time)

            label.setText(msg)

    def toggle_display_mode(self):
        """Change main window dispaly mode between fullscreen and normal
        depending on current its mode.
        """
        if self.main_window.windowState() == Qt.WindowFullScreen:
            self.main_window.showNormal()
        else:
            self.main_window.showFullScreen()
            # Keep the settings window active to prevent main window from
            # burying it
            self.settings_window.activateWindow()

    def blank_screen_and_hide_control_buttons(self):
        """Callback to turning the screen off: turn off backlight power and
        hide the main window's control buttons to prevent accidentally hitting
        them when the screen in blank.
        """
        rpi_utils.toggle_screen_state("off")
        self.hide_control_buttons()

    def enable_screen_and_show_control_buttons(self):
        """Callback to turning the screen on: re-enable backlight power and show
        the main window's control buttons.
        """
        rpi_utils.toggle_screen_state("on")
        self.show_control_buttons()

    def hide_control_buttons(self):
        """Hides the main window's bottom row buttons."""
        self.settings_button.hide()
        self.radio_button.hide()
        self.blank_button.hide()
        self.close_button.hide()

    def show_control_buttons(self):
        """Showes the main window's bottom row buttons."""
        self.settings_button.show()
        self.radio_button.show()
        self.blank_button.show()
        self.close_button.show()

    def enable_tts(self):
        """Callback to the checkbox enabling TTS feature: set the config
        to match the selected value.
        """
        state = "0"
        if self.settings_window.readaloud_checkbox.isChecked():
            state = "1"
        self.env.config.set("main", "readaloud", state)

    def enable_nightmode(self):
        """Callback to the checkbox enabling TTS feature: set the config
        to match the selected value.
        """
        state = "0"
        if self.settings_window.nightmode_checkbox.isChecked():
            state = self.original_nightmode_offset
        self.env.config.set("alarm", "nightmode_offset", state)

    def enable_alarm_brightness_change(self):
        """Callback to the checkbox enabling brightness change on alarm: set the config
        to match the selected value.
        """
        state = "0"
        if self.settings_window.alarm_brightness_checkbox.isChecked():
            state = "1"
        self.env.config.set("alarm", "set_brightness", state)

    def cleanup_and_exit(self):
        """Callback to the close button. Close any existing radio streams and the
        application itself.
        """
        self.radio.stop()
        QApplication.instance().quit()

    def debug_key_press_event(self, event):
        """Custom keyPressEvent handler for debuggin purposes: prints the current
        contents configuration.
        """
        if event.key() == Qt.Key_S:
            config = {section: dict(self.env.config[section])
                      for section in self.env.config.sections()}
            print(json.dumps(config, indent=4))


class AlarmPlayThread(QThread):
    signal = pyqtSignal(int)

    def __init__(self, env):
        super().__init__()
        self.env = env
        self.alarm_builder = alarm_builder.Alarm(self.env)
        self.content = []

    def build(self):
        """Build and alarm."""
        logger.info("Building alarm")
        self.content = self.alarm_builder.build()
        
    def run(self):
        """Play pre-built alarm."""
        # Re-generate greeting to get current time.
        greeting = self.alarm_builder.generate_greeting()
        try:
            self.content[0] = greeting
        except IndexError:
            self.content = [greeting]

        self.alarm_builder.play(self.content)

        # inform the main thread that playing has finished
        self.signal.emit(1)


class RadioStreamer:
    """Helper class for playing a radio stream via mplayer."""
    def __init__(self, config):
        self.process = None
        self.config = config

    def is_playing(self):
        """Check if mplayer is currently running. Return True if it is."""
        return self.process is not None

    def play(self):
        """Open a radio stream as a child process. The stream will continue to run
        in the background.
        """
        # Ensure the currently active 'url' key from config is used as the stream url
        args = self.config["args"].split()
        args[1] = self.config["url"] # we're assuming url position in the arg list!
        args = " ".join(args)

        cmd = "/usr/bin/mplayer {}".format(args)
        logger.info("Running %s", cmd)

        # Run the command via Popen directly to open the stream as an independent child
        # process. This way we do not wait for the stream to finish.
        # Output is captured (truncated) to file.
        with open("logs/radio.log", "w") as f:
            self.process = subprocess.Popen(cmd.split(), stdout=f, stderr=subprocess.STDOUT)

    def stop(self):
        """Terminate the running mplayer process."""
        try:
            self.process.terminate()
            self.process = None
        except AttributeError:
            return
