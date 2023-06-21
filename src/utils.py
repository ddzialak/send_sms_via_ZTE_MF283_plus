import logging
import subprocess
import sys

import requests

from term import terminal_formats_enabled
import zte_mf283


OUTPUT_FMT = "%(message)s"
DEBUG_FMT = "%(levelname).3s %(asctime)s %(name)s %(process)d '%(threadName)s': %(message)s [%(filename)s:%(lineno)d]"

logger = logging.getLogger(__name__)


def setup_cli():
    if sys.stdout.isatty():
        terminal_formats_enabled()
    if '-v' in sys.argv or '--verbose' in sys.argv:
        level = logging.DEBUG
        fmt = DEBUG_FMT
    else:
        level = logging.INFO
        fmt = OUTPUT_FMT
    logging.basicConfig(level=level, format=fmt)
    setup_router()
    zte_mf283.load_known_numbers()


def setup_router():
    if zte_mf283.ROUTER_IP:
        return

    logger.info("Setup/search device")
    code, gateway_ips = subprocess.getstatusoutput("ip r | sed -n 's/default via \\([^ ]*\\) .*/\\1/p'")
    if code == 0:
        for line in gateway_ips.splitlines():
            logger.debug(f'Trying %s', line)
            candidate = line
            resp = requests.get(f'http://{candidate}/index.html', timeout=3, verify=False, allow_redirects=True)
            if 'ZTE_MF283_QSG_v1.pdf' in resp.text:
                zte_mf283.ROUTER_IP = line

    if not zte_mf283.ROUTER_IP:
        raise ValueError(f"Can not find valid device")