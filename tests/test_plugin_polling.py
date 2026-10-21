import threading
import time
from unittest.mock import Mock

import pytest
from PyQt5.QtCore import QEventLoop, QThread, QTimer
from PyQt5.QtWidgets import QApplication

from alarmpi.clients import SourceError
from alarmpi.core.applugin import PluginPoller


def wait(milliseconds):
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec_()


def wait_until(predicate, timeout=2000):
    deadline = time.monotonic() + timeout / 1000
    while not predicate() and time.monotonic() < deadline:
        wait(5)
    assert predicate(), "Timed out waiting for Qt events"


class FakeSource:
    def __init__(self, values=(42,)):
        self.values = list(values)
        self.fetch_threads = []
        self.close_threads = []

    def fetch(self):
        self.fetch_threads.append(QThread.currentThread())
        index = min(len(self.fetch_threads) - 1, len(self.values) - 1)
        value = self.values[index]
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        self.close_threads.append(QThread.currentThread())


def test_polling_does_not_block_gui_or_overlap():
    app = QApplication.instance()
    assert app is not None
    entered = threading.Event()
    release = threading.Event()
    source = FakeSource()
    original_fetch = source.fetch

    def fetch():
        entered.set()
        if not release.wait(2):
            raise RuntimeError("Test fetch was not released")
        return original_fetch()

    source.fetch = fetch
    created_on = []

    def create_source():
        created_on.append(QThread.currentThread())
        return source

    poller = PluginPoller(create_source, 0.01)
    results = []
    delivery_threads = []

    def receive(result):
        results.append(result)
        delivery_threads.append(QThread.currentThread())

    poller.updated.connect(receive)
    heartbeat = []
    timer = QTimer()
    timer.setInterval(1)
    timer.timeout.connect(lambda: heartbeat.append(True))
    timer.start()
    try:
        poller.start()
        wait_until(entered.is_set)
        wait(40)
        assert heartbeat
        assert results == []
        for _ in range(3):
            poller.refresh()
        poller.timer.stop()
        release.set()
        wait_until(lambda: bool(results))
        poller.stop()
        assert results == [42]
        assert created_on == source.fetch_threads
        assert source.fetch_threads == source.close_threads
        assert created_on[0] != app.thread()
        assert delivery_threads == [app.thread()]
        assert not poller.worker_thread.isRunning()
    finally:
        release.set()
        timer.stop()
        poller.stop()


def test_initial_failure_gets_one_retry_and_recovers():
    source = FakeSource((
        SourceError("offline"), 17, SourceError("offline again"), 18,
    ))
    poller = PluginPoller(lambda: source, 60, retry_delay=0.01)
    failures = []
    results = []
    poller.failed.connect(failures.append)
    poller.updated.connect(results.append)
    try:
        poller.start()
        wait_until(lambda: results == [17])
        assert failures == ["offline"]
        assert len(source.fetch_threads) == 2
        assert not poller.retry_timer.isActive()
        poller.refresh()
        wait_until(lambda: results == [17, 18])
        assert failures == ["offline", "offline again"]
        assert len(source.fetch_threads) == 4
    finally:
        poller.stop()


def test_retry_is_bounded_and_stop_cancels_timers():
    source = FakeSource((SourceError("offline"), SourceError("still offline")))
    poller = PluginPoller(lambda: source, 60, retry_delay=0.01)
    failures = []
    poller.failed.connect(failures.append)
    try:
        poller.start()
        poller.start()
        wait_until(lambda: len(failures) == 2)
        wait(40)
        assert len(source.fetch_threads) == 2
        assert not poller.retry_timer.isActive()
        poller.stop()
        poller.stop()
        assert not poller.timer.isActive()
        assert len(source.close_threads) == 1
    finally:
        poller.stop()


def test_stop_cancels_pending_retry():
    source = FakeSource((SourceError("offline"),))
    poller = PluginPoller(lambda: source, 60, retry_delay=0.1)
    try:
        poller.start()
        wait_until(poller.retry_timer.isActive)
        poller.stop()
        wait(120)
        assert len(source.fetch_threads) == 1
        assert not poller.retry_timer.isActive()
    finally:
        poller.stop()


def test_stop_drains_fetch_and_discards_late_result():
    entered = threading.Event()
    release = threading.Event()
    source = FakeSource()
    original_fetch = source.fetch

    def fetch():
        entered.set()
        if not release.wait(2):
            raise RuntimeError("Test fetch was not released")
        return original_fetch()

    source.fetch = fetch
    poller = PluginPoller(lambda: source, 60)
    results = []
    poller.updated.connect(results.append)
    try:
        poller.start()
        wait_until(entered.is_set)
        release.set()
        poller.stop()
        wait(10)
        assert results == []
        assert len(source.close_threads) == 1
        assert not poller.worker_thread.isRunning()
    finally:
        release.set()
        poller.stop()


def test_factory_failure_is_reported_and_retried():
    source = FakeSource()
    factory = Mock(side_effect=[OSError("sensor unavailable"), source])
    poller = PluginPoller(factory, 60, retry_delay=0.01)
    failures = []
    results = []
    poller.failed.connect(failures.append)
    poller.updated.connect(results.append)
    try:
        poller.start()
        wait_until(lambda: bool(results))
        assert failures == ["sensor unavailable"]
        assert factory.call_count == 2
    finally:
        poller.stop()


def test_cleanup_failure_is_logged_and_thread_still_stops(caplog):
    source = FakeSource()
    source.close = Mock(side_effect=RuntimeError("cleanup failed"))
    poller = PluginPoller(lambda: source, 60)
    try:
        poller.start()
        wait_until(lambda: bool(source.fetch_threads))
    finally:
        poller.stop()
    assert not poller.worker_thread.isRunning()
    assert "cleanup failed" in caplog.text


@pytest.mark.parametrize(
    "interval", [0, -1, float("nan"), float("inf"), 3_000_000],
)
def test_invalid_polling_interval_rejected(interval):
    with pytest.raises(ValueError, match="refresh_interval"):
        PluginPoller(lambda: FakeSource(), interval)
