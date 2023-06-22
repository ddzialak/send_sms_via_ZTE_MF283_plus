## Receive and send SMS'es from internal network via ZTE modem MF283+

# Requirements

- MF283+ modem permitted to send SMS
- Computer attached to internal netwok with
  - python3
  - requests

# Definition of known numbers

In file `numbers.txt` is mappping of names to numbers.
Number could be binded with many names and name could be binded
with many numbers, thats OK! When sending SMS to someone by name
the last one number is used.

```
123123123: uncle
123123124: uncle
111222333: aunt
111222333: Janny

# default is a special definition that receive all other SMS-es
# but to make it working "sms --check" must be invoked.
123444567: default
```

# Usage

`./sendsms.sh <receiver> "text to be sent"`

`./sms --check`

`./sms --check --delete-all`

`./sms --rmid <message-id>`
