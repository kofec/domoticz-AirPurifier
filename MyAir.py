#!/usr/bin/python3

import sys
import argparse
from pathlib import Path
pathOfPackages='/usr/local/lib/python3.5/dist-packages'

if Path(pathOfPackages).exists():
    sys.path.append('/usr/local/lib/python3.5/dist-packages')
    import miio.airpurifier
else:
    Print("It can be an issue with import package miio.airpurifier")
    Print("Find where is located package miio.airpurifier and correct variable: pathOfPackages")
    Print("pathOfPackages:", pathOfPackages)
    import miio.airpurifier

parser = argparse.ArgumentParser(description='Script which comunicate with AirPurfier.')
parser.add_argument('IPaddress', help='IP address of AirPurfier' )
parser.add_argument('token', help='token to login to device')
#parser.add_argument('--password', help='Password to login to', default='admin')
#parser.add_argument('--st2', action='store_true', help='if define output of st2.xml is printed')
#parser.add_argument('--out', nargs=2, metavar=('<port number>', 'ON/OFF'), help='eg. --out 1 ON - when turn ON out1')

args = parser.parse_args()
#print(args)
MyAir = miio.airpurifier.AirPurifier(args.IPaddress, args.token)
#print(MyAir.info())
print(MyAir.status())



