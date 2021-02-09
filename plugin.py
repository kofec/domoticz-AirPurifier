# A Python plugin for Domoticz to access AirPurifier 2
#
# Authors:
#  - kofec
#  - Carck
#  - l4m3rx
#  - pawcio
#
# TODO: Update text sensors only when changed
#
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
#
"""
<plugin key="AirPurifier" name="AirPurifier" author="ManyAuthors" version="0.2.2" wikilink="https://github.com/rytilahti/python-miio" externallink="https://github.com/kofec/domoticz-AirPurifier">
    <params>
		<param field="Address" label="IP Address" width="200px" required="true" default="127.0.0.1"/>
		<param field="Mode1" label="AirPurifier Token" default="" width="400px" required="true"  />
        <param field="Mode3" label="Check every x minutes" width="40px" default="15" required="true" />
		<param field="Mode6" label="Debug" width="75px">
			<options>
				<option label="True" value="Debug"/>
				<option label="False" value="Normal" default="true" />
			</options>
		</param>
    </params>
</plugin>
"""
import Domoticz
import sys
import datetime
import socket
import site
import time
path=''
path=site.getsitepackages()
for i in path:
    sys.path.append(i)

import glob
site_path = '/usr/lib/python3.9/site-packages'
sys.path.append(site_path)
eggs = [f for f in glob.glob(site_path + "**/*.egg", recursive=False)]
for f in eggs:
    sys.path.append(f)

import threading
import queue

import miio.airpurifier
from miio import Device, DeviceException
from miio.airpurifier import OperationMode
from functools import partial

L10N = {
    'pl': {
        "Air Quality Index":
            "Jakość powietrza",
        "Avarage Air Quality Index":
            "Średnia wartość AQI",
        "Air pollution Level":
            "Zanieczyszczenie powietrza",
        "Temperature":
            "Temperatura",
        "Humidity":
            "Wilgotność",
        "Fan Speed":
            "Prędkość wiatraka",
        "Favorite Fan Level":
            "Ulubiona prędkość wiatraka",
        "Sensor information":
            "Informacje o stacji",
        "Device Unit=%(Unit)d; Name='%(Name)s' already exists":
            "Urządzenie Unit=%(Unit)d; Name='%(Name)s' już istnieje",
        "Creating device Name=%(Name)s; Unit=%(Unit)d; ; TypeName=%(TypeName)s; Used=%(Used)d":
            "Tworzę urządzenie Name=%(Name)s; Unit=%(Unit)d; ; TypeName=%(TypeName)s; Used=%(Used)d",
        "%(Vendor)s - %(Address)s, %(Locality)s<br/>Station founder: %(sensorFounder)s":
            "%(Vendor)s - %(Address)s, %(Locality)s<br/>Sponsor stacji: %(sensorFounder)s",
        "%(Vendor)s - %(Locality)s %(StreetNumber)s<br/>Station founder: %(sensorFounder)s":
            "%(Vendor)s - %(Locality)s %(StreetNumber)s<br/>Sponsor stacji: %(sensorFounder)s",
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
        "Sensor id (%(sensor_id)d) not exists":
            "Sensor (%(sensor_id)d) nie istnieje",
        "Not authorized":
            "Brak autoryzacji",
        "Starting device update":
            "Rozpoczynanie aktualizacji urządzeń",
        "Update unit=%d; nValue=%d; sValue=%s":
            "Aktualizacja unit=%d; nValue=%d; sValue=%s",
        "Bad air today!":
            "Zła jakość powietrza",
        "Enter correct airly API key - get one on https://developer.airly.eu":
            "Wprowadź poprawny klucz api -  pobierz klucz na stronie https://developer.airly.eu",
        "Awaiting next pool: %s":
            "Oczekiwanie na następne pobranie: %s",
        "Next pool attempt at: %s":
            "Następna próba pobrania: %s",
        "Connection to airly api failed: %s":
            "Połączenie z airly api nie powiodło się: %s",
        "Unrecognized error: %s":
            "Nierozpoznany błąd: %s"
    },
    'en': { }
}

def _(key):
    try:
        return L10N[Settings["Language"]][key]
    except KeyError:
        return key

class UnauthorizedException(Exception):
    def __init__(self, expression, message):
        self.expression = expression
        self.message = message

class SensorNotFoundException(Exception):
    def __init__(self, expression, message):
        self.expression = expression
        self.message = message

class ConnectionErrorException(Exception):
    def __init__(self, expression, message):
        self.expression = expression
        self.message = message

