#!/usr/bin/env python3


import sys
import base64
import codecs
import time
import requests

from encodings import normalize_encoding

import subprocess

ROUTER_IP = '192.168.0.1'
URL = None
HEADERS = None

PASSWD = b'admin'


_cache = {}


def setup_router():
    global ROUTER_IP, URL, HEADERS

    code, gateway_ips = subprocess.getstatusoutput("ip r | sed -n 's/default via \\([^ ]*\\) .*/\\1/p'")
    if code == 0:
        lines = gateway_ips.splitlines()
        if lines and lines[0]:
            ROUTER_IP = lines[0]

    URL = f'http://{ROUTER_IP}/goform/goform_set_cmd_process'
    HEADERS = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                              'X-Requested-With': 'XMLHttpRequest',
                              'Accept': 'application/json, text/javascript, */*; q=0.01',
                              f'Referer': f'http://{ROUTER_IP}/index.html'}


def decode_gsm7(txt, errors):
    ext_table = {
        '\x40': u'|',
        '\x14': u'^',
        '\x65': u'€',
        '\x28': u'{',
        '\x29': u'}',
        '\x3C': u'[',
        '\x3D': u'~',
        '\x3E': u']',
        '\x2F': u'\\',
    }
    chunks = filter(None, txt.split('\x1b'))  # split on ESC
    res = u''
    for chunk in chunks:
        res += ext_table[chunk[0]]  # first character after ESC
        if len(chunk) > 1:
            # charmap_decode returns a tuple..
            decoded, _ = codecs.charmap_decode(chunk[1:], errors, decoding_table)
            res += decoded
    return res, len(txt)


decoding_table = (
    u"@£$¥èéùìòÇ\nØø\rÅå" +
    u"Δ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ" +
    u" !\"#¤%&'()*+,-./" +
    u"0123456789:;<=>?" +
    u"¡ABCDEFGHIJKLMNO" +
    u"PQRSTUVWXYZÄÖÑÜ§" +
    u"¿abcdefghijklmno" +
    u"pqrstuvwxyzäöñüà"
)

encoding_table = codecs.charmap_build(
    decoding_table + '\0' * (256 - len(decoding_table))
)

# extending the encoding table with extension characters
encoding_table[ord(u'|')] = '\x1b\x40'
encoding_table[ord(u'^')] = '\x1b\x14'
encoding_table[ord(u'€')] = '\x1b\x65'
encoding_table[ord(u'{')] = '\x1b\x28'
encoding_table[ord(u'}')] = '\x1b\x29'
encoding_table[ord(u'[')] = '\x1b\x3C'
encoding_table[ord(u'~')] = '\x1b\x3D'
encoding_table[ord(u']')] = '\x1b\x3E'
encoding_table[ord(u'\\')] = '\x1b\x2F'


class GSM7Codec(codecs.Codec):

    def encode(self, txt, errors='strict'):
        return codecs.charmap_encode(txt, errors, encoding_table)

    def decode(self, txt, errors='strict'):
        return decode_gsm7(txt, errors)


class GSM7IncrementalEncoder(codecs.IncrementalEncoder):
    def encode(self, input, final=False):
        return codecs.charmap_encode(input, self.errors, encoding_table)[0]


class GSM7IncrementalDecoder(codecs.IncrementalDecoder):
    def decode(self, input, final=False):
        return codecs.charmap_decode(input, self.errors, decoding_table)[0]


class GSM7StreamWriter(codecs.StreamWriter):
    pass


class GSM7StreamReader(codecs.StreamReader):
    pass


def search_function(encoding):
    """Register the gsm-7 encoding with Python's codecs API. This involves
       adding a search function that takes in an encoding name, and returns
       a codec for that encoding if it knows one, or None if it doesn't.
    """
    if encoding in _cache:
        return _cache[encoding]
    norm_encoding = normalize_encoding(encoding)
    if norm_encoding in ('gsm_7', 'g7', 'gsm7'):
        cinfo = codecs.CodecInfo(
            name='gsm-7',
            encode=GSM7Codec().encode,
            decode=GSM7Codec().decode,
            incrementalencoder=GSM7IncrementalEncoder,
            incrementaldecoder=GSM7IncrementalDecoder,
            streamreader=GSM7StreamReader,
            streamwriter=GSM7StreamWriter,
        )
        _cache[norm_encoding] = cinfo
        return cinfo


codecs.register(search_function)


def two_dig(c):
    res = hex(c)[2:].upper()
    if len(res) == 1:
        return '0' + res
    return res


def encode_sms_body(data, codec):
    buf = []
    for c in data:
        chars = c.encode(codec)
        if len(chars) > 1:
            buf.append(two_dig(chars[-1]))
            buf.append(two_dig(chars[-2]))
        else:
            buf.append('00')
            buf.append(two_dig(chars[-1]))

    result = ''.join(buf)
    print("[%s] Converted %s -> %s" % (codec, data, result))
    return result


def is_phone_number(ph):
    return len(ph) == 9 and ph.isdigit()


def hilfe():
    print("Usage: %s phone_number message" % sys.argv[0])
    sys.exit(2)


def main():
    if len(sys.argv) != 3:
        hilfe()

    if not is_phone_number(sys.argv[1]):
        print("Invalid phone number: %s" % sys.argv[1])
        hilfe()

    setup_router()

    print(f"Login {URL}")

    passwd = base64.encodebytes(PASSWD).decode().strip()
    resp = requests.post(URL, headers=HEADERS,  data={'isTest': 'false', 'goformId': 'LOGIN', 'password': passwd})
    if resp.status_code == 200:
        output = resp.json()
        if str(output['result']).upper() in ['0', 'OK', 'SUCCESS']:

            print("Login succeeded")
            number = sys.argv[1]

            body = sys.argv[2]

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

if __name__ == "__main__":
    main()

