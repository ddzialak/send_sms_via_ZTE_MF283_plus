#/bin/bash

cd $(dirname "$0")

receiver=$1
shift

./zte-cli --send "$receiver"  "$*"
