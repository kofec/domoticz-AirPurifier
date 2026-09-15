# A Python plugin for Domoticz to access Xiaomi Air Purifier 2/2S/Pro
#
# Authors:
#  - kofec
#  - Carck
#  - l4m3rx
#  - pawcio
#
# v0.1.0 - initial version,
# fetching data AirPurifier 2 print(MyAir.status()) <AirPurifierStatus power=on,
# aqi=10 temperature=22.9, humidity=35%, mode=OperationMode.Silent, led=True, led_brightness=LedBrightness.Bright,
# buzzer=False, child_lock=False, brightness=None, favorite_level=10, filter_life_remaining=79,
# filter_hours_used=717, use_time=2581642, motor_speed=352>
#
# v0.1.1 - Add initial version of switches, update to nie version of python-miio
#
# v0.1.2 - Code cleanup
#
# v0.1.3 - Improved temperature parser
#
# v0.2.0
#   - Switch to multiple thread model
#   - Change command timeout
#   - Introduce small sleep before update after command
#   - Update device status directly after command
#   - Expose LED status and switch to control the LED from domoticz
#   - Expose Filter statistics to domoticz
# v0.2.1
#   - Expose illuminance to domoticz
# v0.2.2
#   - Update old version definition in xml
#   - Fix set_favorite_level. python-miio library expects int not str.
# v0.2.3
#   - OnStop fix
# v0.3.0
#   - python-miio runs in a separate process (MyAir.py). It needs cryptography,
#     whose PyO3 bindings can be initialized only once per Domoticz process, so
#     importing miio here broke with a second instance, a plugin restart or any
#     other plugin using cryptography (e.g. TinyTUYA)
#   - onStart no longer talks to the device, so an unreachable purifier does not
#     stop the plugin; devices are created on the first successful status
#   - Fixed LED switch, Beep on models with a buzzer (2/2S) and error handling
#   - Switches are updated only when their state changes
#   - Token is not written to the log in debug mode
# v0.3.1
#   - Fix level names of Mode selectors created by the 2017 version
#     (Auto|Silent|Favorite|Idle): Domoticz showed "Auto" for Idle and vice versa
"""
<plugin key="AirPurifier" name="AirPurifier" author="ManyAuthors" version="0.3.1" wikilink="https://github.com/rytilahti/python-miio" externallink="https://github.com/kofec/domoticz-AirPurifier">
    <params>
        <param field="Address" label="IP Address" width="200px" required="true" default="127.0.0.1"/>
        <param field="Mode1" label="AirPurifier Token" default="" width="400px" required="true"/>
        <param field="Mode3" label="Check every x minutes" width="40px" default="15" required="true"/>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true"/>
            </options>
        </param>
    </params>
</plugin>
"""
import Domoticz
import datetime
import json
import os
import queue
import shutil
import subprocess
import threading

PYTHON = shutil.which("python3") or "/usr/bin/python3"
REQUEST_TIMEOUT = 60  # seconds for one MyAir.py run (miio retries timed out requests)

# Do not change unit numbers - they identify existing devices in Domoticz
UNIT_AIR_QUALITY_INDEX      = 1
UNIT_AIR_POLLUTION_LEVEL    = 2
UNIT_TEMPERATURE            = 3
UNIT_HUMIDITY               = 4
UNIT_MOTOR_SPEED            = 5
UNIT_AVERAGE_AQI            = 6

UNIT_POWER                  = 10
UNIT_MODE                   = 11
UNIT_FAVORITE_LEVEL         = 12
UNIT_CHILD_LOCK             = 13
UNIT_BEEP                   = 15

UNIT_LED                    = 20
UNIT_FILTER_WORK_HOURS      = 21
UNIT_FILTER_LIFE_REMAINING  = 22
UNIT_ILLUMINANCE            = 23

