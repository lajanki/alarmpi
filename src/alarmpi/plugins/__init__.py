"""Built-in sidebar plugins, imported only when enabled."""


def enabled_plugins(config):
    if config["plugins"]["openweathermap.org"]["enabled"]:
        from alarmpi.plugins.weather import WeatherPlugin

        yield "right", WeatherPlugin(
            config["content"]["weather"],
            config["plugins"]["openweathermap.org"]["refresh_interval"],
        )

    if config["plugins"]["HSL"]["enabled"]:
        from alarmpi.plugins.trains import TrainPlugin

        yield "left", TrainPlugin(config["plugins"]["HSL"])

    if config["plugins"]["DHT22"]["enabled"]:
        from alarmpi.plugins.dht22 import DHT22Plugin

        yield "right", DHT22Plugin(config["plugins"]["DHT22"])
