#!/usr/bin/python3

import sys
import argparse
from pathlib import Path

pathOfPackages = '/usr/lib/python3/dist-packages'

if Path(pathOfPackages).exists():
    sys.path.append(pathOfPackages)
else:
    print("It can be an issue with import package miio.airpurifier")
    print("Find where is located package miio.airpurifier and correct variable: pathOfPackages")
    print("pathOfPackages:", pathOfPackages)

pathOfPackages = '/usr/local/lib/python3.5/dist-packages'

if Path(pathOfPackages).exists():
    sys.path.append(pathOfPackages)
    import miio.airpurifier
else:
    print("It can be an issue with import package miio.airpurifier")
    print("Find where is located package miio.airpurifier and correct variable: pathOfPackages")
    print("pathOfPackages:", pathOfPackages)
    import miio.airpurifier

parser = argparse.ArgumentParser(description='Script which comunicate with AirPurfier.')
parser.add_argument('IPaddress', help='IP address of AirPurfier' )
parser.add_argument('token', help='token to login to device')
parser.add_argument('--mode', choices=['Auto', 'Favorite', 'Idle', 'Silent'], help='choose mode operation')
parser.add_argument('--favoriteLevel', type=int, choices=range(0, 11), help='choose mode operation')
parser.add_argument('--power', choices=['ON', 'OFF'], help='power ON/OFF')
parser.add_argument('--debug', action='store_true', help='if define more output is printed')

# MyAir.set_mode(miio.airpurifier.OperationMode.Silent)

args = parser.parse_args()
if args.debug:
    print(args)
MyAir = miio.airpurifier.AirPurifier(args.IPaddress, args.token)

if args.mode:
    if args.mode == "Auto":
            MyAir.set_mode(miio.airpurifier.OperationMode.Auto)
    elif args.mode == "Favorite":
            MyAir.set_mode(miio.airpurifier.OperationMode.Favorite)
    elif args.mode == "Idle":
            MyAir.set_mode(miio.airpurifier.OperationMode.Idle)
    elif args.mode == "Silent":
            MyAir.set_mode(miio.airpurifier.OperationMode.Silent)

if args.favoriteLevel:
    MyAir.set_favorite_level(args.favoriteLevel)

if args.favoriteLevel:
    MyAir.set_favorite_level(args.favoriteLevel)

if args.power:
    if args.power == "ON":
        MyAir.on()
    elif args.power == "OFF":
        MyAir.off()

print(MyAir.status())



