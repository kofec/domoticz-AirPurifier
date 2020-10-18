# domoticz-AirPurifier
Domoticz plugin for Xiaomi AirPurifier 2/2S
* Based on repository https://github.com/lrybak/domoticz-airly/
* and script for Samsung TV: https://www.domoticz.com/wiki/Plugins/SamsungTV.html
* and base on repository https://github.com/rytilahti/python-miio

## Installation

```
pip3 install -U python-miio
```

* Make sure your Domoticz instance supports Domoticz Plugin System - see more https://www.domoticz.com/wiki/Using_Python_plugins

* Get plugin data into DOMOTICZ/plugins directory
```
cd YOUR_DOMOTICZ_PATH/plugins
git clone https://github.com/kofec/domoticz-AirPurifier
```
First use script "MyAir.py" to verify if you have needed python modules
e.g:
```
./MyAir.py 192.168.1.1 850000000000000000000000002 --debug
./MyAir.py -h
usage: MyAir.py [-h] [--mode {Auto,Favorite,Idle,Silent}]
                [--favoriteLevel {0,1,2,3,4,5,6,7,8,9,10}] [--power {ON,OFF}]
                [--debug]
                IPaddress token

Script which comunicate with AirPurfier 2/2S.

positional arguments:
  IPaddress             IP address of AirPurfier
  token                 token to login to device

optional arguments:
  -h, --help            show this help message and exit
  --mode {Auto,Favorite,Idle,Silent}
                        choose mode operation
  --favoriteLevel {0,1,2,3,4,5,6,7,8,9,10}
                        choose mode operation
  --power {ON,OFF}      power ON/OFF
  --debug               if define more output is printed
  --led {ON,OFF}        turn led on/off
```
* check where modules was installed and in file plugin.py find and correct below variable (in my case 2 instances) if needed
pathOfPackages = '/usr/local/lib/python3.5/dist-packages'

Restart Domoticz
* Go to Setup > Hardware and create new Hardware with type: AirPurfier
* Enter name (it's up to you), user name and password if define. If not leave it blank

## Update
```
cd YOUR_DOMOTICZ_PATH/plugins/domoticz-AirPurifier
git pull
```
* Restart Domoticz

## Troubleshooting

In case of issues, mostly plugin not visible on plugin list, check logs if plugin system is working correctly. See Domoticz wiki for resolution of most typical installation issues http://www.domoticz.com/wiki/Linux#Problems_locating_Python
