import sys
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from PyQt5.QtCore import QBuffer, QIODevice
from PyQt5.QtGui import QImage

from alarmpi.clients import SourceError
from alarmpi.clients.weather import WeatherReading
from alarmpi.core import GUIWidgets, apconfig, clock
from alarmpi.plugins import enabled_plugins
from alarmpi.plugins.trains import TrainPlugin
from alarmpi.plugins.weather import WeatherPlugin
from tests.test_clients import WEATHER_CONFIG
from tests.test_plugin_polling import FakeSource, wait, wait_until


@pytest.fixture
def dht_module():
    board = SimpleNamespace(pin=Mock())
    adafruit = SimpleNamespace(DHT22=Mock())
    with patch.dict(sys.modules, {"board": board, "adafruit_dht": adafruit}):
        from alarmpi.clients import dht22
        from alarmpi.plugins import dht22 as plugin

        yield dht22, plugin, adafruit.DHT22


def test_dht_missing_dependencies_report_source_error():
    from alarmpi.clients.dht22 import DHT22Client

    with patch.dict(sys.modules, {"board": None}):
        with pytest.raises(
            SourceError, match="DHT22 dependencies unavailable",
        ):
            DHT22Client({"GPIO": 4})


def test_dht_zero_and_errors_release_device(dht_module):
    module, _, device_class = dht_module
    device = device_class.return_value
    client = module.DHT22Client({"GPIO": 4})
    device.temperature = 0.0
    assert client.fetch() == 0.0
    device.temperature = None
    with pytest.raises(SourceError, match="no measurement"):
        client.fetch()
    client.close()
    device.exit.assert_called_once()


def test_widgets_own_layouts_and_do_not_collide(dht_module):
    _, module, _ = dht_module
    weather = WeatherPlugin({}, 60)
    indoor = module.DHT22Plugin({"refresh_interval": 30})
    window = GUIWidgets.AlarmWindow()
    try:
        window.add_plugin(weather, "right")
        window.add_plugin(indoor, "right")
        layout = window.plugin_layouts["right"]
        assert layout.count() == 2
        first, second = layout.itemAt(0), layout.itemAt(1)
        assert first is not None and second is not None
        assert first.widget() is weather
        assert second.widget() is indoor
        assert weather.error_label.parentWidget() is weather
        assert indoor.dht22_label.parentWidget() is indoor
        weather.show_error("offline")
        indoor.update_display(0)
        assert weather.error_label.text() == "ERR"
        assert "0°C" in indoor.dht22_label.text()
        indoor.show_error("sensor offline")
        assert "0°C" in indoor.dht22_label.text()
        assert indoor.error_label.text() == "ERR"
        indoor.update_display(10)
        assert indoor.error_label.text() == ""
    finally:
        weather.stop()
        indoor.stop()
        window.close()


@pytest.mark.parametrize("error", [
    FileNotFoundError(2, "No such file", "/private/weather-api-key"),
    PermissionError(13, "Permission denied", "/private/weather-api-key"),
    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid credential encoding"),
])
def test_weather_credential_errors_are_safe_for_display(error, caplog):
    widget = WeatherPlugin(WEATHER_CONFIG, 60)
    widget.temperature_label.setText("12°C")
    widget.poller.retry_timer.setInterval(60_000)
    try:
        with patch("builtins.open", side_effect=error):
            widget.start()
            wait_until(lambda: bool(widget.error_label.text()))
        assert widget.error_label.text() == "ERR"
        assert widget.temperature_label.text() == "12°C"
        assert widget.poller.retry_timer.isActive()
        records = [
            record for record in caplog.records
            if record.name == "pluginLogger" and record.exc_info
        ]
        assert records
        exception = records[-1].exc_info[1]
        assert exception is not None
        assert exception.__cause__ is error
        assert str(error) in caplog.text
    finally:
        widget.stop()


@pytest.mark.parametrize("plugin_name", ["weather", "trains", "dht22"])
@pytest.mark.parametrize("error", [
    SourceError("Request failed: private connection details"),
    KeyError("private configuration key"),
])
def test_plugin_errors_only_display_err(plugin_name, error, caplog):
    from alarmpi.plugins.dht22 import DHT22Plugin

    factories = {
        "weather": (
            "alarmpi.plugins.weather.OpenWeatherMapClient",
            lambda: WeatherPlugin({}, 60),
        ),
        "trains": (
            "alarmpi.plugins.trains.TrainClient",
            lambda: TrainPlugin({"refresh_interval": 60, "trains": 2}),
        ),
        "dht22": (
            "alarmpi.plugins.dht22.DHT22Client",
            lambda: DHT22Plugin({"refresh_interval": 60}),
        ),
    }
    factory_path, create_widget = factories[plugin_name]
    source = FakeSource((error,))
    with patch(factory_path, return_value=source):
        widget = create_widget()
    try:
        widget.start()
        wait_until(lambda: bool(widget.error_label.text()))
        assert widget.error_label.text() == "ERR"
        assert str(error) in caplog.text
        assert any(
            record.name == "pluginLogger" and record.exc_info
            for record in caplog.records
        )
        if plugin_name == "dht22":
            assert widget.dht22_label.text() == ""
    finally:
        widget.stop()


