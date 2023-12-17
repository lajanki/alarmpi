
## Alarm configuration
Many features of the alarm, such as alarm content and radio streams to use, can be configured via a .yaml configuration file. By default `configs/default.yaml` will be used.


### default.yaml description

**main**  
* **alarm_time**
  * Default alarm time in HH:MM format. This only pre-sets an alarm to be enabled (or overridden) from the GUI. 
* **low_brightness**
  * Minimum value to set display brightness to when toggling between max and low brightness. Should be between 9 and 255.
  * Raspberry Pi only
* **full_brightness_on_alarm**  
  * When enabled, screen brightness is set to full when the alarm triggers.
  * Can also be toggled from the settings window.
  * Raspberry Pi only
* **nighttime**  
  * Determines time range for nightmode. During this time:
    * display brightness will be set to low when an alarm is set, and
    * when the display is woken up from blank mode, a short timer will be set to re-blank it.
  * Nightmode is useful for quickly checking the time during the night without to manually interact with full brigtness display.
  * Nightmode can also be toggled from the settings window.
  * Raspberry Pi only
* **TTS**
  * Enable/disable text-to-speech alarms. When enabled alarm content will be played as speech, when disabled a beeping sound effect will play as the alarm.
  * Can also be toggled from the settings window.
* **end**
  * An ending greeting to be used by the TTS client after all components, apart from radio stream, have been processed.

**content**  
  Defines the TTS content of the alarm. 
  * `handler` points to a module in the `src/handlers/` folder responsible for creating the content.
  * Additional, content specific, configuration is also passed here. For instance, to get weather data from _openweathermap.org_ an API key needs to be set. See https://openweathermap.org/appid for registering for an API key and http://bulk.openweathermap.org/sample/ for cityid codes.

**Note:** content sections are parsed in the order they appear in the configuration; greeting should come first.


**TTS engines**  
Define which TTS engine to use. Supported engines are:  

 1. GCP
    * Google Cloud Text-to-Speech. This provides the most human-like speech, but requires a Google Cloud project with billing enabled. 
      * Quickstart: https://cloud.google.com/text-to-speech/docs/before-you-begin.
    * Creating and download a service account key and specify the path as `credentials`
    * Paid API with a free tier of 1 million characters per month. A single run of the script generates about 1100 characters worth of text; running the script once per day therefore only generates a total of some 33 000 characters.
      * See https://cloud.google.com/text-to-speech/pricing for pricing

 1. google_translate
    * Google Translate Text-to-Speech engine.
    * This uses an undocumented and unofficial API used in Google Translate. Has a limit of 200 characters per requests which results in noticeable pauses between chunks of text.
      * Google may change or prevent using this API at any time.
    * Eanbled in the default config.

 1. festival
    * Festival is a general purpose TTS system. Does not require an internet access and provides by far the most robotic voice.
    * Used as a fallback when TTS is enabled but no engine is explicitly specified.

**Notes:**
 * Only one TTS engine can be enabled
 * If all TTS engines are disabled but the top level flag **TTS=true** is set, Festival will be used.
 * If disabled in the main config with **TTS=false** and no wakeup song is set, beeping sound effect will play instead.

**radio**  
Radio stations to list for play.
 * The stream will be played though `cvlc`
 * The radio stream plays in a separate process from the Python process running the alarm. While the UI's _radio_ and _close_ buttons take care of terminating the process, a separate `stop.sh` shell script can also be used to terminate both processes. This is useful if the alarm is run in headless mode.

**media**  
Defines an optional wakeup song to be played. 
 * `path` should be a wildcard pattern (a _glob_ pattern) to a set of files. A random file will be chosen.
 * If enabled, the song will be played before any TTS content.

**plugins**  
Additional content known as plugins can be enabled:
 1. `HSL` - Finnish Transport agency's commuter train departures from selected station. Uses DigiTraffic API, see https://www.digitraffic.fi/en/railway-traffic/. Disabled by default.
 2. `DHT22` - indoor temperature using a [DHT22 sensor](https://learn.adafruit.com/dht). Disabled by default.


## Using a custom configuration
You can either modify the provided configuration file `default.yaml` or create a new file and pass that to `main.py` via a command line argument, eg.
```bash
python main.py my_config.yaml
```



### Extending the alarm with custom content
Extending the alarm with you're own content is simple:

 1. Create a handler for your new content and place it in the `src/handlers/` folder. It should subclass `apcontent.AlarmpiContent` and implement the `build` method. This function is where the magic happens: it should store whatever string content to pass to the alarm as the `content` attribute. A minimal handler implementation is something like:
 ```python
 from src import apcontent

 class Handler(apcontent.AlarmpiContent):

    def build(self):
        self.content = "Text-to-Speech content goes here"
 ```

 See any of the existing handlers for reference. The handler module should only contain a single class defining the content parser.
 
 2. Add and entry to the config with `handler` value pointing to your new handler without the folder name.

 3. Remember to set `enabled=true`.

Adding a new TTS engine can be done similarly:

 1. Write the handler. It should should inherit from `src.aptts.AlarmpiTTS` and implement the `play` method.

 2. Add configuration section and enable it.

  * The `credentials` key can be used to point to a file containg any credentials needed for the handler. The file path will be passed to the base class' initializer, see [../src/aptts.py](../src/aptts.py).
  
