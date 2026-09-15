#!/usr/bin/python3
"""Command line client for Xiaomi Air Purifier 2/2S/Pro (python-miio).

The Domoticz plugin runs this script in a separate process for every request.
python-miio needs `cryptography`, whose Rust bindings (PyO3) can be initialized
only once per process. Domoticz runs every plugin in a sub-interpreter of one
process, so importing miio in plugin.py fails as soon as another plugin, a second
instance of this plugin or a restart of it has already loaded `cryptography`.

The token is taken from the second argument or from the MIIO_TOKEN environment
variable (the plugin uses the variable, so the token does not show up in `ps`).
"""

import argparse
import enum
import json
import logging
import os
import sys

MODES = ("Auto", "Favorite", "Idle", "Silent")
ON_OFF = ("ON", "OFF")

# AirPurifierStatus properties passed to the plugin
STATUS_FIELDS = (
    "power", "aqi", "average_aqi", "temperature", "humidity", "mode",
    "favorite_level", "motor_speed", "filter_hours_used", "filter_life_remaining",
    "illuminance", "led", "child_lock", "buzzer", "volume",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Script which communicates with Xiaomi Air Purifier.")
    parser.add_argument("IPaddress", help="IP address of the air purifier")
    parser.add_argument("token", nargs="?", default=os.environ.get("MIIO_TOKEN"),
                        help="token to log in to the device (default: $MIIO_TOKEN)")
    parser.add_argument("--power", choices=ON_OFF, help="power ON/OFF")
    parser.add_argument("--mode", choices=MODES, help="choose operation mode")
    parser.add_argument("--favoriteLevel", type=int, choices=range(0, 18), metavar="{0..17}",
                        help="fan level used in Favorite mode")
    parser.add_argument("--led", choices=ON_OFF, help="turn LED on/off")
    parser.add_argument("--buzzer", choices=ON_OFF, help="turn buzzer on/off (2/2S)")
    parser.add_argument("--volume", type=int, choices=range(0, 101), metavar="{0..100}",
                        help="buzzer volume (Pro)")
    parser.add_argument("--childLock", choices=ON_OFF, help="turn child lock on/off")
    parser.add_argument("--timeout", type=int, default=5, help="timeout of a single request in seconds")
    parser.add_argument("--json", action="store_true", help="print the status as one line of JSON")
    parser.add_argument("--debug", action="store_true", help="if defined more output is printed")
    args = parser.parse_args()
    if not args.token:
        parser.error("the token is required (argument or MIIO_TOKEN)")
    return args


def load_miio():
    # `from miio import AirPurifier` works in every python-miio release, while the
    # module holding the class (and OperationMode) moved in 0.5.12.
    from miio import AirPurifier
    return AirPurifier, sys.modules[AirPurifier.__module__].OperationMode


def status_to_dict(status):
    result = {}
    for name in STATUS_FIELDS:
        try:
            value = getattr(status, name)
        except Exception:  # property not reported by this model
            value = None
        if isinstance(value, enum.Enum):
            value = value.name
        result[name] = value
    return result


def run(args):
    AirPurifier, OperationMode = load_miio()
    device = AirPurifier(args.IPaddress, args.token, timeout=args.timeout)

    if args.power == "ON":
        device.on()
    if args.mode:
        device.set_mode(OperationMode[args.mode])
    if args.favoriteLevel is not None:
        device.set_favorite_level(args.favoriteLevel)
    if args.led:
        device.set_led(args.led == "ON")
    if args.buzzer:
        device.set_buzzer(args.buzzer == "ON")
    if args.volume is not None:
        device.set_volume(args.volume)
    if args.childLock:
        device.set_child_lock(args.childLock == "ON")
    if args.power == "OFF":
        device.off()

    return device.status()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING)

    try:
        status = run(args)
    except Exception as e:
        if not args.json:
            raise
        print(json.dumps({"error": "%s: %s" % (type(e).__name__, e)}))
        return 1

    if args.json:
        print(json.dumps({"status": status_to_dict(status)}))
    else:
        print(status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
