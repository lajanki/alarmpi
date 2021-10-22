from functools import partial
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap

from src.handlers import get_weather


class WeatherPlugin:

    def __init__(self, parent):
        self.retry_flag = False
        self.parent = parent
        config_data = parent.config["content"]["openweathermap.org"]
        self.parser = get_weather.OpenWeatherMapClient(config_data)

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
        _weather_update_slot = partial(self.run_with_retry, func=self.update_weather, delay_ms=10000)
        _timer.timeout.connect(_weather_update_slot)
        _timer.start(refresh_interval_msec)

    def update_weather(self):
        """Update the weather labels on the main window. Makes an API request to
        openweathermap.org for current temperature and windspeed.
        """
        self.retry_flag = False
        weather = self.parser.fetch_and_format_weather()
        pixmap = QPixmap()

        if weather is None:
            self.error_label.setText("<html><span style='font-size:14px'>! not refreshed</span></html>")
            self.retry_flag = True
            return

        self.error_label.clear()
        temperature = weather["temp"]
        wind = weather["wind_speed_ms"]

        msg = "{}°C".format(round(temperature))
        self.temperature_label.setText(msg)

        msg = "{}m/s".format(round(wind))
        self.wind_label.setText(msg)

        # Weather icon is fetched via a separate API call which
        # may fail regardless of the main call.
        if weather["icon"] is None:
            self.retry_flag = True
            return

        pixmap.loadFromData(weather["icon"])
        pixmap = pixmap.scaledToWidth(64)
        self.icon_label.setPixmap(pixmap)

    def run_with_retry(self, func, delay_msec=120000):
        """Run func with single retry after a delay.
        Default delay is 2 minutes.
        """
        func()
        if self.retry_flag:
            self.retry_flag = False
            _timer = QTimer(self.parent.main_window)
            _timer.setSingleShot(True)
            _timer.timeout.connect(func)
            _timer.start(delay_msec)