# Devices are created the first time the purifier reports a value for them
DEVICES = {
    UNIT_AIR_QUALITY_INDEX:     {"Name": "Air Quality Index", "TypeName": "Custom",
                                 "Options": {"Custom": "1;AQI"}, "Image": 7, "Used": 1},
    UNIT_AVERAGE_AQI:           {"Name": "Average Air Quality Index", "TypeName": "Custom",
                                 "Options": {"Custom": "1;AQI"}, "Image": 7, "Used": 1},
    UNIT_AIR_POLLUTION_LEVEL:   {"Name": "Air pollution Level", "TypeName": "Alert", "Image": 7},
    UNIT_TEMPERATURE:           {"Name": "Temperature", "TypeName": "Temperature"},
    UNIT_HUMIDITY:              {"Name": "Humidity", "TypeName": "Humidity"},
    UNIT_MOTOR_SPEED:           {"Name": "Fan Speed", "TypeName": "Custom",
                                 "Options": {"Custom": "1;RPM"}, "Image": 7},
    UNIT_FILTER_WORK_HOURS:     {"Name": "Filter work hours", "TypeName": "Custom",
                                 "Options": {"Custom": "1;h"}, "Image": 7},
    UNIT_FILTER_LIFE_REMAINING: {"Name": "Filter life remaining", "TypeName": "Custom",
                                 "Options": {"Custom": "1;%"}, "Image": 7, "Used": 1},
    UNIT_ILLUMINANCE:           {"Name": "Illuminance sensor", "TypeName": "Illumination", "Used": 1},

    UNIT_POWER:                 {"Name": "Power", "TypeName": "Switch", "Image": 7},
    UNIT_MODE:                  {"Name": "Mode", "TypeName": "Selector Switch", "Switchtype": 18, "Image": 7,
                                 "Options": {"LevelActions": "|||",
                                             "LevelNames": "Idle|Silent|Favorite|Auto",
                                             "LevelOffHidden": "false",
                                             "SelectorStyle": "0"}},
    UNIT_FAVORITE_LEVEL:        {"Name": "Fan Favorite level", "TypeName": "Selector Switch", "Switchtype": 18,
                                 "Image": 7,
                                 "Options": {"LevelActions": "|" * 16,
                                             "LevelNames": "|".join(str(i) for i in range(1, 18)),
                                             "LevelOffHidden": "false",
                                             "SelectorStyle": "0"}},
    UNIT_CHILD_LOCK:            {"Name": "Child Lock", "TypeName": "Switch", "Image": 7},
    UNIT_BEEP:                  {"Name": "Beep", "TypeName": "Switch", "Image": 7},
    UNIT_LED:                   {"Name": "Fan LED", "TypeName": "Switch", "Image": 7},
}

# Selector level of UNIT_MODE <-> python-miio OperationMode name
MODE_LEVELS = {"Idle": 0, "Silent": 10, "Favorite": 20, "Auto": 30}
LEVEL_MODES = {level: mode for mode, level in MODE_LEVELS.items()}

# AQI -> Domoticz Alert level, based on https://en.wikipedia.org/wiki/Air_quality_index
AQI_LEVELS = (
    (50,  1, "Great air quality"),
    (100, 1, "Good air quality"),
    (150, 2, "Average air quality"),
    (200, 3, "Poor air quality"),
    (300, 4, "Bad air quality"),
)

L10N = {
    'pl': {
        "Air Quality Index":
            "Jakość powietrza",
        "Average Air Quality Index":
            "Średnia wartość AQI",
        "Air pollution Level":
            "Zanieczyszczenie powietrza",
        "Temperature":
            "Temperatura",
        "Humidity":
            "Wilgotność",
        "Fan Speed":
            "Prędkość wiatraka",
        "Filter work hours":
            "Czas pracy filtra",
        "Filter life remaining":
            "Pozostała żywotność filtra",
        "Illuminance sensor":
            "Natężenie światła",
        "Great air quality":
            "Bardzo dobra jakość powietrza",
        "Good air quality":
            "Dobra jakość powietrza",
        "Average air quality":
            "Przeciętna jakość powietrza",
        "Poor air quality":
            "Słaba jakość powietrza",
        "Bad air quality":
            "Zła jakość powietrza",
        "Really bad air quality":
            "Bardzo zła jakość powietrza",
    },
    'en': {}
}


def _(key):
    try:
        return L10N[Settings["Language"]][key]
    except KeyError:
        return key


def pollution_level(aqi):
    for limit, level, text in AQI_LEVELS:
        if aqi < limit:
            return level, text
    return 4, "Really bad air quality"


