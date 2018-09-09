# Alarmpi

A clock radio for a Raspberry Pi with a display, work in progress.

This is a fork of skiwithpete's alarmpi project: https://github.com/skiwithpete/alarmpi. After seeing it on [YouTube](https://youtu.be/julETnOLkaU), I knew wanted to build a similar system to replace my existing bedside clock radio. I had already bought the official touchscreen with a new Pi but other than messing around with it, I had no real use for it until this project.

### Main Features
 * A greeting based on time of day
 * Tells the day's weather using Yahoo Weather
 * Reads latest news from BBC World RSS feeds

 These are largely the same as the corresponding features in the original project. Additionally I've added two new one for my own use case:
 * A GUI for displaying current time as well as for scheduling the alarm.

  * The GUI is rather primitive due to hardware limitations: I build this project to run on a Raspberry Pi together with the official touch screen display with no additional input device. Since Raspbian is not a touch screen OS, it's support is limited to emulating mouse clicks. The alarm is therefore set using a binary based system for the hour and minute. TODO: image

 * Stream a radio station using `mplayer`


I've made a number of changed to the original project:
 * Ported the project Python 3 (Python 2 is unsupported)
 * changed naming conventions to be more PEP 8 compliant and other minor cleanups
 * Cleaned up file structure
 * Removed some modules I deemed unnecessary (mainly due to removed features, see the next point)
 * Removed features not applicable to my use case (including turning lights on and off, playing songs and reading stocks from Yahoo Finance, which has been discontinued)
 * Changed which text-to-speech engines are available, see below
 * Changed audio processing to use in-memory objects, thus removing the need to setup a ramdrive
 * Added unit tests (although the test suite is a bit light)



### Setup
First, install required system packages with
`apt install festival mplayer portaudio19-dev python-all-dev`
This includes the Festival text-to-speech engine, the command line movie player mplayer for playing radio streams and audio libraries enabling playback of mp3 files directly in Python.

Next, install requires Python packages with `pip install -r requirements.txt`. Using a virtualenv is recommended.

Optionally, run unit tests with `python -m unittest tests/test_alarm.py`


### Usage
Run the program with `python main.py`. This opens the GUI for displaying current time and scheduling the alarm.

If you have a headless Raspberry Pi environment (ie. no display attached) running the clock module will fail as Tkinter cannot be imported. In such cases you can also run the alarm directly with `python sound_the_alarm.py <path-to-configuration-file>`. This parses the configuration file (by default `alarm.config`), creates an appropriate alarm and plays it.

To schedule the alarm, create a cron entry manually with `crontab -e`, remember to use absolute paths to both the python interpreter to use (again, virtualenvs are handy) as well as to the configuration file. Remember to use absolute paths.

The interface to `sound_the_alarm` is:
```
positional arguments:
  config         path to the config file
  debug          prints debug messages during execution

optional arguments:
  -h, --help     show this help message and exit
  --init-config  re-create the default configuration file alarm.config.
                 Overwrites existing file.
```

#### alarm.config description
The alarm depends on a configuration file which specifies the content the alarm should play and which text-to-speech (tts) client should be used.

 * **[main]** here you can disable all tts processing with `readaloud=0`. Enabling debug mode prints the speech content on screen.
 * The content sections, ie. those with `type=content` define enabled alarm content (greeting, weather and news).
 * The tts sections with `type=tts` define which tts client should be used. 3 choices are provided:
   1. Google Cloud Text-to-Speech engine. This provides the most human-like speech, but requires some additional setup. Since this is a Google Cloud platform API, you need to setup a Google Cloud project and enable billing.

    Follow the quick start guide in https://cloud.google.com/text-to-speech/docs/quickstart-protocol to setup a project. Instead of setting the `GOOGLE_APPLICATION_CREDENTIALS` environment variable, specify the path to your key as the `private_key_file` option in the configuration file.

    While this is a paid API, there is a free tier of 1 million characters per month. This should easily cover the alarm's needs: a single run of the script generates about 1100 characters worth of text, running the script once per day therefore only generates a total of some 33 000 characters. See https://cloud.google.com/text-to-speech/pricing and https://cloud.google.com/text-to-speech/quotas for more information.

  2. Google Translate Text-to-Speech engine. This is an undocumented and unofficial API used in Google Translate. Has a limit of 200 characters per requests which results in slight, but noticeable pauses for longer texts. Google may prevent using this API at any time. This is the enabled choice by default.

  3. Festival. Does not require internet access and provides by far the most robotic voice.

 * **[radio]** Determines the url to the radio stream to play after all sections have been processed.

You can either modify the provided configuration file `alarm.config` or create a new file and pass that to `sound_the_alarm.py` via the `config` argument. To re-create the original configuration file, use the `--init-config` switch.


#### Extending alarm.config with more content
Extending the alarm with more content is simple:
Each content section needs to have `enabled`, `type` and `handler` keys in the configuration file.

 Create a handler for your new content and place it in the `/handlers` folder. It should subclass `AlarmpiContent` and implement the `build` function. This function is where the magic happens: it should store whatever content to pass to the alrm as the `content` attribute. A minimal handler implementation is something like:
 ```
 import apcontent

 class Handler(apcontent.AlarmpiContent):

     def build(self):
         self.content = "Text-to-Speech content goes here"
```
See any of the existing handlers for reference. Set the `handler` option in the configuration file to your new handler without the folder name. Finally set `type` to `content`.

Extending beyond adding new content requires writing new processing logic in `sound_the_alarm.py`.
