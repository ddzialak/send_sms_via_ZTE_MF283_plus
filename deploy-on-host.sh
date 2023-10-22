#!/bin/bash

set -euo pipefail

cd $(dirname $0)

TO_HOST=${1:-}
TO_DIR=${2:-zte-mf283-service}

if [[ "B#M@$TO_HOST" =~ "B#M@-" ]]; then
	echo "Usage: $0 DESTINATION_HOST"
	exit 1
fi

if [[ -z "$TO_HOST" ]] || [[ -z "$TO_DIR" ]]; then
	echo "Host, neither directory, should not be empty"
	exit 1
fi

echo "Deploy service on $TO_HOST in directory $TO_DIR"

echo "Send files to $TO_HOST"
rsync -va --exclude .idea --exclude .git --exclude __pycache__  ./ $TO_HOST:$TO_DIR

echo "Setup systemd"
ssh $TO_HOST bash "$TO_DIR/setup_systemd.sh"