def humidity_status(humidity):
    """Domoticz humidity status: 0 normal, 1 comfortable, 2 dry, 3 wet."""
    if humidity < 40:
        return 2
    if humidity <= 60:
        return 0
    if humidity <= 70:
        return 1
    return 3


class BasePlugin:

    def __init__(self):
        self.myAir = None
        self.pollInterval = datetime.timedelta(minutes=15)
        self.nextPoll = datetime.datetime.now()
        self.failed = False
        self.hasVolume = False  # Pro reports a volume, 2/2S only a buzzer on/off
        self.messageQueue = queue.Queue()
        self.messageThread = threading.Thread(name="QueueThreadPurifier", target=self.handleMessage)

    def onStart(self):
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(1)
            DumpConfigToLog()
        else:
            Domoticz.Debugging(0)

        self.myAir = os.path.join(Parameters["HomeFolder"], "MyAir.py")
        self.pollInterval = datetime.timedelta(minutes=max(1, int(Parameters["Mode3"])))
        FixModeLevelNames()
        self.messageThread.start()

        Domoticz.Heartbeat(20)
        self.onHeartbeat()

    def onStop(self):
        # Drop pending requests and wait for the running one: Domoticz aborts
        # if a plugin thread is still alive when onStop returns
        while True:
            try:
                self.messageQueue.get_nowait()
            except queue.Empty:
                break
        self.messageQueue.put(None)
        if self.messageThread.is_alive():
            self.messageThread.join()
        Domoticz.Debugging(0)

    def onHeartbeat(self):
        now = datetime.datetime.now()
        if now >= self.nextPoll:
            self.nextPoll = now + self.pollInterval
            self.messageQueue.put([])  # status only

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("onCommand called for Unit %d: Parameter '%s', Level: %s" % (Unit, Command, Level))
        onOff = "ON" if str(Command).upper() == "ON" else "OFF"

        if Unit == UNIT_POWER:
            args = ["--power", onOff]
        elif Unit == UNIT_MODE and Level in LEVEL_MODES:
            args = ["--mode", LEVEL_MODES[Level]]
        elif Unit == UNIT_FAVORITE_LEVEL:
            args = ["--favoriteLevel", str(int(Level) // 10 + 1)]
        elif Unit == UNIT_CHILD_LOCK:
            args = ["--childLock", onOff]
        elif Unit == UNIT_BEEP:
            args = ["--volume", "50" if onOff == "ON" else "0"] if self.hasVolume else ["--buzzer", onOff]
        elif Unit == UNIT_LED:
            args = ["--led", onOff]
        else:
            Domoticz.Error("Unsupported command for Unit %d: '%s', Level: %s" % (Unit, Command, Level))
            return

        self.messageQueue.put(args)

    def handleMessage(self):
        Domoticz.Debug("Entering message handler")
        while True:
            args = self.messageQueue.get()
            if args is None:
                Domoticz.Debug("Exiting message handler")
                break
            try:
                self.updateDevices(self.runMyAir(args))
                if self.failed:
                    Domoticz.Log("Air purifier responds again")
                self.failed = False
            except Exception as e:
                # An unplugged purifier should not flood the log on every poll
                if args or not self.failed:
                    Domoticz.Error("Request %s failed: %s" % (args or "status", e))
                else:
                    Domoticz.Debug("Status request failed: %s" % e)
                self.failed = True

    def runMyAir(self, args):
        """Run MyAir.py in its own Python process and return the status it reports."""
        cmd = [PYTHON, self.myAir, Parameters["Address"], "--json"] + args
        Domoticz.Debug("Running " + " ".join(cmd))
        env = dict(os.environ, MIIO_TOKEN=Parameters["Mode1"])
        proc = subprocess.run(cmd, env=env, capture_output=True, encoding="utf-8", errors="replace",
                              timeout=REQUEST_TIMEOUT)
        stderr = proc.stderr.strip()
        if stderr:
            Domoticz.Debug("MyAir.py stderr: " + stderr)
        try:
            reply = json.loads(proc.stdout.strip().splitlines()[-1])
        except (IndexError, ValueError):
            raise RuntimeError("no reply from MyAir.py (exit code %d): %s"
                               % (proc.returncode, stderr.splitlines()[-1] if stderr else ""))
        if "error" in reply:
            raise RuntimeError(reply["error"])
        return reply["status"]

    def updateDevices(self, status):
        Domoticz.Debug("Status: " + str(status))
        self.hasVolume = status["volume"] is not None

        # Sensors are updated on every poll, so Domoticz does not mark them as timed out
        for unit, field in ((UNIT_AIR_QUALITY_INDEX, "aqi"),
                            (UNIT_AVERAGE_AQI, "average_aqi"),
                            (UNIT_TEMPERATURE, "temperature"),
                            (UNIT_MOTOR_SPEED, "motor_speed"),
                            (UNIT_FILTER_WORK_HOURS, "filter_hours_used"),
                            (UNIT_FILTER_LIFE_REMAINING, "filter_life_remaining"),
                            (UNIT_ILLUMINANCE, "illuminance")):
            if status[field] is not None:
                UpdateDevice(unit, 0, str(status[field]), AlwaysUpdate=True)

        if status["aqi"] is not None:
            level, text = pollution_level(status["aqi"])
            UpdateDevice(UNIT_AIR_POLLUTION_LEVEL, level, _(text), AlwaysUpdate=True)

        if status["humidity"] is not None:
            humidity = int(round(status["humidity"]))
            UpdateDevice(UNIT_HUMIDITY, humidity, str(humidity_status(humidity)), AlwaysUpdate=True)

        # Switches
        if status["power"] is not None:
            UpdateDevice(UNIT_POWER, *OnOff(status["power"] == "on"))

        if status["mode"] in MODE_LEVELS:
            level = MODE_LEVELS[status["mode"]]
            UpdateDevice(UNIT_MODE, level, str(level))
        else:
            Domoticz.Debug("Mode not supported by the selector: " + str(status["mode"]))

        if status["favorite_level"] is not None:
            UpdateDevice(UNIT_FAVORITE_LEVEL, 1, str(max(status["favorite_level"] - 1, 0) * 10))

        if status["led"] is not None:
            UpdateDevice(UNIT_LED, *OnOff(status["led"]))

        if status["child_lock"] is not None:
            UpdateDevice(UNIT_CHILD_LOCK, *OnOff(status["child_lock"]))

        beep = status["volume"] > 0 if self.hasVolume else status["buzzer"]
        if beep is not None:
            UpdateDevice(UNIT_BEEP, *OnOff(beep))


global _plugin
_plugin = BasePlugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onStop():
    global _plugin
    _plugin.onStop()


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()


# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "" and x != "Mode1":  # Mode1 is the device token
            Domoticz.Debug("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))


def FixModeLevelNames():
    # Mode selectors created by the 2017 version keep its level names
    # (Auto|Silent|Favorite|Idle, level 0 hidden), while commands use
    # MODE_LEVELS - so Domoticz showed "Auto" for Idle and "Idle" for Auto
    if UNIT_MODE not in Devices:
        return
    device = Devices[UNIT_MODE]
    expected = DEVICES[UNIT_MODE]["Options"]
    if device.Options.get("LevelNames") == expected["LevelNames"]:
        return
    Domoticz.Log("Fixing level names of '%s': '%s' -> '%s'"
                 % (device.Name, device.Options.get("LevelNames"), expected["LevelNames"]))
    options = dict(device.Options, LevelNames=expected["LevelNames"], LevelActions=expected["LevelActions"],
                   LevelOffHidden=expected["LevelOffHidden"])
    device.Update(nValue=device.nValue, sValue=device.sValue, Options=options)


def OnOff(enabled):
    return (1, "On") if enabled else (0, "Off")


def UpdateDevice(Unit, nValue, sValue, AlwaysUpdate=False):
    # Create the device on first use (also after the user deleted it)
    if Unit not in Devices:
        options = dict(DEVICES[Unit], Name=_(DEVICES[Unit]["Name"]))
        Domoticz.Log("Creating device Unit=%d; Name='%s'" % (Unit, options["Name"]))
        Domoticz.Device(Unit=Unit, **options).Create()
        if Unit not in Devices:
            return
    if AlwaysUpdate or Devices[Unit].nValue != nValue or Devices[Unit].sValue != sValue:
        Devices[Unit].Update(nValue=nValue, sValue=sValue)
        Domoticz.Debug("Update %d:'%s' (%s)" % (nValue, sValue, Devices[Unit].Name))
