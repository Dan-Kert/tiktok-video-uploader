import os

OKGREEN = '\x1b[92m'
FAIL = '\x1b[91m'
ENDC = '\x1b[0m'
BOLD = '\x1b[1m'
CYAN = '\x1b[96m'

def _use_color() -> bool:
    return os.getenv('NO_COLOR') is None and os.getenv('TERM') not in (None, 'dumb') and os.isatty(1)

def bold(to_bold: str) -> str:
    return BOLD + to_bold + ENDC if _use_color() else to_bold

def green(to_green: str) -> str:
    return OKGREEN + to_green + ENDC if _use_color() else to_green

def red(to_red: str) -> str:
    return FAIL + to_red + ENDC if _use_color() else to_red

def cyan(to_cyan: str) -> str:
    return CYAN + to_cyan + ENDC if _use_color() else to_cyan