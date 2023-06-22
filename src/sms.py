#!/usr/bin/env python3
import argparse
import logging
import sys

import term
from utils import known_numbers, to_name, to_number, is_phone_number
from utils import setup_cli
from zte_mf283 import Tag
from zte_mf283 import send_sms, set_net_state, check_received_sms, login, set_sms_read, delete_sms

logger = logging.getLogger(__name__)


def parse_args(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--check', action='store_true', help="Check inbox")
    parser.add_argument('--delete-all', action='store_true', help='Delete messages')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose info')
    parser.add_argument('--rmid', type=int, help='Remove single message')
    parser.add_argument('--all', action='store_true', help="Show all inbox messages")
    parser.add_argument(
            '--keep-unread', action='store_true', help="Show inbox messages but keep them unread and do not"
            " invoke actions for new messages like forwarding message or connecting/disconnecting router."
    )
    parser.add_argument('--send', nargs=2, help="Send message, should be followed by receiver's number and text to send")
    return parser.parse_args(args)


def handle_received_message(msg):
    msg_id = msg.get('id')
    number = msg.get('number')
    if number.startswith('+48'):
        number = number[3:]

    if number not in known_numbers:
        return

    content = msg.get('content')

    if content.lower() == 'connect':
        logger.info("connecting...")
        resp = set_net_state(True)
        send_sms(number, str(resp))
    elif content.lower() == 'disconnect':
        logger.info("disconnecting...")
        resp = set_net_state(False)
        send_sms(number, str(resp))
    else:
        redirect_to = to_number('default')
        if redirect_to not in [number, 'default']:
            send_sms(redirect_to, f"[{msg_id}] FROM: {number}\n{content}")


def main():
    parser = parse_args(sys.argv[1:])
    setup_cli(verbose=parser.verbose)
    if parser.check or parser.all or parser.keep_unread:
        login()
        m1 = check_received_sms(sys.argv[2] if len(sys.argv) == 3 else None, mem_store=0)
        m2 = check_received_sms(sys.argv[2] if len(sys.argv) == 3 else None, mem_store=1)
        m1.update(m2)
        for _id, msg in sorted(m1.items(), key=lambda t: t[1].get('date')):
            logger.debug(msg)
            number = to_name(msg.get('number'))
            content = msg.get('content')
            date = msg.get('date')
            tag = msg.get('tag')

            state = {Tag.READ: ' -> ', Tag.UNREAD: ' => ', Tag.SENT: ' <- '}.get(str(tag), '???')
            style = term.YELLOW if tag in [Tag.READ, Tag.UNREAD] else term.NORMAL
            bright = term.BRIGHT if tag == Tag.UNREAD in state else ''
            logger.info(f'%5s %-12s %4s %s {style}{bright}%r{term.RESET_ALL}' % (msg.get('id'), date, number, state, content))

            if tag == '1' and not parser.keep_unread:
                try:
                    handle_received_message(msg)
                    set_sms_read(msg.get('id'))
                except Exception as e:
                    logger.error(f"Handle message error: {e}")

            if parser.delete_all:
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
