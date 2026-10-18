from functools import partial

from PyQt5.QtWidgets import QLabel

from alarmpi.clients.trains import TrainClient
from alarmpi.core.applugin import AlarmpiPlugin


class TrainPlugin(AlarmpiPlugin):
    def __init__(self, config, parent=None):
        super().__init__(
            partial(TrainClient, config), config["refresh_interval"], parent,
        )
        self.train_labels = []
        for _ in range(config["trains"]):
            label = QLabel(self)
            self.content_layout.addWidget(label)
            self.train_labels.append(label)
        self.poller.updated.connect(self.update_display)

    def update_display(self, trains):
        self.error_label.clear()
        for i, label in enumerate(self.train_labels):
            if i >= len(trains):
                label.clear()
                continue
            train = trains[i]
            line_id = train["commuterLineID"]
            scheduled = train["scheduledTime"].strftime("%H:%M")
            message = f"{line_id} {scheduled}"
            if train["cancelled"]:
                message += " CANCELLED"
            elif train["liveEstimateTime"]:
                estimate = train["liveEstimateTime"].strftime("%H:%M")
                message += f" ⇒ {estimate}"
            label.setText(message)
