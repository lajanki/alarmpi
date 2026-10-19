
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
| **TTS** | Enable Text-to-Speech alarm content. A beeping sound effect is played if disabled. |
| **end** | Closing line spoken by the TTS client after everything except the radio stream. |

---

#### `alsa`

ALSA Audio output device configuration: playback device and initial volume. Use `aplay -l` to list devices.

---

#### `content`

Alarm speech content. Each block can point at a handler and pass extra options (for example OpenWeatherMap API keys).

- **`handler`** — module under `src/alarmpi/handlers/` that builds that segment’s text.
- **Other keys** — engine- or source-specific (e.g. OpenWeatherMap: [API keys](https://openweathermap.org/appid), [city IDs](http://bulk.openweathermap.org/sample/)).

**Order:** Blocks are processed in YAML order; **greeting** should be processed first.

---

#### `TTS` (engines)

Only one engine is can be enabled.

| Engine | Summary |
|--------|---------|
| **GCP** | [Google Cloud Text-to-Speech](https://cloud.google.com/text-to-speech). Most natural voice; needs a GCP project. **Authentication:** set `GOOGLE_APPLICATION_CREDENTIALS` to enable Application Default Credentials. Alternatively, configure service account to impersonate through `auth` section, but this still requires runtime user credentials to initiate the impersonation. **Cost:** Moderate usage likely falls under free tier — see [pricing](https://cloud.google.com/text-to-speech/pricing). |
| **Piper** | Local neural TTS. Install with the project dependencies and download a voice model; no network access is needed to synthesize after setup. |

The sample configuration selects Piper and expects the voice at
`voices/en_US-lessac-medium.onnx`. From the project root, download that voice
and its matching `.onnx.json` metadata file with:

```bash
uv run python -m piper.download_voices en_US-lessac-medium --data-dir voices
```

Set `TTS.Piper.model_path` to the `.onnx` file for a different voice. Review
the voice's model card for its license and usage restrictions.

> [!NOTE]
> - Piper is used with its configured voice if no engine is enabled.
> - If TTS is disabled a beeping sound effect will play on alarm.
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
| **openweathermap.org** | Current outdoor temperature, wind, and weather icon. Uses credentials and city settings from `content.openweathermap.org`, even if its spoken content is disabled. |

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

### Adding a TTS engine

Adding a new TTS engine can be done similarly:

 1. Write the handler. It should should inherit from `alarmpi.aptts.AlarmpiTTS` and implement the `play` method.

 2. Add configuration section and enable it.

  * The `credentials` key can be used to point to a file containg any credentials needed for the handler. The file path will be passed to the base class' initializer, see [../src/aptts.py](../src/aptts.py).
  
