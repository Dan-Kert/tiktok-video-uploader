from typing import Any, Literal
from playwright.sync_api import Page, sync_playwright
from . import config, logger
from .types import ProxyDict

browser_t = Literal['chrome', 'firefox', 'webkit', 'edge', 'safari', 'chromium']

def get_browser(name: browser_t='chromium', headless: bool=False, proxy: ProxyDict | None=None, *args, **kwargs) -> Page:
    p = sync_playwright().start()
    try:
        if name in {'chrome', 'edge', 'chromium'}:
            browser_type = p.chromium
        elif name == 'firefox':
            browser_type = p.firefox
        elif name in {'webkit', 'safari'}:
            browser_type = p.webkit
        else:
            browser_type = p.chromium
        launch_args: dict[str, Any] = {'headless': headless, 'args': ['--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage']}
        if name == 'chrome':
            launch_args['channel'] = 'chrome'
        elif name == 'edge':
            launch_args['channel'] = 'msedge'
        if proxy:
            scheme = str(proxy.get('scheme') or 'http').lower()
            host = str(proxy.get('host', '')).strip()
            port = str(proxy.get('port', '')).strip()
            if not host or not port:
                raise ValueError('Proxy must include host and port')
            if 'user' in proxy or 'password' in proxy:
                if scheme in {'socks5', 'socks5h'}:
                    raise ValueError('Chromium does not support SOCKS5 authentication; use a SOCKS5 proxy without credentials or a different proxy type.')
            launch_args['proxy'] = {'server': f'{scheme}://{host}:{port}'}
            if 'user' in proxy and 'password' in proxy:
                launch_args['proxy']['username'] = proxy['user']
                launch_args['proxy']['password'] = proxy['password']
        browser = browser_type.launch(**launch_args)
        context_args: dict[str, Any] = {
            'viewport': {'width': 1280, 'height': 720},
            'locale': 'en-US',
            'timezone_id': 'UTC',
            'extra_http_headers': {'Accept-Language': 'en-US,en;q=0.9'},
        }
        if name in {'firefox', 'webkit', 'safari'}:
            context_args.pop('user_agent', None)
        else:
            context_args['user_agent'] = config.disguising.user_agent
        try:
            context = browser.new_context(**context_args)
            context.add_init_script("\n            Object.defineProperty(navigator, 'webdriver', {\n                get: () => undefined\n            });\n            Object.defineProperty(navigator, 'language', {\n                get: () => 'en-US'\n            });\n            Object.defineProperty(navigator, 'languages', {\n                get: () => ['en-US', 'en']\n            });\n            ")
            page = context.new_page()
            page._playwright = p
            page._browser = browser
        except Exception:
            browser.close()
            p.stop()
            raise
        page.set_default_timeout(config.implicit_wait * 1000)
    except Exception:
        p.stop()
        raise
    return page

def close_browser(page: Page) -> None:
    browser = getattr(page, 'context', None)
    browser_obj = browser.browser if browser is not None else None
    try:
        if browser_obj is not None:
            browser_obj.close()
    except Exception as exc:
        logger.debug('Error closing browser: %s', exc)
    playwright = getattr(page, '_playwright', None)
    try:
        if playwright is not None:
            playwright.stop()
    except Exception as exc:
        logger.debug('Error stopping Playwright: %s', exc)
    if browser_obj is not None and hasattr(browser_obj, '_browser_type') and getattr(browser_obj._browser_type, '_playwright', None) is not None:
        try:
            browser_obj._browser_type._playwright.stop()  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug('Error stopping Playwright via browser type: %s', exc)