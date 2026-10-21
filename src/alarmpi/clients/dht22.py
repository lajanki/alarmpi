from alarmpi.clients import SourceError


class DHT22Client:
    """Get readings from a DHT22 sensor."""

    def __init__(self, section_data):
        try:
            import board
            import adafruit_dht
        except ImportError as e:
            raise SourceError(f"DHT22 dependencies unavailable: {e}") from e

        PIN = board.pin.Pin(section_data["GPIO"])
        self.dht_device = adafruit_dht.DHT22(PIN, use_pulseio=False)

    def fetch(self) -> float:
        """Read the sensor; the plugin retries transient failures."""
        try:
            temperature = self.dht_device.temperature
        except (RuntimeError, OSError) as e:
            raise SourceError(f"Temperature read failed: {e}") from e
        if temperature is None:
            raise SourceError("Temperature read returned no measurement")
        return temperature

    def close(self):
        self.dht_device.exit()
