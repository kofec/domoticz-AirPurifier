# domoticz-AirPurifier
Domoticz plugin for Xiaomi AirPurifier 2/2S and Pro (python-miio `zhimi.airpurifier` models: v1-v7, m1, m2, ma1, ma2, sa1, sa2, mc1, mc2)
* Based on repository https://github.com/lrybak/domoticz-airly/
* and script for Samsung TV: https://www.domoticz.com/wiki/Plugins/SamsungTV.html
* and base on repository https://github.com/rytilahti/python-miio

## How it works
The plugin does not import python-miio. Every poll and every command runs `MyAir.py`
in a separate `python3` process, which prints the purifier status as JSON.

python-miio needs `cryptography`, whose Rust bindings (PyO3) can be initialized only
once per process. Domoticz runs all plugins in one process, so importing miio in the
plugin failed with `ImportError: PyO3 modules may only be initialized once per interpreter process`
as soon as a second instance of the plugin, a restart of the plugin or another plugin
using `cryptography` (e.g. TinyTUYA) was involved.

## Installation

```
pip3 install -U python-miio
```
On OpenWrt install `python3-cryptography` with `opkg` first - it cannot be built there.

* Make sure your Domoticz instance supports Domoticz Plugin System - see more https://www.domoticz.com/wiki/Using_Python_plugins

* Get plugin data into DOMOTICZ/plugins directory
```
cd YOUR_DOMOTICZ_PATH/plugins
git clone https://github.com/kofec/domoticz-AirPurifier
```
First use script "MyAir.py" to verify if you have needed python modules - run it with the
`python3` found in `PATH` of the Domoticz service, this is the one the plugin uses.
e.g:
```
./MyAir.py 192.168.1.1 850000000000000000000000002 --debug
./MyAir.py -h
usage: MyAir.py [-h] [--power {ON,OFF}] [--mode {Auto,Favorite,Idle,Silent}]
                [--favoriteLevel {0..17}] [--led {ON,OFF}] [--buzzer {ON,OFF}]
                [--volume {0..100}] [--childLock {ON,OFF}] [--timeout TIMEOUT]
                [--json] [--debug]
                IPaddress [token]

Script which communicates with Xiaomi Air Purifier.

positional arguments:
  IPaddress             IP address of the air purifier
  token                 token to log in to the device (default: $MIIO_TOKEN)

options:
  -h, --help            show this help message and exit
  --power {ON,OFF}      power ON/OFF
  --mode {Auto,Favorite,Idle,Silent}
                        choose operation mode
  --favoriteLevel {0..17}
                        fan level used in Favorite mode
  --led {ON,OFF}        turn LED on/off
  --buzzer {ON,OFF}     turn buzzer on/off (2/2S)
  --volume {0..100}     buzzer volume (Pro)
  --childLock {ON,OFF}  turn child lock on/off
  --timeout TIMEOUT     timeout of a single request in seconds
  --json                print the status as one line of JSON
  --debug               if defined more output is printed
```

Restart Domoticz
* Go to Setup > Hardware and create new Hardware with type: AirPurifier
* Enter name (it's up to you), IP address, token and poll interval

Devices are created when the purifier reports the first value for them, so an unreachable
purifier does not stop the plugin - it retries on the next poll.

## Update
```
cd YOUR_DOMOTICZ_PATH/plugins/domoticz-AirPurifier
git pull
```
* Restart Domoticz

## Troubleshooting

In case of issues, mostly plugin not visible on plugin list, check logs if plugin system is working correctly. See Domoticz wiki for resolution of most typical installation issues http://www.domoticz.com/wiki/Linux#Problems_locating_Python

Set Debug to True in the hardware settings to see the `MyAir.py` command line and its output in the Domoticz log.
