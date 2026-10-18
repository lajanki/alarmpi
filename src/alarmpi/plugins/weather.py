from functools import partial
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap

from alarmpi.clients import SourceError
from alarmpi.clients.weather import OpenWeatherMapClient
from alarmpi.core import applugin


class WeatherPlugin(applugin.AlarmpiPlugin):

    def __init__(self, parent):
        config_data = parent.config["content"]["openweathermap.org"]
        self.parser = OpenWeatherMapClient(config_data, include_icon=True)
        super().__init__(parent)

    def create_widgets(self):
        """Create and set QLabels for displaying weather components."""
        self.temperature_label = QLabel(self.parent.main_window)
        self.wind_label = QLabel(self.parent.main_window)
        self.icon_label = QLabel(self.parent.main_window)
        self.error_label = QLabel(self.parent.main_window)

        self.parent.main_window.right_plugin_grid.addWidget(self.temperature_label, 0, 0, Qt.AlignRight)
        self.parent.main_window.right_plugin_grid.addWidget(self.wind_label, 1, 0, Qt.AlignRight)
        self.parent.main_window.right_plugin_grid.addWidget(self.icon_label, 2, 0, Qt.AlignRight | Qt.AlignTop)
        self.parent.main_window.right_plugin_grid.addWidget(self.error_label, 3, 0, Qt.AlignRight | Qt.AlignTop)

    def setup_polling(self):
        """Setup polling for updating the weather every 30 minutes."""
        self.update_weather()

        refresh_interval_msec = self.parent.config["plugins"]["openweathermap.org"]["refresh_interval"] * 1000
        _timer = QTimer(self.parent.main_window)
        weather_update_slot = partial(self.run_with_retry, func=self.update_weather, delay_sec=10)
        _timer.timeout.connect(weather_update_slot)
        _timer.start(refresh_interval_msec)

    def update_weather(self):
        """Fetch weather through the shared client and update existing labels."""
        self.retry_flag = False
        try:
            weather = self.parser.fetch()
        except SourceError as e:
            self.error_label.setText(f"! not refreshed - {e}")
            self.retry_flag = True
            return

        self.error_label.clear()
        self.temperature_label.setText(f"{round(weather.temp)}°C")
        self.wind_label.setText(f"{round(weather.wind_speed_ms)}m/s")

        if weather.icon_error:
            self.error_label.setText(f"! not refreshed - {weather.icon_error}")
            self.retry_flag = True
            return

        if weather.icon is not None:
            pixmap = QPixmap()
            pixmap.loadFromData(weather.icon)
            self.icon_label.setPixmap(pixmap.scaledToWidth(64))
