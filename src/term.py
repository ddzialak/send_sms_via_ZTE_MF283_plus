
BLACK = ''
RED = ''
GREEN = ''
YELLOW = ''
BLUE = ''
MAGENTA = ''
CYAN = ''
WHITE = ''
RESET = ''
BRIGHT = ''
DIM = ''
NORMAL = ''
RESET_ALL = ''


class Color:
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    RESET = '\033[39m'

    BRIGHT = '\033[1m'
    DIM = '\033[2m'
    NORMAL = '\033[22m'
    RESET_ALL = '\033[0m'


attrs = [name for name in vars(Color) if name.isupper()]


def terminal_formats_enabled():
    for attr in attrs:
        globals()[attr] = getattr(Color, attr)


def terminal_formats_disabled():
    for attr in attrs:
        globals()[attr] = ''
