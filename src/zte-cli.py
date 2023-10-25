#!/usr/bin/env python3

import argparse
import json
import logging
import sys
import time

import term
from utils import get_callback
from utils import known_numbers, to_name, to_number, is_phone_number
from utils import setup_cli, sms_cmds
from zte_mf283 import Tag
from zte_mf283 import send_sms, set_net_state, check_received_sms, login, \
    set_sms_read, delete_sms, enable_dhcp_server, disable_dhcp_server, get_status

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
    parser.add_argument('--connect', action='store_true', help="Request network connection.")
    parser.add_argument('--disconnect', action='store_true', help="Request disconnection.")
    parser.add_argument('--get-status', action='store_true', help="Request for status.")
    parser.add_argument('--interval', type=int, default=10, help='Interval between commands (see --repeat)')
    parser.add_argument('--repeat', type=int, default=1, help='Number of repeatitions')
    return parser.parse_args(args)


STATUS_KEYS = {'signalbar', 'network_type', 'sms_unread_num', 'simcard_roam', 'network_provider', 'ppp_status'}


def get_status_wrap(*args):
    logger.info("get status %s", args)
    json_out = {k: v for (k, v) in get_status().items() if k in STATUS_KEYS}
    return json.dumps(json_out, sort_keys=True, indent=2)


def register_sms_commands():
    sms_cmds['connect'] = get_callback(set_net_state, True, with_args=False)
    sms_cmds['disconnect'] = get_callback(set_net_state, False, with_args=False)
    sms_cmds['dhcpon!'] = get_callback(enable_dhcp_server)
    sms_cmds['dhcpoff!'] = get_callback(disable_dhcp_server)

    check_status_fn = get_callback(get_status_wrap)
    sms_cmds['getstatus'] = check_status_fn
    sms_cmds['status'] = check_status_fn
    sms_cmds['checkstatus'] = check_status_fn


def exec_request_and_reply(sender, msg):
    lines = msg.get('content').lower().replace('-', '').replace('_', ' ').splitlines()
    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue
        cmd = parts[0]
        args = parts[1:]
        if cmd in sms_cmds:
            try:
                callback = sms_cmds.get(cmd)
                result = callback(*args)
            except Exception as ex:
                result = f'ERR: {ex}'
            send_sms(sender, f"[{cmd}]\n{result}")
        else:
            keys_str = ', '.join(sms_cmds.keys())
            send_sms(sender, f"Unrecognized: {line}, defined: {keys_str}")


def handle_received_message(msg):
    sender = msg.get('number')
    if sender.startswith('+48'):
        sender = sender[3:]

    if sender not in known_numbers:
        return

    forward_to = to_number('default')
    if forward_to == sender:
        exec_request_and_reply(sender, msg)
    else:
        if not forward_to:
            logger.info("Do not forward message as recipient ('default' entry in numbers.txt) is not defined")
        else:
            msg_id = msg.get('id')
            msg_orig = msg.get('content')
            send_sms(forward_to, f"[{msg_id}] FROM: {sender}\n{msg_orig}")


def check_inbox(parser):
    login()
    register_sms_commands()
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
        print(f'%5s %-12s %4s %s {style}{bright}%r{term.RESET_ALL}' % (msg.get('id'), date, number, state, content))

        if tag == '1' and not parser.keep_unread:
            try:
                handle_received_message(msg)
                set_sms_read(msg.get('id'))
            except Exception as e:
                logger.exception(f"Handle message error: {e}")

        if parser.delete_all:
            delete_sms(msg.get('id'))


def execute_request(parser):
    if parser.check or parser.all or parser.keep_unread:
        check_inbox(parser)

    if parser.send:
        receiver = parser.send[0]
        text = parser.send[1]
        number = to_number(receiver)
        if not number:
            logger.error(f"Unrecognized receiver: {receiver}")
        elif not is_phone_number(number):
            logger.error("Invalid phone number: %s" % number)
        else:
            login()
            send_sms(number, text)

    if parser.rmid:
        login()
        logger.info("Delete message %s", parser.rmid)
        delete_sms(parser.rmid)

    if parser.connect:
        resp = set_net_state(True)
        logger.info(f"Connection request result: {resp}")
    if parser.disconnect:
        resp = set_net_state(False)
        logger.info(f"Disconnection request result: {resp}")
    if parser.get_status:
        resp = get_status()
        print(json.dumps(resp, sort_keys=True, indent=2))


def main():
    parser = parse_args(sys.argv[1:])
    setup_cli(verbose=parser.verbose)

    repeat_num = parser.repeat
    while repeat_num != 0:
        execute_request(parser)
        repeat_num -= 1
        if repeat_num == 0:
            break
        logger.debug("sleeping...")
        time.sleep(parser.interval)


if __name__ == "__main__":
    try:
       main()
    except KeyboardInterrupt:
        print("Bye!")
