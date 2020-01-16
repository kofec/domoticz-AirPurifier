# domoticz-AirPurifier
Domoticz plugin for Xiaomi AirPurifier Pro 
* Based on the kofec repository https://github.com/kofec/domoticz-AirPurifier

## Installation

```
pip3 install -U python-miio
```

* Make sure your Domoticz instance supports Domoticz Plugin System - see more https://www.domoticz.com/wiki/Using_Python_plugins

* Get plugin data into DOMOTICZ/plugins directory
```
cd YOUR_DOMOTICZ_PATH/plugins
git clone https://github.com/pawcio50501/domoticz-AirPurifier
```

* check the location of the python-miio installation and correct below variable if needed (python.py)
site_path = '/usr/local/lib/python3.6/site-packages'

Restart Domoticz
* Go to Setup > Hardware and create new Hardware with type: AirPurfier
* Enter name (it's up to you), user name and password if define. If not leave it blank

## Update
```
cd YOUR_DOMOTICZ_PATH/plugins/domoticz-AirPurifier
git pull
```
* Restart Domoticz


