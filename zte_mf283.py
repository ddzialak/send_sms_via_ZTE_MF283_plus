import base64
import logging
import subprocess
import time

import requests

from codes import decode_message
from codes import encode_message
from codes import parse_time


logger = logging.getLogger(__name__)

PASSWD = b'admin'
ROUTER_IP = ''

_cache = {}

known_numbers = {}


def load_known_numbers():
    with open('numbers.txt') as fh:
        lines = fh.readlines()

    for line in lines:
        if ':' in line:
            number, user = line.split(':', 1)
            number = number.strip()
            user = user.lower().strip()
            if is_phone_number(number) and not is_phone_number(user):
                known_numbers[user] = number
                known_numbers[number] = user
                logger.debug(f"Loaded {user} number: {number}")
            else:
                logger.debug("Skip line: %s (%s is not number or %s is a valid number)", line, number, user)


def to_name(number_or_name):
    if number_or_name.startswith('+48'):
        number_or_name = number_or_name[3:]
    if not is_phone_number(number_or_name):
        return number_or_name
    return known_numbers.get(number_or_name, number_or_name)


def to_number(number_or_name):
    if number_or_name.startswith('+48'):
        number_or_name = number_or_name[3:]
    if is_phone_number(number_or_name):
        return number_or_name
    return known_numbers.get(number_or_name, number_or_name)



def setup_cli():
    import sys
    level = logging.DEBUG if '-v' in sys.argv or '--verbose' in sys.argv else logging.INFO
    logging.basicConfig(level=level)
    setup_router()
    load_known_numbers()

def setup_router():
    global ROUTER_IP

    if ROUTER_IP:
        return

    logger.info("Setup/search device")
    code, gateway_ips = subprocess.getstatusoutput("ip r | sed -n 's/default via \\([^ ]*\\) .*/\\1/p'")
    if code == 0:
        for line in gateway_ips.splitlines():
            logger.debug(f'Trying %s', line)
            candidate = line
            resp = requests.get(f'http://{candidate}/index.html', timeout=3, verify=False, allow_redirects=True)
            if 'ZTE_MF283_QSG_v1.pdf' in resp.text:
                ROUTER_IP = line

    if not ROUTER_IP:
        raise ValueError(f"Can not find valid device")


def encode_sms_body(data, codec):
    result = encode_message(data)
    logger.debug("[%s] Converted %s -> %s" % (codec, data, result))
    return result


def decode_sms_body(data):
    return decode_message(data, True)


def is_phone_number(ph):
    return len(ph) == 9 and ph.isdigit()


def login():
    if not ROUTER_IP:
        raise ValueError("Sorry!")

    passwd = base64.encodebytes(PASSWD).decode().strip()
    raw_headers = f'''
        Content-Type: application/x-www-form-urlencoded; charset=UTF-8
        X-Requested-With: XMLHttpRequest
        Accept: application/json, text/javascript, */*; q=0.01
        Referer: http://{ROUTER_IP}/index.html
    '''
    data = {'isTest': 'false', 'goformId': 'LOGIN', 'password': passwd}
    resp = send_request('post', '/goform/goform_set_cmd_process', raw_headers, data=data)
    if resp.status_code == 200:
        output = resp.json()
        if str(output['result']).upper() in ['0', 'OK', 'SUCCESS']:
            logger.info("Login succeeded")
            return True
        logger.log(output)
    logger.error("Login FAILED (see log above)")
    logger.error(f"Response: {resp}")
    raise SystemExit(7)


def send_sms(number, body):
    raw_headers = f'''
        Content-Type: application/x-www-form-urlencoded; charset=UTF-8
        X-Requested-With: XMLHttpRequest
        Accept: application/json, text/javascript, */*; q=0.01
        Referer: http://{ROUTER_IP}/index.html
    '''
    sms_time = time.strftime('%Y;%m;%d;%H;%M;%S;+2')[2:]
    data = {'isTest': 'false',
            'goformId': 'SEND_SMS',
            'notCallback': 'true',
            'Number': str(number),
            'sms_time': sms_time,
            'MessageBody': encode_sms_body(body, 'UNICODE'),
            'ID': '-1',
            'encode_type': 'UNICODE'}
    resp = send_request('post', '/goform/goform_set_cmd_process', raw_headers, data=data)
    print(resp.status_code)
    print(resp.json())


def check_received_sms(ts=None, mem_store=1):
    if ts is None:
        ts = str((time.time() - 3600) * 1000)
    url_params = {
        'isTest': 'false',
        'cmd': 'sms_data_total',
        'page': '0',
        'data_per_page': '100',
        'mem_store': str(mem_store),
        'tags': '10',
        'order_by': 'order by id desc',
        '_': ts
    }
    raw_headers = f"""Host: {ROUTER_IP}
User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0
Accept: application/json, text/javascript, */*; q=0.01
Accept-Language: en-US,en;q=0.5
Accept-Encoding: gzip, deflate
X-Requested-With: XMLHttpRequest
DNT: 1
Connection: close
Referer: http://{ROUTER_IP}/index.html"""
    resp = send_request('get', '/goform/goform_get_cmd_process', raw_headers, params=url_params)
    data = resp.json()
    messages = data.get('messages')
    for msg in messages:
        msg['content'] = decode_sms_body(msg['content'])
        msg['date'] = parse_time(msg['date'])
        # logger.info("%6s %8s %s" % (msg['id'], msg['number'], decode_sms_body(msg['content'])))
        # tag=2 -> sent
        # tag=1 -> received, unread
        # tag=0 -> received, read
    return {msg.get('id'): msg for msg in messages}


