#!/usr/bin/env python3


import base64
import codecs
import logging
import subprocess
import sys
import time

import requests

from codes import encode_message
from codes import decode_message
from codes import parse_time

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

ROUTER_IP = '192.168.0.1'

PASSWD = b'admin'


_cache = {}


def setup_router():
    global ROUTER_IP, URL, HEADERS

    code, gateway_ips = subprocess.getstatusoutput("ip r | sed -n 's/default via \\([^ ]*\\) .*/\\1/p' | tail -n 1")
    if code == 0:
        lines = gateway_ips.splitlines()
        if lines and lines[0]:
            ROUTER_IP = lines[0]


def encode_sms_body(data, codec):
    result = encode_message(data)
    print("[%s] Converted %s -> %s" % (codec, data, result))
    return result


def decode_sms_body(data):
    return decode_message(data, True)


def is_phone_number(ph):
    return len(ph) == 9 and ph.isdigit()


def hilfe():
    print("Usage: %s phone_number message" % sys.argv[0])
    print("Usage: %s check [ts]" % sys.argv[0])
    sys.exit(2)


def login():
    setup_router()
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
            print("Login succeeded")
            return True
        print(output)
    print("Login FAILED")
    print(f"Response: {resp}")
    raise SystemExit(7)


def send_sms(number, body):
    try:
        # max=765
        body = encode_sms_body(body[:760], 'gsm7')
        encoding = 'GSM7_default'
    except UnicodeEncodeError:
        # max=335
        body = encode_sms_body(body[:330], 'utf16')
        encoding = 'UNICODE'

    print("[%s] => %s" % (encoding, body))

    sms_time = time.strftime('%Y;%m;%d;%H;%M;%S;+2')[2:]

    # encode_type=UNICODE | GSM7_default
    # [UNICODE] łóść ŻÓL! => 0142 00F3 015B 0107 0020 017B 00D3 004C 0021
    # [GSM7]
    data = {'isTest': 'false',
            'goformId': 'SEND_SMS',
            'notCallback': 'true',
            'Number': str(number),
            'sms_time': sms_time,
            'MessageBody': body,
            'ID': '-1',
            'encode_type': 'UNICODE'}
    resp = requests.post(URL, headers=HEADERS, data=data)
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
        # print(msg)
        # logger.info("%6s %8s %s" % (msg['id'], msg['number'], decode_sms_body(msg['content'])))
        # tag=2 -> wysłane
        # tag=1 -> odebrane, nieprzeczytane
        # tag=0 -> odebrane, przeczytane
    return {msg.get('id'): msg for msg in messages}


def get_url(path):
    if not path.startswith('/'):
        path = f'/{path}'
    return f'http://{ROUTER_IP}{path}'


IGNORED_HEADERS = {'content-length', 'connection'}


def raw_data_to_headers(raw_headers):
    headers = {}
    for line in raw_headers.strip().splitlines():
        key, value = line.split(': ', 1)
        key = key.strip()
        if key.lower() not in IGNORED_HEADERS:
            headers[key] = value.strip()
    return headers


def send_request(method, path, raw_headers, **kwargs):
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
    return resp


def set_sms_read(msgid):
    raw_headers = f"""Host: {ROUTER_IP}
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
Referer: http://{ROUTER_IP}/index.html"""

    data = f'isTest=false&goformId=SET_MSG_READ&msg_id={msgid}%3B&tag=0'
    return send_request('post', '/goform/goform_set_cmd_process', raw_headers, data=data)

def delete_sms(msgid):
    raw_headers = f'''Host: {ROUTER_IP}
User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0
Accept: application/json, text/javascript, */*; q=0.01
Accept-Language: en-US,en;q=0.5
Accept-Encoding: gzip, deflate
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest
Content-Length: {len(data)}
Origin: http://{ROUTER_IP}
DNT: 1
Connection: close
Referer: http://{ROUTER_IP}/index.html
'''
    data = f'isTest=false&goformId=DELETE_SMS&msg_id={msgid}%3B&notCallback=true'
    return send_request('POST', '/goform/goform_set_cmd_process', raw_headers, data=data)


def main():
    if (len(sys.argv) in [2, 3]) and (sys.argv[1].strip('-').lower() == 'check'):
        login()
        m1 = check_received_sms(sys.argv[2] if len(sys.argv) == 3 else None, mem_store=0)
        m2 = check_received_sms(sys.argv[2] if len(sys.argv) == 3 else None, mem_store=1)
        m1.update(m2)
        for _id, msg in sorted(m1.items()):
            print(msg)
            if msg.get('tag') == '1':
                set_sms_read(msg.get('id'))
            # if int(msg.get('id')) > 468:
            #     delete_sms(msg.get('id'))
        return 0

    if len(sys.argv) != 3:
        hilfe()

    if not is_phone_number(sys.argv[1]):
        print("Invalid phone number: %s" % sys.argv[1])
        hilfe()

    login()

    number = sys.argv[1]
    body = sys.argv[2]
    send_sms(number, body)


if __name__ == "__main__":
    main()