def test_weather_partial_failure_updates_text_and_retries(caplog):
    reading = WeatherReading(
        12.5, "clear", 3, 10.8, 11, "07:00", "18:00",
        icon_error="icon offline",
    )
    source = FakeSource((reading, reading))
    with patch(
        "alarmpi.plugins.weather.OpenWeatherMapClient", return_value=source,
    ):
        widget = WeatherPlugin({}, 60)
    widget.poller.retry_timer.setInterval(10)
    try:
        widget.start()
        wait_until(lambda: len(source.fetch_threads) == 2)
        wait(30)
        assert widget.temperature_label.text() == "12°C"
        assert widget.error_label.text() == "ERR"
        assert "icon offline" in caplog.text
        assert len(source.fetch_threads) == 2
    finally:
        widget.stop()


def test_invalid_icon_reports_error_and_valid_icon_recovers(caplog):
    widget = WeatherPlugin({}, 60)
    reading = WeatherReading(
        10, "clear", 2, 7.2, 9, "07:00", "18:00", b"invalid",
    )
    widget.update_display(reading)
    assert widget.error_label.text() == "ERR"
    assert "Invalid weather icon image" in caplog.text
    image = QImage(2, 2, QImage.Format_RGB32)
    image.fill(0)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    widget.update_display(
        WeatherReading(
            10, "clear", 2, 7.2, 9, "07:00", "18:00", bytes(buffer.data()),
        ),
    )
    assert widget.error_label.text() == ""
    pixmap = widget.icon_label.pixmap()
    assert pixmap is not None and not pixmap.isNull()
    widget.stop()


def test_train_rendering_clears_unused_labels_and_preserves_data_on_error():
    widget = TrainPlugin({"refresh_interval": 60, "trains": 3})
    scheduled = datetime(2026, 10, 18, 12, 0)
    estimate = datetime(2026, 10, 18, 12, 5)
    trains = [
        {
            "commuterLineID": "K", "scheduledTime": scheduled,
            "liveEstimateTime": estimate, "cancelled": False,
        },
        {
            "commuterLineID": "R", "scheduledTime": scheduled,
            "liveEstimateTime": estimate, "cancelled": True,
        },
    ]
    widget.train_labels[2].setText("stale")
    widget.update_display(trains)
    assert widget.train_labels[0].text() == "K 12:00 ⇒ 12:05"
    assert widget.train_labels[1].text() == "R 12:00 CANCELLED"
    assert widget.train_labels[2].text() == ""
    widget.show_error("offline")
    assert widget.error_label.text() == "ERR"
    assert widget.train_labels[0].text() == "K 12:00 ⇒ 12:05"
    widget.update_display([])
    assert all(label.text() == "" for label in widget.train_labels)
    assert widget.error_label.text() == ""
    widget.stop()


def test_disabled_plugins_do_not_import_hardware():
    config = {
        "plugins": {
            name: {"enabled": False}
            for name in ("openweathermap.org", "HSL", "DHT22")
        },
    }
    with patch.dict(sys.modules, {"alarmpi.plugins.dht22": None}):
        assert list(enabled_plugins(config)) == []


def test_clock_mounts_starts_and_stops_plugins():
    config = apconfig.AlarmConfig("tests/test_alarm.yaml")
    with patch("alarmpi.core.clock.apconfig.AlarmConfig", return_value=config):
        instance = clock.Clock("unused")
    source = FakeSource(([],))
    with (
        patch("alarmpi.plugins.trains.TrainClient", return_value=source),
        patch("alarmpi.core.clock.utils.get_volume", return_value=50),
        patch("alarmpi.core.clock.utils.set_volume"),
    ):
        config["plugins"]["HSL"].update({
            "enabled": True, "refresh_interval": 60, "trains": 2,
        })
        instance.setup()
    try:
        assert len(instance.plugins) == 1
        plugin = instance.plugins[0]
        wait_until(lambda: bool(source.fetch_threads))
        item = instance.main_window.plugin_layouts["left"].itemAt(0)
        assert item is not None and item.widget() is plugin
        instance.main_window.close()
        assert not plugin.poller.worker_thread.isRunning()
        assert len(source.close_threads) == 1
    finally:
        instance.stop_plugins()
        instance.main_window.close()
