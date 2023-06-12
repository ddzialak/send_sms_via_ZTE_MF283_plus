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

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

ROUTER_IP = '192.168.0.1'
URL = None
HEADERS = None

PASSWD = b'admin'


_cache = {}


def setup_router():
    global ROUTER_IP, URL, HEADERS

    code, gateway_ips = subprocess.getstatusoutput("ip r | sed -n 's/default via \\([^ ]*\\) .*/\\1/p' | tail -n 1")
    if code == 0:
        lines = gateway_ips.splitlines()
        if lines and lines[0]:
            ROUTER_IP = lines[0]

    URL = f'http://{ROUTER_IP}/goform/goform_set_cmd_process'
    HEADERS = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                              'X-Requested-With': 'XMLHttpRequest',
                              'Accept': 'application/json, text/javascript, */*; q=0.01',
                              f'Referer': f'http://{ROUTER_IP}/index.html'}


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
    print(f"Login {URL}")
    passwd = base64.encodebytes(PASSWD).decode().strip()
    resp = requests.post(URL, headers=HEADERS,  data={'isTest': 'false', 'goformId': 'LOGIN', 'password': passwd})
    if resp.status_code == 200:
        output = resp.json()
        if str(output['result']).upper() in ['0', 'OK', 'SUCCESS']:
            print("Login succeeded")
            return True
    print("Login FAILED")
    print(f"Response: {resp}")
    print(f"Response: {resp.data}")
    return False


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



def check_received_sms(ts=None):
    login()
    if ts is None:
        ts = str((time.time() - 3600) * 1000)
    url = f'http://{ROUTER_IP}/goform/goform_get_cmd_process'
    url_params = {
        'isTest': 'false',
        'cmd': 'sms_data_total',
        'page': '0',
        'data_per_page': '100',
        'mem_store': '1',
        'tags': '10',
        'order_by': 'order by id desc',
        '_': ts
    }
    raw_headers = f"""Host: 192.168.0.2
User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0
Accept: application/json, text/javascript, */*; q=0.01
Accept-Language: en-US,en;q=0.5
Accept-Encoding: gzip, deflate
X-Requested-With: XMLHttpRequest
DNT: 1
Connection: close
Referer: http://{ROUTER_IP}/index.html"""
    headers = dict([line.split(': ', 1) for line in raw_headers.splitlines()])
    resp = requests.get(url, headers=headers, params=url_params)
    data = resp.json()
    for msg in data.get('messages'):
        msg['content'] = decode_sms_body(msg['content'])
        print(msg)
        # logger.info("%6s %8s %s" % (msg['id'], msg['number'], decode_sms_body(msg['content'])))
        # tag=2 -> wysłane
        # tag=1 -> odebrane, nieprzeczytane
        # tag=0 -> odebrane, przeczytane


def delete_sms(msgid):
    raw_request = f'''POST /goform/goform_set_cmd_process HTTP/1.1
Host: 192.168.0.2
User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0
Accept: application/json, text/javascript, */*; q=0.01
Accept-Language: en-US,en;q=0.5
Accept-Encoding: gzip, deflate
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest
Content-Length: 63
Origin: http://192.168.0.2
DNT: 1
Connection: keep-alive
Referer: http://192.168.0.2/index.html
'''
    data = f'isTest=false&goformId=DELETE_SMS&msg_id={msgid}%3B&notCallback=true'


def main():
    if (len(sys.argv) in [2, 3]) and (sys.argv[1].strip('-').lower() == 'check'):
        return check_received_sms(sys.argv[2] if len(sys.argv) == 3 else None)

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
