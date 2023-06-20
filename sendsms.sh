#/bin/bash

receiver=$1
shift

python3 sms.py --send "$receiver"  "$*"
