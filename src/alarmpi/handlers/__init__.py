from importlib import import_module


HANDLERS = {
    "content": {
        "bbc_news": ("get_bbc_news", "NewsParser"),
        "greeting": ("get_greeting", "Greeting"),
        "weather": ("get_weather", "WeatherContent"),
    },
    "tts": {
        "gcp": ("get_gcp_tts", "GoogleCloudTTS"),
        "piper": ("get_piper_tts", "PiperTTSManager"),
    },
}


def is_registered_handler(category, handler_id):
    return handler_id in HANDLERS.get(category, {})


def get_handler(category, handler_id):
    try:
        module_name, class_name = HANDLERS[category][handler_id]
    except KeyError as error:
        raise ValueError(
            f"Unknown {category} handler: {handler_id}"
        ) from error

    module = import_module(f"{__name__}.{module_name}")
    return getattr(module, class_name)
