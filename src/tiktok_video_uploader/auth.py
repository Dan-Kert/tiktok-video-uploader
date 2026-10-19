import re
from http import cookiejar
from time import sleep, time
from typing import Any, cast

from playwright.sync_api import Page, expect

from . import config, logger
from .browsers import close_browser, get_browser
from .types import Cookie, cookie_from_dict
from .utils import green

DEFAULT_COOKIE_DOMAIN = '.tiktok.com'

class AuthBackend:
    username: str
    password: str
    cookies: list[Cookie]
    cookies_path: str | None
    cookies_str: str | None
    cookies_list: list[Cookie]
    sessionid: str | None

    def __init__(self, username: str='', password: str='', cookies_list: list[Cookie] | None=None, cookies: str | None=None, cookies_str: str | None=None, sessionid: str | None=None):
        if username and (not password) or (password and (not username)):
            raise InsufficientAuth('Username and password must be provided together.')
        self.cookies_path = cookies
        self.cookies_str = cookies_str
        self.cookies_list = list(cookies_list) if cookies_list else []
        self.sessionid = sessionid
        self.cookies = []
        has_cookie_input = bool(self.cookies_path or self.cookies_str or self.cookies_list or self.sessionid)
        if not (has_cookie_input or (username and password)):
            raise InsufficientAuth('No valid authentication source found. Provide cookies, sessionid, or username/password.')
        self.username = username
        self.password = password
        if cookies:
            logger.debug(green('Authenticating browser with cookies'))
        elif username and password:
            logger.debug(green('Authenticating browser with username and password'))
        elif sessionid:
            logger.debug(green('Authenticating browser with sessionid'))
        elif self.cookies_list:
            logger.debug(green('Authenticating browser with cookies_list'))

    def authenticate_agent(self, page: Page) -> Page:
        if not self.cookies:
            self.cookies = self._resolve_cookies()
        if not self.cookies and self.username and self.password:
            self.cookies = login(page, username=self.username, password=self.password)
        if not self.cookies:
            raise InsufficientAuth('No valid authentication source found. Provide a valid cookies file, cookies list/string, sessionid, or username/password.')
        logger.debug(green('Authenticating browser with cookies'))
        playwright_cookies: list[dict[str, Any]] = []
        for cookie in self.cookies:
            c: dict[str, Any] = dict(cookie)
            if 'expiry' in c:
                c['expires'] = c.pop('expiry')
            if c.get('expires') is not None and c['expires'] <= 0:
                c.pop('expires')
            if c.get('sameSite') not in ('Strict', 'Lax', 'None'):
                c.pop('sameSite', None)
            if not c.get('domain'):
                c['domain'] = DEFAULT_COOKIE_DOMAIN
            if not c.get('path'):
                c['path'] = '/'
            playwright_cookies.append(c)
        added = 0
        for pc in playwright_cookies:
            try:
                page.context.add_cookies([cast(Any, pc)])
                added += 1
            except Exception as e:
                logger.error("Failed to add cookie %s (domain=%r): %s", pc.get('name'), pc.get('domain'), e)
        logger.debug(f'Added {added}/{len(playwright_cookies)} cookies')
        if not any((c['name'] == 'sessionid' for c in page.context.cookies())):
            raise InsufficientAuth('The sessionid cookie was not accepted by the browser. Check cookies.txt (the sessionid line, its domain and format).')
        page.goto(str(config.paths.main))
        current_url = page.url
        if '/login' in current_url:
            logger.error(f'Redirected to {current_url} and sessionid cookie is missing or invalid')
            raise InsufficientAuth(f'Authentication failed: redirected to {current_url}. Cookie or sessionid is invalid or expired.')
        expect(page).to_have_title(re.compile('TikTok'), timeout=config.explicit_wait * 1000)
        return page

    def _resolve_cookies(self) -> list[Cookie]:
        resolved_cookies: list[Cookie] = []
        if self.cookies_path:
            try:
                resolved_cookies.extend(self.get_cookies(path=self.cookies_path))
            except OSError as error:
                raise FileNotFoundError(f"Could not read cookies file '{self.cookies_path}': {error}") from error
        if self.cookies_str:
            resolved_cookies.extend(self.get_cookies(cookies_str=self.cookies_str))
        if self.cookies_list:
            resolved_cookies.extend(self.cookies_list)
        if self.sessionid:
            resolved_cookies.append({'name': 'sessionid', 'value': self.sessionid, 'domain': DEFAULT_COOKIE_DOMAIN, 'path': '/'})
        return resolved_cookies

    def get_cookies(self, path: str | None=None, cookies_str: str | None=None) -> list[Cookie]:
        if path:
            with open(path, encoding='utf-8') as file:
                lines = file.read().splitlines()
        elif cookies_str is not None:
            lines = cookies_str.splitlines()
        else:
            raise ValueError('Must have either a path or a cookies_str')
        return_cookies: list[Cookie] = []
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            http_only = False
            if line.startswith('#HttpOnly_'):
                line = line[len('#HttpOnly_'):]
                http_only = True
            elif line.startswith('#'):
                continue
            split = [x.strip() for x in line.split('\t')]
            if len(split) < 7:
                continue
            cookie: Cookie = {'name': split[5], 'value': split[6], 'domain': split[0], 'path': split[2] or '/', 'secure': split[3].upper() == 'TRUE', 'httpOnly': http_only}
            try:
                expiry = int(float(split[4]))
                if expiry > 0:
                    cookie['expiry'] = expiry
            except ValueError:
                pass
            return_cookies.append(cookie)
        return return_cookies

