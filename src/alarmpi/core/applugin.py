"""Background polling and lifecycle shared by the built-in sidebar widgets."""

import logging
import math
from collections.abc import Callable

from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot

from alarmpi.clients import DataSource


plugin_logger = logging.getLogger("pluginLogger")
SOURCE_ERRORS = (
    RuntimeError, OSError, ValueError, KeyError, IndexError, TypeError,
)


def _timer_interval(seconds: float, name: str) -> int:
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"Plugin {name} must be a positive number")
    milliseconds = round(seconds * 1000)
    if not 1 <= milliseconds <= 2_147_483_647:
        raise ValueError(f"Plugin {name} is outside Qt timer limits")
    return milliseconds


class _FetchWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, create_source: Callable[[], DataSource]):
        super().__init__()
        self.create_source = create_source
        self.source: DataSource | None = None

    @pyqtSlot()
    def fetch(self):
        try:
            if self.source is None:
                self.source = self.create_source()
            result = self.source.fetch()
        except SOURCE_ERRORS as e:
            plugin_logger.exception("Plugin refresh failed")
            self.failed.emit(str(e))
        else:
            self.succeeded.emit(result)

    @pyqtSlot()
    def shutdown(self):
        try:
            if self.source is not None:
                self.source.close()
        except SOURCE_ERRORS:
            plugin_logger.exception("Plugin resource cleanup failed")
        finally:
            thread = QThread.currentThread()
            assert thread is not None
            thread.quit()


class PluginPoller(QObject):
    updated = pyqtSignal(object)
    failed = pyqtSignal(str)
    _fetch_requested = pyqtSignal()
    _shutdown_requested = pyqtSignal()

    def __init__(
        self, create_source: Callable[[], DataSource], refresh_interval: float,
        parent=None, *, retry_delay: float = 10,
    ):
        super().__init__(parent)
        interval_ms = _timer_interval(refresh_interval, "refresh_interval")
        retry_ms = _timer_interval(retry_delay, "retry_delay")

        self._active = False
        self._busy = False
        self._retry_attempt = False
        self._stopped = False
        self.worker_thread = QThread(self)
        self.worker = _FetchWorker(create_source)
        self.worker.moveToThread(self.worker_thread)
        self._fetch_requested.connect(self.worker.fetch)
        self._shutdown_requested.connect(self.worker.shutdown)
        self.worker.succeeded.connect(self._succeeded)
        self.worker.failed.connect(self._failed)
        self.worker_thread.finished.connect(self.worker.deleteLater)

        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.refresh)
        self.retry_timer = QTimer(self)
        self.retry_timer.setSingleShot(True)
        self.retry_timer.setInterval(retry_ms)
        self.retry_timer.timeout.connect(self._retry)

    def start(self):
        if self._stopped:
            raise RuntimeError("A stopped plugin cannot be restarted")
        if self._active:
            return
        self._active = True
        self.worker_thread.start()
        self.timer.start()
        self.refresh()

    def refresh(self):
        if not self._active or self._busy:
            return
        self.retry_timer.stop()
        self._retry_attempt = False
        self._request()

    def _request(self):
        self._busy = True
        self._fetch_requested.emit()

    def schedule_retry(self):
        """Retry partial failures too, such as an unavailable weather icon."""
        if self._active and not self._retry_attempt:
            self.retry_timer.start()

    def _retry(self):
        if self._active and not self._busy:
            self._retry_attempt = True
            self._request()

    @pyqtSlot(object)
    def _succeeded(self, result):
        self._busy = False
        if self._active:
            self.updated.emit(result)

    @pyqtSlot(str)
    def _failed(self, message):
        self._busy = False
        if self._active:
            self.failed.emit(message)
            self.schedule_retry()

    def stop(self):
        """Drain in-flight work and release resources on the worker."""
        if self._stopped:
            return
        self._active = False
        self._stopped = True
        self.timer.stop()
        self.retry_timer.stop()
        if self.worker_thread.isRunning():
            self._shutdown_requested.emit()
            self.worker_thread.wait()


class AlarmpiPlugin:

    def __init__(self, parent):
        self.retry_flag = False
        self.parent = parent

    def run_with_retry(self, func, delay_sec=10):
        """Run func with single retry after a delay."""
        func()
        if self.retry_flag:
            self.retry_flag = False
            timer = QTimer(self.parent.main_window)
            timer.setSingleShot(True)
            timer.timeout.connect(func)
            timer.start(delay_sec*1000)
