
## Alarm configuration
Many features of the alarm, such as alarm content and radio streams to use, can be configured via a .yaml configuration file. By default `configs/default.yaml` will be used.


### `default.yaml` reference


#### `main`

| Key | Purpose |
|-----|---------|
| **alarm_time** | Alarm time in `HH:MM` format. Additionally, the alarm must be enabled from the GUI. |
| **low_brightness** | Minimum brightness when toggling between max and low (9–255). *Raspberry Pi only.* |
| **full_brightness_on_alarm** | When enabled, brightness goes to full when the alarm fires. Also in settings. *Raspberry Pi only.* |
| **nighttime** | Night mode time range. While active: brightness stays low when an alarm is set; waking from blank starts a short timer to re-blank. Handy for checking the time at night without full brightness. Also in settings. *Raspberry Pi only.* |
| **TTS** | Master speech switch and selected engine. Set `enabled: false` to use the beep instead of speech. The `handler` is optional; without a configured engine the alarm uses the beep. |

---

#### `alsa`

ALSA output card selector passed to `amixer -c`. Use `aplay -l` to list cards.
A card ID is preferred over a card number as ordering is not guaranteed accross boots.
For example: `card: "PCH"`.
`startup_volume` is an optional override for current ALSA volume on launch.
When omitted or `null`, Alarmpi leaves the
current volume unchanged and initializes the slider from the device's level.

---

#### `content`

Alarm speech content. Registered handlers are selected by the content section
name (`greeting`, `weather`, or `bbc_news`, case-insensitive). Handler sections
can pass extra options, such as OpenWeatherMap API keys. Other sections can
provide literal text directly.

- **`text`** — literal content to speak without a handler; use this for simple
   lines such as the closing phrase.
- **`template`** — for the `greeting` section, the sentence to format with
   `{period}`, `{name}`, `{weekday}`, `{month}`, `{day_of_month}`, and `{time}`.
   The name comes from the greeting config; date and period use the current
   date/time, and time uses `main.alarm_time`.