def login_accounts(page: Page | None=None, accounts=None, *args, **kwargs) -> dict[str, list[Cookie]]:
    owns_page = page is None
    page = page or get_browser(*args, **kwargs)
    cookies = {}
    try:
        for account in accounts or []:
            username, password = get_username_and_password(account)
            cookies[username] = login(page, username, password)
    finally:
        if owns_page:
            close_browser(page)
    return cookies

def login(page: Page, username: str, password: str) -> list[Cookie]:
    assert username and password, 'Username and password are required'
    if str(config.paths.main) not in page.url:
        page.goto(str(config.paths.main))
    cookies = page.context.cookies()
    session_cookie = next((c for c in cookies if c['name'] == config.selectors.login.cookie_of_interest), None)
    if session_cookie:
        page.context.clear_cookies()
    page.goto(str(config.paths.login))
    username_field = page.locator(f'xpath={config.selectors.login.username_field}')
    username_field.wait_for(state='visible', timeout=config.explicit_wait * 1000)
    username_field.clear()
    username_field.fill(username)
    password_field = page.locator(f'xpath={config.selectors.login.password_field}')
    password_field.clear()
    password_field.fill(password)
    submit = page.locator(f'xpath={config.selectors.login.login_button}')
    submit.click()
    print(f'Complete the captcha for {username}')
    start_time = time()
    captcha_wait = config.captcha_wait
    while True:
        cookies = page.context.cookies()
        if any((c['name'] == config.selectors.login.cookie_of_interest for c in cookies)):
            break
        sleep(0.5)
        if time() - start_time > captcha_wait:
            raise InsufficientAuth('Captcha did not complete in time. Please finish the login challenge and retry.')
    try:
        page.wait_for_function("(url) => window.location.href !== url", str(config.paths.login), timeout=config.explicit_wait * 1000)
    except Exception:
        pass
    return page.context.cookies()

def get_username_and_password(login_info: tuple | dict):
    if not isinstance(login_info, dict):
        if len(login_info) < 2:
            raise InsufficientAuth('Login info must include username and password.')
        return (login_info[0], login_info[1])
    if 'email' in login_info:
        return (login_info['email'], login_info['password'])
    if 'username' in login_info:
        return (login_info['username'], login_info['password'])
    raise InsufficientAuth('Login info must include an email or username plus a password.')

def save_cookies(path: str, cookies: list[Cookie]) -> None:
    cookie_jar = cookiejar.MozillaCookieJar(path)
    for cookie in cookies:
        cookie_jar.set_cookie(cookie_from_dict(cookie))
    cookie_jar.save()

class InsufficientAuth(Exception):
    """Authentication failed or TikTok rejected the supplied login state."""

    def __init__(self, message: str | None=None):
        super().__init__(message or self.__doc__ or 'Authentication failed.')