import csv
import getpass
import logging
import os
import re
import sys
from argparse import ArgumentParser, Namespace
from os.path import exists, join

from .auth import InsufficientAuth, login_accounts, save_cookies
from .types import ProxyDict
from .upload import FailedToUpload, TikTokUploader

BROWSERS = ['chromium', 'chrome', 'firefox', 'webkit', 'edge', 'safari']

def main() -> None:
    args = get_uploader_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s', datefmt='[%H:%M:%S]')
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='[%H:%M:%S]')
    try:
        proxy = parse_proxy(args.proxy)
        password = args.password or os.environ.get('TIKTOK_PASSWORD')
        if password is None and args.username and not args.cookies and not args.sessionid:
            password = getpass.getpass('TikTok password: ')
        args.password = password
        validate_uploader_args(args)
        visibility = args.visibility
        with TikTokUploader(username=args.username, password=args.password, cookies=args.cookies, proxy=proxy, sessionid=args.sessionid, browser=args.browser, headless=not args.attach) as uploader:
            result = uploader.upload_video(filename=args.video, description=args.description, visibility=visibility)
        print('-------------------------')
        if not result:
            print('Error while uploading video')
        else:
            print('Video uploaded successfully')
        print('-------------------------')
        if not result:
            raise FailedToUpload('Video upload failed.')
    except (InsufficientAuth, FailedToUpload, FileNotFoundError, ValueError) as exc:
        print(f'Upload failed: {exc}', file=sys.stderr)
        raise SystemExit(1) from exc

def get_uploader_args() -> Namespace:
    parser = ArgumentParser(description='TikTok uploader is a video uploader which can upload a' + 'video from your computer to the TikTok using playwright automation')
    parser.add_argument('-v', '--video', help='Video file', required=True)
    parser.add_argument('-d', '--description', help='Description', default='')
    # schedule CLI option removed
    parser.add_argument('--proxy', help='Proxy user:pass@host:port or host:port format', default=None)
    parser.add_argument('--visibility', help='Video visibility: if omitted, no visibility change is made; choices: everyone, friends, only_you', choices=['everyone', 'friends', 'only_you'], default=None)
    parser.add_argument('-V', '--verbose', action='store_true', default=False, help='Enable debug logging')
    # cover option removed
    parser.add_argument('-c', '--cookies', help='The cookies you want to use')
    parser.add_argument('-s', '--sessionid', help='The session id you want to use')
    parser.add_argument('-u', '--username', help='Your TikTok email / username')
    parser.add_argument('-p', '--password', help='Your TikTok password')
    parser.add_argument('--browser', choices=BROWSERS, default='chromium', help='Browser to use (default: chromium, installed by `playwright install chromium`; chrome / edge need the real browser installed)')
    parser.add_argument('--attach', '-a', action='store_true', default=False, help='Runs the program in headful mode (shows browser window)')
    return parser.parse_args()

def validate_uploader_args(args: Namespace) -> None:
    if not exists(args.video):
        raise FileNotFoundError(f'Could not find the video file at {args.video}')
    if args.cookies and (args.username or args.password):
        raise ValueError('You can not pass in both cookies and username / password')
    has_auth = bool(args.cookies or args.sessionid or (args.username and (args.password or os.environ.get('TIKTOK_PASSWORD'))))
    if not has_auth:
        raise InsufficientAuth('Provide at least one authentication source: --cookies, --sessionid, or --username with --password or TIKTOK_PASSWORD.')

def auth() -> None:
    args = get_auth_args()
    validate_auth_args(args=args)
    if args.input:
        login_info = get_login_info(path=args.input, header=args.header)
    else:
        login_info = [(args.username, args.password)]
    username_and_cookies = login_accounts(accounts=login_info, name=args.browser)
    os.makedirs(args.output, exist_ok=True)
    for username, cookies in username_and_cookies.items():
        path = join(args.output, _safe_filename(username) + '.txt')
        save_cookies(path=path, cookies=cookies)
        os.chmod(path, 0o600)

def _safe_filename(name: str) -> str:
    return re.sub('[^\\w.@+-]', '_', name)

def get_auth_args() -> Namespace:
    parser = ArgumentParser(description='TikTok Auth is a program which can log you into multiple accounts sequentially')
    parser.add_argument('-o', '--output', default='tmp', help='The output folder to save the cookies to')
    parser.add_argument('-i', '--input', help='A csv file with username and password')
    parser.add_argument('--no-header', dest='header', action='store_false', default=True, help='The csv file has no header line (by default the first line is skipped)')
    parser.add_argument('-u', '--username', help='Your TikTok email / username')
    parser.add_argument('-p', '--password', help='Your TikTok password')
    parser.add_argument('--browser', choices=BROWSERS, default='chromium', help='Browser to use (default: chromium)')
    return parser.parse_args()

def validate_auth_args(args: Namespace) -> None:
    if args.input and (args.username or args.password):
        raise ValueError('You can not pass in both username / password and input file')
    if not args.input and (not (args.username and args.password)):
        raise ValueError('Pass either --input or both --username and --password')

def get_login_info(path: str, header: bool=True) -> list[tuple[str, str]]:
    with open(path, encoding='utf-8', newline='') as file:
        rows = [row for row in csv.reader(file) if row]
    if header:
        rows = rows[1:]
    login_info: list[tuple[str, str]] = []
    for number, row in enumerate(rows, start=1):
        if len(row) != 2:
            raise ValueError(f"Entry {number} of {path} is not valid: expected 'username,password'")
        login_info.append((row[0].strip(), row[1]))
    return login_info

# schedule parsing removed

def parse_proxy(proxy_raw: str | None) -> ProxyDict:
    proxy: ProxyDict = {}
    if not proxy_raw:
        return proxy
    remainder = proxy_raw
    if '://' in proxy_raw:
        scheme, remainder = proxy_raw.split('://', 1)
        if scheme.lower() in {'http', 'https', 'socks5', 'socks5h'}:
            proxy['scheme'] = scheme.lower()
        else:
            raise ValueError(f'Unsupported proxy scheme: {scheme!r}')
    else:
        proxy['scheme'] = 'http'
    if '@' in remainder:
        auth_part, host_port = remainder.rsplit('@', 1)
        if ':' in auth_part:
            proxy['user'], proxy['password'] = auth_part.split(':', 1)
        else:
            proxy['user'] = auth_part
        host_part, port_part = host_port.rsplit(':', 1)
    else:
        if ':' not in remainder:
            raise ValueError(f'Invalid proxy format: {proxy_raw!r}. Expected host:port')
        host_part, port_part = remainder.rsplit(':', 1)
    if not host_part or not port_part:
        raise ValueError(f'Invalid proxy format: {proxy_raw!r}. Expected host:port')
    proxy['host'] = host_part
    proxy['port'] = port_part
    return proxy