def get_url(path):
    if not path.startswith('/'):
        path = f'/{path}'
    return f'http://{ROUTER_IP}{path}'


IGNORED_HEADERS = {'content-length', 'connection'}


def raw_data_to_headers(raw_headers):
    headers = {}
    for line in raw_headers.strip().splitlines():
        if ':' not in line:
            logger.warning(f"IGNORE Unexpected header line: {line}")
            continue
        key, value = line.split(': ', 1)
        key = key.strip()
        if key.lower() not in IGNORED_HEADERS:
            headers[key] = value.strip()
    return headers


def send_request(method, path, raw_headers, raise_on_error=True, **kwargs):
    req_headers = raw_data_to_headers(raw_headers)
    resp = requests.request(method, get_url(path), headers=req_headers, **kwargs)
    if resp.status_code // 100 != 2:
        logger.info(f"Request {method} {path}")
        logger.info(f"Headers: {req_headers}")
        logger.info("FAILED")
        logger.info(resp.headers)
        logger.info('')
        logger.info(resp.text)
        logger.info(resp)
        if raise_on_error:
            raise ValueError(f"HTTP Error {resp}")
    return resp


def set_sms_read(msgid):
    raw_headers = f"""
        Host: {ROUTER_IP}
        User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0
        Accept: application/json, text/javascript, */*; q=0.01
        Accept-Language: en-US,en;q=0.5
        Accept-Encoding: gzip, deflate
        Content-Type: application/x-www-form-urlencoded; charset=UTF-8
        X-Requested-With: XMLHttpRequest
        Content-Length: 54
        Origin: http://{ROUTER_IP}
        DNT: 1
        Connection: close
        Referer: http://{ROUTER_IP}/index.html
    """
    data = f'isTest=false&goformId=SET_MSG_READ&msg_id={msgid}%3B&tag=0'
    return send_request('post', '/goform/goform_set_cmd_process', raw_headers, data=data)


def delete_sms(msgid):
    raw_headers = f'''
        Host: {ROUTER_IP}
        User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0
        Accept: application/json, text/javascript, */*; q=0.01
        Accept-Language: en-US,en;q=0.5
        Accept-Encoding: gzip, deflate
        Content-Type: application/x-www-form-urlencoded; charset=UTF-8
        X-Requested-With: XMLHttpRequest
        Origin: http://{ROUTER_IP}
        DNT: 1
        Connection: close
        Referer: http://{ROUTER_IP}/index.html
    '''
    data = f'isTest=false&goformId=DELETE_SMS&msg_id={msgid}%3B&notCallback=true'
    return send_request('post', '/goform/goform_set_cmd_process', raw_headers, data=data)


def set_net_state(state: bool):
    raw_headers = f'''
        Host: {ROUTER_IP}
        User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0
        Accept: application/json, text/javascript, */*; q=0.01
        Accept-Language: en-US,en;q=0.5
        Accept-Encoding: gzip, deflate
        Content-Type: application/x-www-form-urlencoded; charset=UTF-8
        X-Requested-With: XMLHttpRequest
        Content-Length: 54
        Origin: http://{ROUTER_IP}
        DNT: 1
        Connection: keep-alive
        Referer: http://{ROUTER_IP}/index.html
    '''
    set_state = 'CONNECT_NETWORK' if state else 'DISCONNECT_NETWORK'
    data = f'isTest=false&notCallback=true&goformId={set_state}'
    return send_request('post', '/goform/goform_set_cmd_process', raw_headers, data=data)


def disable_dhcp_server(lan_ip=ROUTER_IP, reboot=1):
    method = 'post'
    path = '/goform/goform_set_cmd_process'
    raw_headers = '''
        Host: 192.168.0.2
        User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0
        Accept: application/json, text/javascript, */*; q=0.01
        Accept-Language: en-US,en;q=0.5
        Accept-Encoding: gzip, deflate
        Content-Type: application/x-www-form-urlencoded; charset=UTF-8
        X-Requested-With: XMLHttpRequest
        Content-Length: 116
        Origin: http://192.168.0.2
        DNT: 1
        Connection: keep-alive
        Referer: http://192.168.0.2/index.html
    '''.replace('192.168.0.2', ROUTER_IP)
    data = (
        f'isTest=false&goformId=DHCP_SETTING&lanIp={lan_ip}&lanNetmask=255.255.255.0'
        f'&lanDhcpType=DISABLE&dhcp_reboot_flag={reboot}'
    )
    return send_request(method, path, raw_headers, data=data)


def enable_dhcp_server(lan_ip=ROUTER_IP, dhcp_start='192.168.0.241', dhcp_end='192.168.0.254', reboot=1):
    method = 'post'
    path = '/goform/goform_set_cmd_process'
    raw_headers = '''
        Host: 192.168.0.2
        User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0
        Accept: application/json, text/javascript, */*; q=0.01
        Accept-Language: en-US,en;q=0.5
        Accept-Encoding: gzip, deflate
        Content-Type: application/x-www-form-urlencoded; charset=UTF-8
        X-Requested-With: XMLHttpRequest
        Content-Length: 174
        Origin: http://192.168.0.2
        DNT: 1
        Connection: keep-alive
        Referer: http://192.168.0.2/index.html
    '''.replace('192.168.0.2', ROUTER_IP)
    data = (
        f'isTest=false&goformId=DHCP_SETTING&lanIp={lan_ip}&lanNetmask=255.255.255.0&'
        f'lanDhcpType=SERVER&dhcpStart={dhcp_start}&dhcpEnd={dhcp_end}&dhcpLease=24&dhcp_reboot_flag={reboot}'
    )
    return send_request(method, path, raw_headers, data=data)
