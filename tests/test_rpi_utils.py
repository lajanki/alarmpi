import pytest
from unittest import mock

from alarmpi.utils import rpi_utils


@pytest.fixture()
def enable_pi():
    rpi_utils.IS_RASPBERRY_PI = True

@pytest.fixture()
def disable_pi():
    rpi_utils.IS_RASPBERRY_PI = False

def test_set_value_when_pi(enable_pi):
    """Is file written to when running on a Raspberry Pi?"""
    with mock.patch("builtins.open", mock.mock_open()) as mock_file:
        rpi_utils._set_value("test.txt", 42)

        mock_file.assert_called_once_with("test.txt", "w")
        mock_file().write.assert_called_once_with("42")

def test_set_value_when_not_pi(disable_pi):
    """Is file write skipped when not running on a Raspberry Pi?"""
    with mock.patch("builtins.open", mock.mock_open()) as mock_file:
        rpi_utils._set_value("test.txt", 42)

        mock_file.assert_not_called()

def test_get_value_when_pi(enable_pi):
    """Is file read from when running on a Raspberry Pi?"""
    with mock.patch("builtins.open", mock.mock_open(read_data="1")) as mock_file:
        rpi_utils._get_value("test.txt")

        mock_file.assert_called_once_with("test.txt")

def test_get_value_when_not_pi(disable_pi):
    """Is file read skipped when not running on a Raspberry Pi?"""
    with mock.patch("builtins.open", mock.mock_open(read_data="1")) as mock_file:
        rpi_utils._get_value("test.txt")

        mock_file.assert_not_called()
