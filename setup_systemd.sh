#!/bin/bash

set -euo pipefail

if [[ $USER = root ]]; then
	SUDO=""
else
	SUDO=sudo
fi

cd $(dirname $0)

for service_file in systemd/*.service;
do
  echo "----------------------------------------"
	echo "Prepare === ${service_file} === "
	echo
	service=$(echo $service_file | sed 's#systemd/\(.*\).service#\1#')
	sed "s|\$PWD|$PWD|" "${service_file}" | $SUDO tee "/etc/systemd/system/${service}.service"
done

$SUDO systemctl daemon-reload

for service_file in systemd/*.service;
do
  echo
  echo "Enable & restart $service_file"
	$SUDO systemctl enable "${service_file##systemd/}"
	$SUDO systemctl restart "${service_file##systemd/}"
done