class BasePlugin:
    enabled = False
    MyAir = None

    def __init__(self):
        # Consts
        self.version = "0.2.3"

        self.EXCEPTIONS = {
            "SENSOR_NOT_FOUND":     1,
            "UNAUTHORIZED":         2,
        }

        self.debug = False
        self.inProgress = False

        # Do not change below UNIT constants!
        self.UNIT_AIR_QUALITY_INDEX     = 1
        self.UNIT_AIR_POLLUTION_LEVEL   = 2
        self.UNIT_TEMPERATURE           = 3
        self.UNIT_HUMIDITY              = 4
        self.UNIT_MOTOR_SPEED           = 5
        self.UNIT_AVARAGE_AQI           = 6

        self.UNIT_POWER_CONTROL         = 10
        self.UNIT_MODE_CONTROL          = 11
        self.UNIT_MOTOR_SPEED_FAVORITE  = 12
        self.UNIT_CHILD_LOCK            = 13
        self.UNIT_BEEP                  = 15

        self.UNIT_LED                   = 20
        self.FILTER_WORK_HOURS          = 21
        self.FILTER_LIFE_REMAINING      = 22
        self.UNIT_ILLUMINANCE_SENSOR    = 23


        self.nextpoll = datetime.datetime.now()
        self.messageQueue = queue.Queue()
        self.messageThread = threading.Thread(name="QueueThreadPurifier", target=BasePlugin.handleMessage, args=(self,))
        return

    def connectIfNeeded(self):
        for i in range(1, 6):
            try:
                if None == self.MyAir:
                    self.MyAir = miio.airpurifier.AirPurifier(Parameters["Address"], Parameters["Mode1"])
                break;
            except miio.airpurifier.AirPurifierException as e:
                Domoticz.Error("connectIfNeeded: " + str(e))
                self.MyAir = None

    def handleMessage(self):
        Domoticz.Debug("Entering message handler")
        while True:
            try:
                Message = self.messageQueue.get(block=True)
                if Message is None:
                    Domoticz.Debug("Exiting message handler")
                    self.messageQueue.task_done()
                    break

                self.connectIfNeeded()

                if (Message["Type"] == "onHeartbeat"):
                    self.onHeartbeatInternal(Message["Fetch"])
                elif (Message["Type"] == "onCommand"):
                    self.onCommandInternal(Message["Mthd"], *Message["Arg"])

                self.messageQueue.task_done()

            except Exception as err:
                Domoticz.Error("handleMessage: "+str(err))
                self.MyAir = None
                with self.messageQueue.mutex:
                   	self.messageQueue.queue.clear()

    def onStart(self):
        #Domoticz.Log("path: " + str(sys.path))
        Domoticz.Debug("onStart called")
        if Parameters["Mode6"] == 'Debug':
            self.debug = True
            Domoticz.Debugging(1)
            DumpConfigToLog()
        else:
            Domoticz.Debugging(0)

        self.connectIfNeeded()
        self.MyAir._timeout = 1
        self.messageThread.start()

        Domoticz.Heartbeat(20)
        self.pollinterval = int(Parameters["Mode3"]) * 60

        res = self.MyAir.status()
        Domoticz.Log(str(res))
        self.variables = {
            self.FILTER_LIFE_REMAINING: {
                "Name":     _("Filter life remaining"),
                "TypeName": "Custom",
                "Options":  {"Custom": "1;%s" % "%"},
                "Image":    7,
                "Used":     1,
                "nValue":   0,
                "sValue":   None,
            },
            self.FILTER_WORK_HOURS: {
                "Name":     _("Filter work hours"),
                "TypeName": "Custom",
                "Options":  {"Custom": "1;%s" % "h"},
                "Image":    7,
                "Used":     0,
                "nValue":   0,
                "sValue":   0,
            },
            self.UNIT_AIR_QUALITY_INDEX: {
                "Name":     _("Air Quality Index"),
                "TypeName": "Custom",
                "Options":  {"Custom": "1;%s" % "AQI"},
                "Image":    7,
                "Used":     1,
                "nValue":   0,
                "sValue":   None,
            },
            self.UNIT_AVARAGE_AQI: {
                "Name":     _("Avarage Air Quality Index"),
                "TypeName": "Custom",
                "Options": {"Custom": "1;%s" % "AQI"},
                "Image": 7,
                "Used": 1,
                "nValue": 0,
                "sValue": None,
            },
            self.UNIT_AIR_POLLUTION_LEVEL: {
                "Name":     _("Air pollution Level"),
                "TypeName": "Alert",
                "Image":    7,
                "Used":     0,
                "nValue":   0,
                "sValue":   None,
            },
            self.UNIT_TEMPERATURE: {
                "Name":     _("Temperature"),
                "TypeName": "Temperature",
                "Used":     0,
                "nValue":   0,
                "sValue":   None,
            },
            self.UNIT_HUMIDITY: {
                "Name":     _("Humidity"),
                "TypeName": "Humidity",
                "Used":     0,
                "nValue":   0,
                "sValue":   None,
            },
            self.UNIT_MOTOR_SPEED: {
                "Name":     _("Fan Speed"),
                "TypeName": "Custom",
                "Options":  {"Custom": "1;%s" % "RPM"},
                "Image":    7,
                "Used":     0,
                "nValue":   0,
                "sValue":   None,
            },
            self.UNIT_CHILD_LOCK: {
                "Name":     _("Child Lock"),
                "TypeName": "Switch",
                "Image":    7,
                "Used":     0,
                "nValue":   0,
                "sValue":   None,
            },
            self.UNIT_BEEP: {
                "Name":     _("Beep"),
                "TypeName": "Switch",
                "Image":    7,
                "Used":     0,
                "nValue":   0,
                "sValue":   None,
            },
        }
        if res.illuminance is not None:
            self.variables.update({self.UNIT_ILLUMINANCE_SENSOR: {
                "Name":     _("Illuminance sensor"),
                "TypeName": "Custom",
                "Options":  {"Custom": "1;%s" % "lux"},
                "Image":    7,
                "Used":     1,
                "nValue":   0,
                "sValue":   None,
            }})
            if (self.UNIT_ILLUMINANCE_SENSOR in Devices):
                Domoticz.Log("Device UNIT_ILLUMINANCE_SENSOR with id " + str(self.UNIT_ILLUMINANCE_SENSOR) + " exist")
            else:
                Domoticz.Device(Name="Illuminance sensor", Unit=self.UNIT_ILLUMINANCE_SENSOR, Type=244, Subtype=73,
                                Switchtype=7, Image=7).Create()

        # Create switches - if not exist
        if self.UNIT_POWER_CONTROL in Devices:
            Domoticz.Log("Device UNIT_POWER_CONTROL with id " + str(self.UNIT_POWER_CONTROL) + " exist")
        else:
            Domoticz.Device(Name="Power", Unit=self.UNIT_POWER_CONTROL, TypeName="Switch", Image=7).Create()

        if self.UNIT_CHILD_LOCK in Devices:
            Domoticz.Log("Device UNIT_CHILD_LOCK with id " + str(self.UNIT_CHILD_LOCK) + " exist")
        else:
            Domoticz.Device(Name="Child Lock", Unit=self.UNIT_CHILD_LOCK, TypeName="Switch", Image=7).Create()

        if self.UNIT_BEEP in Devices:
            Domoticz.Log("Device UNIT_BEEP with id " + str(self.UNIT_BEEP) + " exist")
        else:
            Domoticz.Device(Name="Beep", Unit=self.UNIT_BEEP, TypeName="Switch", Image=7).Create()

        if self.UNIT_MODE_CONTROL in Devices:
            Domoticz.Log("Device UNIT_MODE_CONTROL with id " + str(self.UNIT_MODE_CONTROL) + " exist")
        else:
            Options = {"LevelActions": "||||",
                    "LevelNames": "Idle|Silent|Favorite|Auto",
                    "LevelOffHidden": "false",
                    "SelectorStyle": "0"
                    }
            Domoticz.Device(Name="Mode", Unit=self.UNIT_MODE_CONTROL, TypeName="Selector Switch", Switchtype=18,
                            Image=7,
                            Options=Options).Create()

        if self.UNIT_MOTOR_SPEED_FAVORITE in Devices:
            Domoticz.Log("Device UNIT_MOTOR_SPEED_FAVORITE with id " + str(self.UNIT_MOTOR_SPEED_FAVORITE) + " exist")
        else:
            Options = {"LevelActions": "|||||||||||||||||",
                    "LevelNames": "1|2|3|4|5|6|7|8|9|10|11|12|13|14|15|16|17",
                    "LevelOffHidden": "false",
                    "SelectorStyle": "0"
                    }
            Domoticz.Device(Name="Fan Favorite level", Unit=self.UNIT_MOTOR_SPEED_FAVORITE, TypeName="Selector Switch", Switchtype=18,
                            Image=7,
                            Options=Options).Create()
        if (self.UNIT_LED in Devices):
            Domoticz.Log("Device UNIT_LED with id " + str(self.UNIT_LED) + " exist")
        else:
            Domoticz.Device(Name="Fan LED", Unit=self.UNIT_LED, TypeName="Switch", Image=7).Create()

        self.onHeartbeat(fetch=False)

    def onStop(self):
        Domoticz.Log("onStop called")

        with self.messageQueue.mutex:
            self.messageQueue.queue.clear()

        # signal queue thread to exit
        self.messageQueue.put(None)
        Domoticz.Log("Clearing message queue ...")
        self.messageQueue.join()

        # Wait until queue thread has exited
        Domoticz.Log("Threads still active: "+str(threading.active_count())+", should be 1.")
        while (threading.active_count() > 1):
            for thread in threading.enumerate():
                if (thread.name != threading.current_thread().name):
                    Domoticz.Log("'"+thread.name+"' is still running, waiting otherwise Domoticz will abort on plugin exit.")
            time.sleep(1.0)

        Domoticz.Debugging(0)

    def onConnect(self, Status, Description):
        Domoticz.Log("onConnect called")

    def onMessage(self, Data, Status, Extra):
        Domoticz.Log("onMessage called")

    def onCommandInternal(self, func, *arg):
        try:
            stat = func(*arg)
            Domoticz.Log(str(stat))

            self.onHeartbeat(fetch=True)
        except miio.airpurifier.AirPurifierException as e:
            Domoticz.Log("Something fail: " + e.output.decode())
            self.onHeartbeat(fetch=False)
        except Exception as e:
            Domoticz.Error(_("Unrecognized command error: %s") % str(e))

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))
#        self.messageQueue.put({"Type": "Command", "Unit": Unit, "Command": Command, "Level": Level, "Hue": Hue})

        mthd = None
        arg = []

        if Unit == self.UNIT_POWER_CONTROL:
            mthd = self.MyAir.on if str(Command).upper() == "ON" else self.MyAir.off
        elif Unit == self.UNIT_MODE_CONTROL and int(Level) == 0:
            mthd = self.MyAir.set_mode
            arg = [OperationMode.Idle]
        elif Unit == self.UNIT_MODE_CONTROL and int(Level) == 10:
            mthd = self.MyAir.set_mode
            arg = [OperationMode.Silent]
        elif Unit == self.UNIT_MODE_CONTROL and int(Level) == 20:
            mthd = self.MyAir.set_mode
            arg = [OperationMode.Favorite]
        elif Unit == self.UNIT_MODE_CONTROL and int(Level) == 30:
            mthd = self.MyAir.set_mode
            arg = [OperationMode.Auto]
        elif Unit == self.UNIT_MOTOR_SPEED_FAVORITE:
            mthd = self.MyAir.set_favorite_level
            arg = [int(int(Level)/10 + 1)]
        elif Unit == self.UNIT_CHILD_LOCK:
            mthd = self.MyAir.set_child_lock
            arg = [True if str(Command).upper() == "TRUE" or str(Command).upper() == "ON" else False]
        elif Unit == self.UNIT_BEEP:
            mthd = self.MyAir.set_volume
            arg = [50 if str(Command).upper() == "TRUE" or str(Command).upper() == "ON" else 0]
        elif Unit == self.UNIT_LED:
            enabled = str(Command).upper() == "ON"
            mthd = self.myAir.set_led(enabled)
            self.UpdateLedStatus(enabled)
        else:
            Domoticz.Log("onCommand called not found")

        if None == mthd:
            return

        Domoticz.Log(str({"Type":"onCommand", "Mthd":mthd, "Arg":arg}))
        self.messageQueue.put({"Type":"onCommand", "Mthd":mthd, "Arg":arg})


    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(
            Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self):
        Domoticz.Log("onDisconnect called")

    def postponeNextPool(self, seconds=3600):
        self.nextpoll = (datetime.datetime.now() + datetime.timedelta(seconds=seconds))
        return self.nextpoll

    def createDevice(self, key=None):
        """create Domoticz virtual device"""

        def createSingleDevice(key):
            """inner helper function to handle device creation"""

            item = self.variables[key]
            _unit = key
            _name = item['Name']

            # skip if already exists
            if key in Devices:
                Domoticz.Debug(_("Device Unit=%(Unit)d; Name='%(Name)s' already exists") % {'Unit': key, 'Name': _name})
                return

            try:
                _options = item['Options']
            except KeyError:
                _options = {}

            _typename = item['TypeName']

            try:
                _used = item['Used']
            except KeyError:
                _used = 0

            try:
                _image = item['Image']
            except KeyError:
                _image = 0

            Domoticz.Debug(_("Creating device Name=%(Name)s; Unit=%(Unit)d; ; TypeName=%(TypeName)s; Used=%(Used)d") % {
                               'Name':     _name,
                               'Unit':     _unit,
                               'TypeName': _typename,
                               'Used':     _used,
                           })

            Domoticz.Device(
                Name=_name,
                Unit=_unit,
                TypeName=_typename,
                Image=_image,
                Options=_options,
                Used=_used
            ).Create()

        if key:
            createSingleDevice(key)
        else:
            for k in self.variables.keys():
                createSingleDevice(k)

    def UpdateLedStatus(self, enabled):
        if enabled:
            UpdateDevice(self.UNIT_LED, 1, "Fan LED ON")
        else:
            UpdateDevice(self.UNIT_LED, 0, "Fan LED OFF")

    def onHeartbeat(self, fetch=False):
        Domoticz.Debug("onHeartbeat called")
        self.messageQueue.put({"Type": "onHeartbeat", "Fetch": fetch})
        return True

    def onHeartbeatInternal(self, fetch=False):
        now = datetime.datetime.now()
        if fetch == False:
            if now < self.nextpoll:
                Domoticz.Debug(_("Awaiting next pool: %s") % str(self.nextpoll))
                return

        # Set next pool time
        self.postponeNextPool(seconds=self.pollinterval)

        try:
            res = self.MyAir.status()
            Domoticz.Log(str(res))
            # check if another thread is not running
            # and time between last fetch has elapsed
            self.inProgress = True

            try:
                if str(res.mode) == "OperationMode.Idle":
                    UpdateDevice(self.UNIT_MODE_CONTROL, 0, '0')
                elif str(res.mode) == "OperationMode.Silent":
                    UpdateDevice(self.UNIT_MODE_CONTROL, 10, '10')
                elif str(res.mode) == "OperationMode.Favorite":
                    UpdateDevice(self.UNIT_MODE_CONTROL, 20, '20')
                elif str(res.mode) == "OperationMode.Auto":
                    UpdateDevice(self.UNIT_MODE_CONTROL, 30, '30')
                else:
                    Domoticz.Log("Wrong state for UNIT_MODE_CONTROL: " + str(res.mode))
            except KeyError:
                Domoticz.Log("Cannot update: UNIT_MODE_CONTROL") 
                pass  # No mode value

            UpdateDevice(self.UNIT_MOTOR_SPEED_FAVORITE, 1, str(int(int(res.favorite_level)-1)*10))

            try:
                self.variables[self.UNIT_AVARAGE_AQI]['sValue'] = str(res.average_aqi)
            except KeyError:
                pass  # No airQualityIndex value

            try:
                self.variables[self.UNIT_AIR_QUALITY_INDEX]['sValue'] = str(res.aqi)
            except KeyError:
                pass  # No airQualityIndex value

            try:
                self.variables[self.UNIT_TEMPERATURE]['sValue'] = str(res.temperature)
            except KeyError:
                pass  # No temperature value

            try:
                self.variables[self.UNIT_MOTOR_SPEED]['sValue'] = str(res.motor_speed)
            except KeyError:
                pass  # No motor_speed value

            try:
                if str(res.power) == "on":
                    UpdateDevice(self.UNIT_POWER_CONTROL, 1, "AirPurifier ON")
                elif str(res.power) == "off":
                    UpdateDevice(self.UNIT_POWER_CONTROL, 0, "AirPurifier OFF")
            except KeyError:
                pass  # No power value

            #       AQI	Air Pollution - base on https://en.wikipedia.org/wiki/Air_quality_index
            #       Level	Health Implications
            #       0–50	    Excellent
            #       51–100	Good
            #       101–150	Lightly Polluted
            #       151–200	Moderately Polluted
            #       201–300	Heavily Polluted
            #       300+	Severely Polluted

            # sometimes response has 10 times lower value - uncomment below
            # res.aqi = int(res.aqi) * 10
            if int(res.aqi) < 50:
                pollutionLevel = 1  # green
                pollutionText = _("Great air quality")
            elif int(res.aqi) < 100:
                pollutionLevel = 1  # green
                pollutionText = _("Good air quality")
            elif int(res.aqi) < 150:
                pollutionLevel = 2  # yellow
                pollutionText = _("Average air quality")
            elif int(res.aqi) < 200:
                pollutionLevel = 3  # orange
                pollutionText = _("Poor air quality")
            elif int(res.aqi) < 300:
                pollutionLevel = 4  # red
                pollutionText = _("Bad air quality")
            elif int(res.aqi) >= 300:
                pollutionLevel = 4  # red
                pollutionText = _("Really bad air quality")
            else:
                pollutionLevel = 0


            self.variables[self.UNIT_AIR_POLLUTION_LEVEL]['nValue'] = pollutionLevel
            self.variables[self.UNIT_AIR_POLLUTION_LEVEL]['sValue'] = pollutionText

            try:
                humidity = int(round(res.humidity))
                if humidity < 40:
                    humidity_status = 2  # dry humidity
                elif 40 <= humidity <= 60:
                    humidity_status = 0  # normal humidity
                elif 40 < humidity <= 70:
                    humidity_status = 1  # comfortable humidity
                else:
                    humidity_status = 3  # wet humidity

                self.variables[self.UNIT_HUMIDITY]['nValue'] = humidity
                self.variables[self.UNIT_HUMIDITY]['sValue'] = str(humidity_status)

            except KeyError:
                pass  # No humidity value

            try:
                self.variables[self.FILTER_WORK_HOURS]['nValue'] = res.filter_hours_used
                self.variables[self.FILTER_WORK_HOURS]['sValue'] = str(res.filter_hours_used)
            except KeyError:
                pass  # No filter_hours_used

            try:
                self.variables[self.FILTER_LIFE_REMAINING]['nValue'] = res.filter_life_remaining
                self.variables[self.FILTER_LIFE_REMAINING]['sValue'] = str(res.filter_life_remaining)
            except KeyError:
                pass  # No filter_life_remaining

            try:
                self.variables[self.UNIT_ILLUMINANCE_SENSOR]['nValue'] = res.illuminance
                self.variables[self.UNIT_ILLUMINANCE_SENSOR]['sValue'] = str(res.illuminance)
            except KeyError:
                pass  # No illuminance

            self.doUpdate()

            try:
                self.UpdateLedStatus(bool(res.led))
            except KeyError:
                pass  # No led value
	   
            # child lock
            if res.child_lock:
                UpdateDevice(self.UNIT_CHILD_LOCK, 1, "ChildLock ON")
            else:
                UpdateDevice(self.UNIT_CHILD_LOCK, 0, "ChildLock OFF")

             # beep
            if res.volume is not None and res.volume > 0:
                UpdateDevice(self.UNIT_BEEP, 1, "Beep ON")
            else:
                UpdateDevice(self.UNIT_BEEP, 0, "Beep OFF")

        except miio.airpurifier.AirPurifierException as e:
            Domoticz.Error("onHeartbeatInternal: " + str(e))
            self.MyAir = None
            return
        except Exception as e:
            Domoticz.Error(_("Unrecognized heartbeat error: %s") % str(e))
        finally:
            self.inProgress = False
        if Parameters["Mode6"] == 'Debug':
            Domoticz.Debug("onHeartbeat finished")


    def doUpdate(self):
        Domoticz.Log(_("Starting device update"))
        for unit in self.variables:
            Domoticz.Debug(str(self.variables[unit]))
            nV = self.variables[unit]['nValue']
            sV = self.variables[unit]['sValue']

            # cast float to str
            if isinstance(sV, float):
                sV = str(float("{0:.1f}".format(sV))).replace('.', ',')

            # Create device if required
            if sV:
                self.createDevice(key=unit)
                if unit in Devices:
                    Domoticz.Log(_("Update unit=%d; nValue=%d; sValue=%s") % (unit, nV, sV))
                    Devices[unit].Update(nValue=nV, sValue=sV)


global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Status, Description):
    global _plugin
    _plugin.onConnect(Status, Description)

def onMessage(Data, Status, Extra):
    global _plugin
    _plugin.onMessage(Data, Status, Extra)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect():
    global _plugin
    _plugin.onDisconnect()

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

    # Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return

def UpdateDevice(Unit, nValue, sValue):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if (Unit in Devices):
        if (Devices[Unit].nValue != nValue) or (Devices[Unit].sValue != sValue):
            Devices[Unit].Update(nValue=nValue, sValue=str(sValue))
            Domoticz.Log("Update " + str(nValue) + ":'" + str(sValue) + "' (" + Devices[Unit].Name + ")")
    return
