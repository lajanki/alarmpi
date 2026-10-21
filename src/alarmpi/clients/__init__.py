"""Data sources shared by the GUI plugins and alarm content handlers."""

from typing import Protocol


class SourceError(RuntimeError):
    """A data source could not be refreshed."""


class DataSource(Protocol):
    def fetch(self) -> object: ...

    def close(self) -> None: ...
