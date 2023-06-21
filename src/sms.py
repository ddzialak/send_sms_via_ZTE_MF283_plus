#!/usr/bin/env python3
import argparse
import logging
import sys

from utils import setup_cli
from zte_mf283 import send_sms, set_net_state, check_received_sms, login, set_sms_read, is_phone_number, known_numbers, \
    to_name, delete_sms, to_number

import term

logger = logging.getLogger(__name__)


def parse_args(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--check', action='store_true', help="Check inbox")
    parser.add_argument('-d', '--delete', action='store_true', help='Delete messages')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose info')
    parser.add_argument('--rmid', type=int, help='Remove single message')
    parser.add_argument('--all', action='store_true', help="Show all inbox messages")
    parser.add_argument('--keep-unread', action='store_true', help="Show inbox messages but do not mark them as read")
    parser.add_argument('--send', nargs=2, help="Send message, should be followed by receiver's number and text to send")
    return parser.parse_args(args)


def handle_received_message(msg):
    msg_id = msg.get('id')
    number = msg.get('number')
    if number not in known_numbers:
        return
    if number.startswith('+48'):
        number = number[3:]
    content = msg.get('content')

    if content.lower() == 'neton':
        resp = set_net_state(True)
        send_sms(number, str(resp))
    elif content.lower() == 'netoff':
        resp = set_net_state(False)
        send_sms(number, str(resp))


state_desc = {
        '0': ' -> ',
        '1': ' => ',
        '2': ' <- ',
}


def main():
    setup_cli()
    parser = parse_args(sys.argv[1:])
    if parser.check or parser.all or parser.keep_unread:
        login()
        m1 = check_received_sms(sys.argv[2] if len(sys.argv) == 3 else None, mem_store=0)
        m2 = check_received_sms(sys.argv[2] if len(sys.argv) == 3 else None, mem_store=1)
        m1.update(m2)
        for _id, msg in sorted(m1.items(), key=lambda t: t[1].get('date')):
            logger.debug(msg)
            if msg.get('tag') == '1':
                set_sms_read(msg.get('id'))
                handle_received_message(msg)
            number = to_name(msg.get('number'))
            content = msg.get('content')
            date = msg.get('date')
            tag = msg.get('tag')
            state = state_desc.get(str(tag), '???')
            style = term.YELLOW if "<" in state  else term.NORMAL
            bright = term.BRIGHT if "=" in state else ''
            logger.info(f'%5s %-12s %4s %s {style}{bright}%s{term.RESET_ALL}' % (msg.get('id'), date, number, state, content))
            if parser.delete:
                delete_sms(msg.get('id'))

    if parser.send:
        receiver = parser.send[0]
        text = parser.send[1]
        number = to_number(receiver)
        if not is_phone_number(number):
            logger.error("Invalid phone number: %s" % number)
        login()
        send_sms(number, text)

    if parser.rmid:
        login()
        logger.info("Delete message %s", parser.rmid)
        delete_sms(parser.rmid)


if __name__ == "__main__":
    main()
