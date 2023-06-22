import configparser
import logging
import os
import subprocess
import sys

import requests

from term import terminal_formats_enabled

OUTPUT_FMT = "%(message)s"
DEBUG_FMT = "%(levelname).3s %(asctime)s %(name)s %(process)d '%(threadName)s': %(message)s [%(filename)s:%(lineno)d]"

logger = logging.getLogger(__name__)

known_numbers = {}

module_path = os.path.abspath(__file__)
module_dir = os.path.dirname(os.path.dirname(module_path))

config_dirs = ['/etc', module_dir, './']


def is_phone_number(ph):
    return len(ph) == 9 and ph.isdigit()


def load_config():
    config = configparser.ConfigParser()

    for cfg_dir in config_dirs:
        candidate = os.path.join(cfg_dir, 'mf283.ini')
        if os.path.isfile(candidate):
            config.read(candidate)

    return config


def setup_cli(verbose=False):
    if sys.stdout.isatty():
        terminal_formats_enabled()
    if verbose:
        level = logging.DEBUG
        fmt = DEBUG_FMT
    else:
        level = logging.INFO
        fmt = OUTPUT_FMT

    config = load_config()
    logging.basicConfig(level=level, format=fmt)
    setup_router(config.get('default', 'router_ip', fallback='auto'))
    load_known_numbers()


def _check_addr(router_ip):
    logger.debug(f'Trying %s', router_ip)
    resp = requests.get(f'http://{router_ip}/index.html', timeout=3, verify=False, allow_redirects=True)
    return 'ZTE_MF283_QSG_v1.pdf' in resp.text


def setup_router(router_ip):
    import zte_mf283

    if zte_mf283.ROUTER_IP:
        return
    router_ip = router_ip.strip().lower()
    if not router_ip or router_ip == 'auto':
        logger.info("Setup/search device")
        code, gateway_ips = subprocess.getstatusoutput("ip r | sed -n 's/default via \\([^ ]*\\) .*/\\1/p'")
        if code == 0:
            for line in gateway_ips.splitlines():
                if _check_addr(line):
                    zte_mf283.ROUTER_IP = line
                    break
    else:
        if _check_addr(router_ip):
            zte_mf283.ROUTER_IP = router_ip
        else:
            raise ValueError(f"Router IP from config: {router_ip} doesn't work, check config and device.")

    if not zte_mf283.ROUTER_IP:
        raise ValueError(f"Missing device or not configured properly")



def load_known_numbers():
    file_with_numbers = os.path.join(os.path.dirname(os.path.dirname(module_path)), 'numbers.txt')
    if not os.path.isfile(file_with_numbers):
        logger.debug("Missing file with numbers: %s", file_with_numbers)
        return
    with open(file_with_numbers) as fh:
        lines = fh.readlines()

    for line in lines:
        line = line.strip()
        if line.startswith('#') or line.startswith(';'):
            continue
        if ':' not in line:
            logger.debug("Skip line %s as there is no ':' separator.", line)
            continue

        numbers, user = line.split(':', 1)
        for number in numbers.split(','):
            user = user.lower().strip()
            number = number.strip()
            if is_phone_number(number):
                known_numbers[number] = user
                known_numbers.setdefault(f'user: {user}', []).append(number)
            else:
                logger.debug("Skip %s as it's not valid phone number (user %s in line: %s)", number, user, line)
            logger.debug(f"Loaded {user} number: {number}")


def to_name(number_or_name):
    number_or_name = number_or_name.strip()
    if number_or_name.startswith('+48'):
        number_or_name = number_or_name[3:]
    number_or_name = number_or_name.strip()
    return known_numbers.get(number_or_name, number_or_name)


def to_number(number_or_name, default=None):
    if number_or_name.startswith('+48'):
        number_or_name = number_or_name[3:]
    if is_phone_number(number_or_name):
        return number_or_name
    return known_numbers.get(f'user: {number_or_name}', default)
