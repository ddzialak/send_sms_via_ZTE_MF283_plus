import configparser
import functools
import logging
import os
import shlex
import subprocess
import sys
from typing import Callable

import requests

from term import terminal_formats_enabled

OUTPUT_FMT = "%(message)s"
DEBUG_FMT = "%(levelname).3s %(asctime)s %(name)s %(process)d '%(threadName)s': %(message)s [%(filename)s:%(lineno)d]"

logger = logging.getLogger(__name__)

known_numbers = {}

module_path = os.path.abspath(__file__)
module_dir = os.path.dirname(os.path.dirname(module_path))

config_dirs = ['/etc', module_dir, './']

sms_cmds = {
}


def is_phone_number(ph):
    ph = str(ph)
    return len(ph) == 9 and ph.isdigit()


def load_config(filename='mf283.ini', without=None, config=None) -> configparser.ConfigParser:
    config = config or configparser.ConfigParser()
    without = without or set()
    num_loaded_files = 0

    for cfg_dir in config_dirs:
        candidate = os.path.abspath(os.path.join(cfg_dir, filename))
        if candidate not in without and os.path.isfile(candidate):
            without.add(candidate)
            if '-v' in sys.argv or '--verbose' in sys.argv:
               print("Load config: %s" % candidate)
            config.read(candidate)
            num_loaded_files += 1

    if num_loaded_files:
        extra_cfg_file = config.get('default', 'import', fallback='mf283-user.ini')
        if extra_cfg_file:
            load_config(extra_cfg_file, without, config)

    return config


def exec_cmd(cmd, *args, timeout=10):
    try:
        completed_proc = subprocess.run(cmd + ' ' + shlex.join(args), shell=True, timeout=timeout, capture_output=True)
        result = []
        if completed_proc.stderr:
            result.append(completed_proc.stderr.strip().decode())
        if completed_proc.stdout:
            result.append(completed_proc.stdout.strip().decode())
        if completed_proc.returncode:
            result.append(f"ERR: {completed_proc.returncode}")
        return '\n'.join(result)
    except Exception as ex:
        return f"cmd error: {ex}"


def get_callback(fn, *args, with_args=False, **fn_kwargs) -> Callable[..., str]:

    @functools.wraps(fn)
    def callback(*input_args):
        run_with_args = list(args)
        result = []
        if with_args:
            run_with_args.extend(input_args)
        elif input_args:
            result.append('Please avoid args, this command ignores them.')
        result.append(str(fn(*run_with_args, **fn_kwargs)))
        return '\n'.join(result)

    return callback


def load_cmds(config: configparser.ConfigParser):
    cmd_prefix = 'command:'
    for section in config.sections():
        if not section.startswith(cmd_prefix):
            continue
        key = section[len(cmd_prefix):].strip()
        cmd = config.get(section, 'exec', fallback='').strip()
        with_args = config.getboolean(section, 'with_args', fallback=False)
        if key and cmd:
            alias = config.get(section, 'alias', fallback='').strip()
            timeout = config.getint(section, 'timeout', fallback=10)
            callback = get_callback(exec_cmd, cmd, timeout=timeout, with_args=with_args)
            logger.debug(f"Register cmd {key} {alias=} => {cmd}")
            sms_cmds[key] = callback
            if alias:
                sms_cmds[alias] = callback


def setup_cli(verbose=False):
    if sys.stdout.isatty():
        terminal_formats_enabled()
    if verbose:
        level = logging.DEBUG
        fmt = DEBUG_FMT
    else:
        level = logging.INFO
        fmt = OUTPUT_FMT

    config: configparser.ConfigParser = load_config()
    logging.basicConfig(level=level, format=fmt)
    setup_router(config.get('default', 'router_ip', fallback='auto'))
    setup_passwd(config.get('default', 'password', fallback=None))
    load_known_numbers()
    load_cmds(config)


def _check_addr(router_ip):
    logger.debug(f'Trying %s', router_ip)
    resp = requests.get(f'http://{router_ip}/index.html', timeout=3, verify=False, allow_redirects=True)
    return 'ZTE_MF283_QSG_v1.pdf' in resp.text


def setup_passwd(password):
    if password:
        import zte_mf283
        zte_mf283.PASSWD = password.encode()


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
                known_numbers[f'user: {user}'] = number
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
