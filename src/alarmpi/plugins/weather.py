from functools import partial

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel

from alarmpi.clients.weather import OpenWeatherMapClient, WeatherReading
from alarmpi.core.applugin import AlarmpiPlugin, plugin_logger


class WeatherPlugin(AlarmpiPlugin):
    def __init__(self, config, refresh_interval, parent=None):
        super().__init__(
            partial(OpenWeatherMapClient, config, include_icon=True),
            refresh_interval, parent,
        )
        self.error_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self.temperature_label = QLabel(self)
        self.wind_label = QLabel(self)
        self.icon_label = QLabel(self)
        labels = (self.temperature_label, self.wind_label, self.icon_label)
        for label in labels:
            self.content_layout.addWidget(
                label, alignment=Qt.AlignmentFlag.AlignRight,
            )
        self.poller.updated.connect(self.update_display)

    def update_display(self, weather: WeatherReading):
        self.temperature_label.setText(f"{round(weather.temp)}°C")
        self.wind_label.setText(f"{round(weather.wind_speed_ms)}m/s")
        self.error_label.clear()
        if weather.icon_error:
            self.show_error(weather.icon_error)
            plugin_logger.warning("%s", weather.icon_error)
            self.poller.schedule_retry()
        elif weather.icon is not None:
            pixmap = QPixmap()
            if not pixmap.loadFromData(weather.icon):
                message = "Invalid weather icon image"
                self.show_error(message)
                plugin_logger.error(message)
                self.poller.schedule_retry()
                return
            self.icon_label.setPixmap(pixmap.scaledToWidth(64))
