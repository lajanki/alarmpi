from functools import partial

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel

from alarmpi.clients.dht22 import DHT22Client
from alarmpi.core.applugin import AlarmpiPlugin


class DHT22Plugin(AlarmpiPlugin):
    def __init__(self, config, parent=None):
        super().__init__(
            partial(DHT22Client, config), config["refresh_interval"], parent,
        )
        self.dht22_label = QLabel(self)
        self.content_layout.addWidget(
            self.dht22_label, alignment=Qt.AlignmentFlag.AlignRight,
        )
        self.poller.updated.connect(self.update_display)

    def update_display(self, temperature: float):
        self.error_label.clear()
        self.dht22_label.setText(f"⌂ {round(temperature)}°C")

    def show_error(self, message):
        if not self.dht22_label.text():
            self.dht22_label.setText("ERR")
        super().show_error(message)
