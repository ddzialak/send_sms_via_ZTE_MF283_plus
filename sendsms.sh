#/bin/bash

cd $(dirname "$0")

receiver=$1
shift

python3 src/sms.py --send "$receiver"  "$*"