- **Other keys** — engine- or source-specific (e.g. OpenWeatherMap: [API keys](https://openweathermap.org/appid), [city IDs](http://bulk.openweathermap.org/sample/)).

**Order:** Blocks are processed in YAML order; keep **greeting** first and put
**farewell** last.

---

#### `main.TTS` (engine)

Select a TTS engine using its handler. Engine-specific options go in the same
mapping.

| Engine | Summary |
|--------|---------|
| **GCP** | [Google Cloud Text-to-Speech](https://cloud.google.com/text-to-speech). Requires a GCP project. Set `GOOGLE_APPLICATION_CREDENTIALS` for Application Default Credentials, or configure service-account impersonation with `auth`. See [pricing](https://cloud.google.com/text-to-speech/pricing). |
| **Piper** | Local neural TTS. Install with the project dependencies and download a voice model; no network access is needed to synthesize after setup. |

Piper example (also used in the default config):

```yaml
main:
   TTS:
      handler: piper
      model_path: voices/en_US-lessac-medium.onnx
```

From the project root, download the voice and its matching `.onnx.json`
metadata file with:

```bash
uv run python -m piper.download_voices en_US-lessac-medium --data-dir voices
```

Set `main.TTS.model_path` to the `.onnx` file for a different voice. Review the
voice's model card for its license and usage restrictions.

GCP example:

```yaml
main:
   TTS:
      handler: gcp
      # Optional service-account impersonation; otherwise use ADC through
      # GOOGLE_APPLICATION_CREDENTIALS.
      auth:
         service_account: <account>@<project>.iam.gserviceaccount.com
```

> [!NOTE]
> - Set `main.TTS: null` to disable speech. Without a wakeup track the alarm beeps.
> - If TTS setup or playback fails, the alarm falls back to a beep.
> - GCP: A single alarm generates around 1 100 characters falling well within the  WaveNet free tier

---

#### `radio`

Station URLs for the radio feature. Playback uses `cvlc`. The stream runs outside the main Python process; the UI **radio** / **close** buttons or the `stop.sh` script can stop it (useful in headless mode).

---

#### `media`

Optional wakeup track before TTS.

- **`path`** — glob to audio files; one file is chosen at random each alarm.

---

#### `plugins`

Extra data sources (disabled by default):

| Plugin | What it does |
|--------|----------------|
| **HSL** | Commuter train departures (Finland). [DigiTraffic](https://www.digitraffic.fi/en/railway-traffic/). |
| **DHT22** | Indoor temperature via a [DHT22](https://learn.adafruit.com/dht) sensor. |
| **openweathermap.org** | Current outdoor temperature, wind, and weather icon. Uses credentials and city settings from `content.weather`, even if its spoken content is disabled. |

Each plugin's `refresh_interval` is in seconds and must be positive. Plugins
fetch data on background workers to avoid intefering with the main GUI thread.
Failed refreshes retain the last successful display with an additional `ERR` message.
Detailed errors are kept in the plugin error log, not displayed in the widgets.

Plugin widgets are stacked independently in the left or right sidebar.


## Using a custom configuration
You can either modify the provided configuration file `default.yaml` or create a new file and pass it as a command line argument:
```bash
uv run alarmpi my_config.yaml
```


### Extending the alarm with custom content
Extending the alarm with you're own content is simple:

 1. Create a handler for your new content and place it in the `src/alarmpi/handlers/` folder. It should subclass `apcontent.AlarmpiContent` and implement the `build` method. This function is where the magic happens: it should store whatever string content to pass to the alarm as the `content` attribute. A minimal handler implementation is something like:
 ```python
 from alarmpi.core import apcontent

 class Handler(apcontent.AlarmpiContent):

    def build(self):
        self.content = "Text-to-Speech content goes here"
 ```

 See any of the existing handlers for reference. The handler module should only contain a single class defining the content parser.
 
 2. Add and entry to the config with `handler` value pointing to your new handler without the folder name.

 3. Remember to set `enabled=true`.

### Adding a sidebar plugin

The built-in plugins use three small pieces:

1. A Qt-independent data client under [`src/alarmpi/clients/`](../src/alarmpi/clients/)
   implements `fetch()` and `close()`. It returns domain data or raises
   `SourceError` on a failed read. `close()` releases resources such as GPIO
   devices (and can be empty for stateless HTTP clients). Both methods, and
   client construction, run on the same background thread.
2. A widget under [`src/alarmpi/plugins/`](../src/alarmpi/plugins/) subclasses
   `AlarmpiPlugin`, passes a client factory and refresh interval to its
   constructor, and creates its labels in `self.content_layout`. Connect
   `self.poller.updated` to a rendering method; this runs on the GUI thread.
   The widget owns its layout and error label, not the main window's grid.
3. Add an enabled check and yield `(side, widget)` from
   [`enabled_plugins`](../src/alarmpi/plugins/__init__.py), where `side` is
   `"left"` or `"right"`. Import optional hardware modules only for enabled
   plugins. The clock mounts the widget and manages its `start()`/`stop()`
   lifecycle.

If a source also supplies spoken alarm content, add a separate content handler
that uses the same client. For example,
[`get_weather.py`](../src/alarmpi/handlers/get_weather.py) formats speech without
creating a widget or downloading a weather icon. Client, widget, and speech
formatting remain separate responsibilities; no dynamic plugin discovery is
required.

### Adding a handler

Implement the handler in `src/alarmpi/handlers/`, then register its stable ID
and class in the appropriate registry in `src/alarmpi/handlers/__init__.py`.
Content handlers go in `content`; TTS handlers go in `tts` and inherit from
`alarmpi.core.aptts.AlarmpiTTS`. Configs use the registry ID, not the Python
module filename.
  
