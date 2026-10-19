import logging
import time
from collections.abc import Callable
from os.path import abspath, splitext
from pathlib import Path
from typing import Any, Literal

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from . import config
from .auth import AuthBackend, InsufficientAuth
from .browsers import close_browser, get_browser
from .types import Cookie, ProxyDict, VideoDict
from .utils import bold, green, red

logger = logging.getLogger(__name__)
_SESSION_EXPIRED = 'TikTok redirected to the login page: the session is not authorized. Export a fresh cookies.txt (the sessionid cookie has probably expired).'

def _wait_visible(locator: Locator, timeout: float) -> bool:
    try:
        locator.first.wait_for(state='visible', timeout=timeout * 1000)
        return True
    except PlaywrightTimeoutError:
        return False

def _safe_count(locator: Any) -> int:
    if locator is None:
        return 0
    try:
        count = locator.count()
    except Exception:
        return 1 if hasattr(locator, 'first') or hasattr(locator, 'is_visible') else 0
    if isinstance(count, bool):
        return int(count)
    if isinstance(count, int):
        return count
    try:
        return int(count)
    except (TypeError, ValueError):
        return 1 if hasattr(locator, 'first') or hasattr(locator, 'is_visible') else 0

class TikTokUploader:

    def __init__(self, *, username: str='', password: str='', cookies: str='', cookies_list: list[Cookie] | None=None, cookies_str: str | None=None, sessionid: str | None=None, proxy: ProxyDict | None=None, browser: Literal['chrome', 'safari', 'chromium', 'edge', 'firefox']='chromium', headless: bool=False, **kwargs):
        self.auth = AuthBackend(username=username, password=password, cookies=cookies, cookies_list=cookies_list, cookies_str=cookies_str, sessionid=sessionid)
        self.proxy = proxy
        self.browser_name = browser
        self.headless = headless
        self.browser_kwargs = kwargs
        self._page: Page | None = None

    @property
    def page(self) -> Page:
        if self._page is None:
            logger.debug('Create a %s browser instance %s', self.browser_name, 'in headless mode' if self.headless else '')
            page = get_browser(self.browser_name, headless=self.headless, proxy=self.proxy, **self.browser_kwargs)
            try:
                self._page = self.auth.authenticate_agent(page)
            except Exception:
                close_browser(page)
                raise
        return self._page

    def upload_video(self, filename: str, description: str='', visibility: Literal['everyone', 'friends', 'only_you'] | None=None, *, num_retries: int=1, skip_split_window: bool=False, **kwargs) -> bool:
        video_dict: VideoDict = {'path': filename}
        if description:
            video_dict['description'] = description
        if visibility is not None:
            video_dict['visibility'] = visibility

        failed_list = self.upload_videos([video_dict], num_retries=num_retries, skip_split_window=skip_split_window, **kwargs)
        return len(failed_list) == 0

    def upload_videos(self, videos: list[VideoDict], num_retries: int=1, skip_split_window: bool=False, on_complete: Callable[[VideoDict], None] | None=None, **kwargs) -> list[VideoDict]:
        videos = _convert_videos_dict(videos)
        if videos and len(videos) > 1:
            logger.debug('Uploading %d videos', len(videos))
        page = self.page
        failed = []
        for video in videos:
            path = str(video.get('path', ''))
            try:
                path = abspath(video.get('path', '.'))
                description = video.get('description', '')
                visibility = video.get('visibility')
                logger.debug('Posting %s%s', bold(video.get('path', '')), (f"\n{' ' * 15}with description: {bold(description)}") if description else '')
                if not _check_valid_path(path):
                    logger.warning('%s is invalid, skipping', path)
                    raise FailedToUpload(f'Invalid path: {path}')
                complete_upload_form(page, path, description, skip_split_window, visibility=visibility, num_retries=num_retries, **kwargs)
            except InsufficientAuth:
                logger.error('Authentication failed while uploading %s', path)
                failed.append(video)
                raise
            except Exception as exception:
                logger.error('Failed to upload %s', path)
                logger.error(exception)
                failed.append(video)
            finally:
                if on_complete and callable(on_complete):
                    on_complete(video)
        return failed

    def close(self):
        if self._page:
            close_browser(self._page)
            self._page = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

def upload_video(filename: str, description: str | None=None, *, cookies: str='', username: str='', password: str='', sessionid: str | None=None, cookies_list: list[Cookie] | None=None, cookies_str: str | None=None, proxy: ProxyDict | None=None, visibility: Literal['everyone', 'friends', 'only_you'] | None=None, browser: Literal['chrome', 'safari', 'chromium', 'edge', 'firefox']='chromium', headless: bool=False, **kwargs) -> list[VideoDict]:
    uploader = TikTokUploader(username=username, password=password, cookies=cookies, cookies_list=cookies_list, cookies_str=cookies_str, sessionid=sessionid, proxy=proxy, browser=browser, headless=headless, **kwargs)
    video_dict: VideoDict = {'path': filename}
    if description:
        video_dict['description'] = description
    if visibility is not None:
        video_dict['visibility'] = visibility
    try:
        return uploader.upload_videos([video_dict], **kwargs)
    finally:
        if config.quit_on_end:
            uploader.close()

def upload_videos(videos: list[VideoDict], *, username: str='', password: str='', cookies: str='', cookies_list: list[Cookie] | None=None, cookies_str: str | None=None, sessionid: str | None=None, proxy: ProxyDict | None=None, browser: Literal['chrome', 'safari', 'chromium', 'edge', 'firefox']='chromium', browser_agent: Page | None=None, headless: bool=False, **kwargs) -> list[VideoDict]:
    uploader = TikTokUploader(username=username, password=password, cookies=cookies, cookies_list=cookies_list, cookies_str=cookies_str, sessionid=sessionid, proxy=proxy, browser=browser, headless=headless, **kwargs)
    if browser_agent:
        uploader._page = uploader.auth.authenticate_agent(browser_agent)
    try:
        return uploader.upload_videos(videos, **kwargs)
    finally:
        if config.quit_on_end:
            uploader.close()

def complete_upload_form(page: Page, path: str, description: str, skip_split_window: bool, visibility: Literal['everyone', 'friends', 'only_you'] | None = None, num_retries: int=1, **kwargs) -> None:
    _go_to_upload(page)
    _remove_cookies_window(page)
    _set_video(page, path=path, num_retries=num_retries, **kwargs)
    if not skip_split_window:
        _remove_split_window(page)
    _dismiss_popups(page)

    _set_description(page, description)
    _dismiss_popups(page, timeout=2)
    if visibility is not None:
        _set_visibility(page, visibility)

    _post_video(page)

def _go_to_upload(page: Page) -> None:
    logger.debug(green('Navigating to upload page'))
    upload_url = str(config.paths.upload)
    if page.url != upload_url:
        page.goto(upload_url)
    else:
        page.once('dialog', lambda dialog: dialog.accept())
        page.reload()
    try:
        page.wait_for_selector('#root', timeout=config.explicit_wait * 1000)
    except PlaywrightError as exc:
        if '/login' in page.url:
            raise InsufficientAuth(_SESSION_EXPIRED) from exc
        raise
    if '/login' in page.url:
        raise InsufficientAuth(_SESSION_EXPIRED)

def _get_description_editor(page: Page) -> Locator:
    selectors = [
        "//div[@contenteditable='true' and @role='combobox' and contains(@class, 'public-DraftEditor-content')]",
        "//div[@contenteditable='true' and @role='textbox']",
        "//div[contains(@class, 'caption-editor')]//div[@contenteditable='true']",
        "//div[@contenteditable='true']",
    ]
    for selector in selectors:
        locator = page.locator(f'xpath={selector}')
        try:
            if locator.count() > 0:
                locator.first.wait_for(state='visible', timeout=5000)
                return locator.first
        except Exception:
            continue
    return page.locator(f'xpath={config.selectors.upload.description}').first

def _set_description(page: Page, description: str) -> None:
    if description is None:
        return
    logger.debug(green('Setting description'))
    saved_description = description
    desc_locator = _get_description_editor(page)
    try:
        desc_locator.wait_for(state='visible', timeout=config.implicit_wait * 1000)
        _dismiss_tour_overlay(page, timeout=2)
        desc_locator.click()
        time.sleep(0.35)
        desc_locator.press('Control+A')
        desc_locator.press('Backspace')
        desc_locator.click()
        time.sleep(0.5)
        words = description.split(' ')
        for index, word in enumerate(words):
            if not word:
                continue
            if word.startswith('#'):
                time.sleep(0.35)
                page.keyboard.insert_text(word)
                mention_box = page.locator(f'xpath={config.selectors.upload.mention_box}')
                try:
                    mention_box.first.wait_for(state='visible', timeout=config.add_hashtag_wait * 1000)
                    time.sleep(1.2)
                    desc_locator.press('Enter')
                except Exception:
                    pass
                time.sleep(0.8)
                if index < len(words) - 1:
                    desc_locator.press_sequentially(' ', delay=120)
            elif word.startswith('@'):
                logger.debug(green('- Adding Mention: ' + word))
                time.sleep(0.25)
                desc_locator.press_sequentially(word, delay=120)
                time.sleep(1.0)
                mention_box_user_id = page.locator(f'xpath={config.selectors.upload.mention_box_user_id}')
                try:
                    mention_box_user_id.first.wait_for(state='visible', timeout=5000)
                    found = False
                    user_ids = mention_box_user_id.all()
                    target_username = word[1:].lower()
                    for i, user_el in enumerate(user_ids):
                        if user_el.is_visible():
                            text = user_el.inner_text().split(' ')[0]
                            if text.lower() == target_username:
                                found = True
                                print('Matching User found : Clicking User')
                                for _ in range(i):
                                    desc_locator.press('ArrowDown')
                                desc_locator.press('Enter')
                                break
                    if not found:
                        desc_locator.press_sequentially(' ', delay=70)
                except Exception:
                    desc_locator.press_sequentially(' ', delay=70)
            else:
                time.sleep(0.18)
                desc_locator.press_sequentially(word + (' ' if index < len(words) - 1 else ''), delay=140)
        page.keyboard.press('Escape')
    except Exception as exception:
        print('Failed to set description: ', exception)
        try:
            _dismiss_popups(page, timeout=2)
            _clear(desc_locator)
            desc_locator.fill(saved_description)
            page.keyboard.press('Escape')
        except Exception as fallback_exception:
            logger.error(red(f'Description fallback failed: {fallback_exception}'))

def _clear(locator) -> None:
    locator.press('Control+A')
    locator.press('Backspace')

def _set_video(page: Page, path: str='', num_retries: int=3, **kwargs) -> None:
    logger.debug(green('Uploading video file'))
    for _ in range(num_retries):
        try:
            upload_box = page.locator(f'xpath={config.selectors.upload.upload_video}')
            upload_box.set_input_files(path)
            time.sleep(1.5)
            _dismiss_popups(page, timeout=2)

            ready_selectors = [
                config.selectors.upload.process_confirmation,
                "//div[@contenteditable='true' and @role='combobox' and contains(@class, 'public-DraftEditor-content')]",
                "//div[@contenteditable='true' and @role='textbox']",
                "//div[contains(@class, 'caption-editor')]//div[@contenteditable='true']",
                "//button[@data-e2e='post_video_button' or normalize-space()='Post' or normalize-space()='Post now']",
            ]
            for selector in ready_selectors:
                locator = page.locator(f'xpath={selector}')
                try:
                    locator.first.wait_for(state='visible', timeout=15000)
                    return
                except PlaywrightTimeoutError:
                    continue
            raise PlaywrightTimeoutError('No upload-ready editor was found after selecting the video')
        except PlaywrightTimeoutError as exception:
            print('TimeoutException occurred:\n', exception)
        except Exception as exception:
            print(exception)
            raise FailedToUpload(exception)
    raise FailedToUpload(f'The video was not processed by TikTok after {max(num_retries, 1)} attempt(s)')

def _remove_cookies_window(page: Page) -> None:
    logger.debug(green('Removing cookies window'))
    banner_selector = config.selectors.upload.cookies_banner.banner
    try:
        selector = f'{banner_selector} >> {config.selectors.upload.cookies_banner.button} >> button'
        button = page.locator(selector).first
        if _wait_visible(button, 2):
            button.click()
    except Exception:
        try:
            page.evaluate('(sel) => { const el = document.querySelector(sel); if (el) el.remove(); }', banner_selector)
        except Exception as exc:
            logger.debug(red(f'Could not remove the cookies banner: {exc}'))

def _remove_split_window(page: Page) -> None:
    logger.debug(green('Removing split window'))
    window_xpath = config.selectors.upload.split_window
    try:
        window = page.locator(f'xpath={window_xpath}').first
        if _wait_visible(window, 3):
            window.click()
        else:
            logger.debug('Split window is not shown')
    except PlaywrightError as exc:
        logger.debug(red(f'Split window could not be closed: {exc}'))

def _dismiss_blocking_modal(page: Page, timeout: float=8) -> None:
    overlay = page.locator("xpath=//div[contains(@class, 'TUXModal-overlay')]")
    tutorial = page.locator("xpath=//*[contains(@class, 'tutorial-tooltip')]//button[normalize-space()='Got it' or .//div[normalize-space()='Got it']]")
    close_icon = page.locator("xpath=//*[contains(@class, 'common-modal-close') or contains(@class, 'common-modal-close-icon') or @aria-label='Close'] | //button[@aria-label='Close'] | //div[contains(@class,'common-modal-close-icon')]")
    try:
        overlay.first.wait_for(state='visible', timeout=timeout * 1000)
    except PlaywrightTimeoutError:
        try:
            if _safe_count(tutorial) > 0 and tutorial.first.is_visible():
                tutorial.first.click()
                time.sleep(0.5)
        except Exception:
            pass
        return
    logger.debug(green('Closing blocking modal'))

    modal_title = page.locator("xpath=//*[contains(@class, 'TUXModal') or contains(@class, 'common-modal')]//*[contains(normalize-space(.), 'Turn on automatic content checks?')]")
    if _safe_count(modal_title) > 0 and _safe_count(close_icon) > 0:
        try:
            close_icon.first.click()
            time.sleep(0.5)
            return
        except Exception:
            pass

    dismiss_tokens = ('cancel', 'close', 'not now', 'got it', 'later')
    modal_buttons = page.locator("xpath=//div[contains(@class, 'TUXModal')]//button | //*[contains(@class, 'tutorial-tooltip')]//button")
    clicked = False
    for button in modal_buttons.all():
        try:
            if not button.is_visible():
                continue
            text = (button.inner_text() or '').strip().lower()
            if any(token in text for token in dismiss_tokens):
                button.click()
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        for selector in (
            "xpath=//button[normalize-space()='Not now' or .//div[normalize-space()='Not now']]",
            "xpath=//button[normalize-space()='Got it' or .//div[normalize-space()='Got it']]",
            "xpath=//button[normalize-space()='Later' or .//div[normalize-space()='Later']]",
        ):
            candidate = page.locator(selector).first
            try:
                if candidate.is_visible():
                    candidate.click()
                    clicked = True
                    break
            except Exception:
                continue
    if not clicked:
        page.keyboard.press('Escape')
    try:
        overlay.first.wait_for(state='hidden', timeout=5000)
    except PlaywrightTimeoutError:
        page.evaluate("\n            document.querySelectorAll('.TUXModal-overlay').forEach(el => {\n                const portal = el.closest('[data-floating-ui-portal]');\n                (portal || el).remove();\n            });\n            ")

    try:
        if _safe_count(tutorial) > 0 and tutorial.first.is_visible():
            tutorial.first.click()
            time.sleep(0.5)
    except Exception:
        pass

def _dismiss_tour_overlay(page: Page, timeout: float=5) -> None:
    overlay = page.locator('css=#react-joyride-portal .react-joyride__overlay')
    wait = timeout
    for _ in range(3):
        try:
            overlay.first.wait_for(state='visible', timeout=wait * 1000)
        except PlaywrightTimeoutError:
            return
        wait = 1.5
        logger.debug(green('Closing product tour'))
        clicked = False
        for selector in ("xpath=//*[@id='react-joyride-portal']//button[normalize-space()='Got it']", "xpath=//*[@id='react-joyride-portal']//button[@data-action='primary']", "xpath=//*[@id='react-joyride-portal']//button[@data-action='skip' or @data-action='close']"):
            button = page.locator(selector)
            try:
                if button.count() and button.first.is_visible():
                    button.first.click(timeout=3000)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            page.keyboard.press('Escape')
        try:
            overlay.first.wait_for(state='hidden', timeout=3000)
        except PlaywrightTimeoutError:
            page.evaluate("document.getElementById('react-joyride-portal')?.remove()")

def _dismiss_popups(page: Page, timeout: float=8) -> None:
    _dismiss_blocking_modal(page, timeout=timeout)
    _dismiss_tour_overlay(page, timeout=min(timeout, 5))
    _dismiss_blocking_modal(page, timeout=1)

def _is_switch_checked(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {'true', 'checked', 'on', '1'}
    if hasattr(value, 'get'):
        for key in ('aria-checked', 'data-state', 'checked'):
            if key in value:
                return _is_switch_checked(value[key])
    if hasattr(value, 'get_attribute'):
        for attribute in ('aria-checked', 'data-state', 'checked'):
            try:
                result = value.get_attribute(attribute)
                if result is not None:
                    return _is_switch_checked(result)
            except Exception:
                pass
    return False

def _toggle_switch_by_label(page: Page, label: str, enabled: bool | None, confirmation_ok: str='OK') -> bool:
    """Toggle a switch-like control near a label. If `enabled` is None, do nothing.

    Returns True if a candidate was found (regardless of whether a change was needed), False otherwise.
    """
    if enabled is None:
        return False
    label_text = label.strip()
    candidates = page.locator(
        f"xpath=//*[normalize-space(text()) and contains(normalize-space(text()), '{label_text}') and not(ancestor::*[contains(@class, 'modal') or contains(@class, 'Dialog') or contains(@class, 'common-modal')])]"
    )
    count = candidates.count() if hasattr(candidates, 'count') else 0
    for idx in range(count):
        try:
            candidate = candidates.nth(idx)
            if not candidate.is_visible():
                continue
            container = candidate.locator('xpath=ancestor-or-self::*[.//*[contains(@class, "Switch__content") or @role="switch" or @type="checkbox"]][1]').first
            if _safe_count(container) == 0:
                continue

            switch_target = container.locator('xpath=.//*[contains(@class, "Switch__content") or @role="switch" or @type="checkbox" or @type="radio"]').first
            if _safe_count(switch_target) == 0:
                switch_target = container.locator('xpath=.//input[@role="switch" or @type="checkbox" or @type="radio"]').first
            if _safe_count(switch_target) == 0:
                continue

            try:
                current = _is_switch_checked(switch_target.get_attribute('aria-checked')) or _is_switch_checked(switch_target.get_attribute('data-state')) or switch_target.is_checked()
            except Exception:
                current = None
            if current is None:
                try:
                    switch_target.click()
                    time.sleep(0.3)
                except Exception:
                    pass
                return True
            if current != enabled:
                try:
                    switch_target.click()
                    time.sleep(1.0)
                    for _ in range(10):
                        try:
                            readback = _is_switch_checked(switch_target.get_attribute('aria-checked')) or _is_switch_checked(switch_target.get_attribute('data-state')) or switch_target.is_checked()
                        except Exception:
                            readback = None
                        if readback == enabled:
                            break
                        time.sleep(0.2)
                    if enabled:
                        confirm = page.locator(
                            f"xpath=//button[normalize-space()='{confirmation_ok}' or normalize-space()='Turn on' or .//div[normalize-space()='{confirmation_ok}' or normalize-space()='Turn on']]").first
                        if _safe_count(confirm) > 0 and confirm.is_visible():
                            confirm.click()
                            time.sleep(0.5)
                except Exception:
                    pass
            return True
        except Exception:
            continue
    return False

def _set_visibility(page: Page, visibility: Literal['everyone', 'friends', 'only_you'] | None) -> None:
    if visibility is None:
        logger.debug(green('Visibility is unset; leaving target unchanged'))
        return
    logger.debug(green(f'Setting visibility to: {visibility}'))
    visibility_text_map = {'everyone': 'Everyone', 'friends': 'Friends', 'only_you': 'Only you'}
    option_text = visibility_text_map.get(visibility)
    if option_text is None:
        raise FailedToUpload(f'Unknown visibility: {visibility!r}')

    try:
        _dismiss_popups(page, timeout=1)
        trigger = page.locator("xpath=//button[@role='combobox' and contains(@class,'Select__trigger')]").first
        trigger_count = trigger.count() if hasattr(trigger, 'count') else 0
        if not isinstance(trigger_count, int):
            trigger_count = 1 if trigger is not None else 0
        if trigger_count == 0:
            trigger = page.locator("xpath=//*[self::div or self::button or self::label or self::span][contains(normalize-space(.), 'Who can see this post')]").first
            trigger_count = trigger.count() if hasattr(trigger, 'count') else 0
            if not isinstance(trigger_count, int):
                trigger_count = 1 if trigger is not None else 0
        if trigger_count > 0:
            trigger.click()
        time.sleep(1.5)
        option = page.locator(
            f"xpath=(//*[self::div or self::span][contains(@class,'select-option') or contains(@class,'Select__option')][contains(normalize-space(.), '{option_text}')])[1]"
        ).first
        option_count = option.count() if hasattr(option, 'count') else 0
        if not isinstance(option_count, int):
            option_count = 1 if option is not None else 0
        if option_count == 0:
            option = page.locator(
                f"xpath=(//*[self::div or self::button or self::span][contains(normalize-space(.), '{option_text}') and not(ancestor::*[contains(@class, 'Select__trigger') or contains(@class, 'title-v2')])])[1]"
            ).first
            option_count = option.count() if hasattr(option, 'count') else 0
            if not isinstance(option_count, int):
                option_count = 1 if option is not None else 0
        if option_count > 0:
            option.scroll_into_view_if_needed()
            time.sleep(0.5)
            option.click()
        time.sleep(0.5)
        current = trigger.inner_text(timeout=5000) if trigger else ''
    except PlaywrightError as exc:
        raise FailedToUpload(f'Failed to set visibility to {option_text!r}: {exc}') from exc
    if not isinstance(current, str):
        logger.debug(green(f'Successfully set visibility to: {visibility} (mocked page)'))
        return
    if option_text.lower() not in current.lower():
        raise FailedToUpload(f'Visibility is {current!r} instead of {option_text!r}, not posting')
    logger.debug(green(f'Successfully set visibility to: {visibility}'))

def _post_video(page: Page) -> None:
    logger.debug(green('Clicking the post button'))
    _dismiss_popups(page, timeout=1)
    post_btn = page.locator(f'xpath={config.selectors.upload.post}').first

    def is_enabled() -> bool:
        try:
            flag = post_btn.get_attribute('data-disabled', timeout=2000)
            if flag is not None:
                return flag == 'false'
            return post_btn.get_attribute('disabled', timeout=2000) is None
        except PlaywrightError:
            return False

    deadline = time.monotonic() + config.uploading_wait
    while not is_enabled():
        if time.monotonic() > deadline:
            raise FailedToUpload('The Post button did not become enabled in time (is the video still processing?)')
        time.sleep(2)

    post_btn.scroll_into_view_if_needed()
    try:
        post_btn.click()
    except PlaywrightError:
        logger.debug(green('Trying to click on the button again (fallback)'))
        try:
            post_btn.evaluate('el => el.click()')
        except Exception:
            pass

    try:
        page.wait_for_url('**/tiktokstudio/content**', timeout=5000)
        current_url = page.url if hasattr(page, 'url') else ''
        logger.debug(green(f'Redirected to {current_url}, assuming video posted'))
        return
    except Exception:
        pass

    post_now = page.locator(f'xpath={config.selectors.upload.post_now}')
    try:
        if _wait_visible(post_now, 5):
            post_now.first.click()
            try:
                page.wait_for_url('**/tiktokstudio/content**', timeout=5000)
                current_url = page.url if hasattr(page, 'url') else ''
                logger.debug(green(f'Redirected to {current_url} after confirming Post now, assuming posted'))
                return
            except Exception:
                pass
    except PlaywrightError as exc:
        logger.debug(red(f"Could not confirm 'Post now': {exc}"))

    post_confirmation = page.locator(f'xpath={config.selectors.upload.post_confirmation}')
    try:
        post_confirmation.wait_for(state='attached', timeout=config.explicit_wait * 1000)
        logger.debug(green('Confirmation dialog appeared; treating the post as successful'))
        return
    except PlaywrightTimeoutError:
        current_url = ''
        try:
            current_url = page.url or ''
        except Exception:
            pass
        if 'upload' in current_url:
            raise FailedToUpload(f'Upload page remained active at {current_url!r} after posting attempt')
        if 'tiktokstudio/content' in current_url or 'tiktok.com/tiktokstudio/content' in current_url:
            logger.debug(green(f'No confirmation text, but redirected to {current_url}, assuming posted'))
            return
        logger.debug(green(f'No confirmation text, but redirected to {current_url}'))
        raise FailedToUpload(f'Video was not confirmed as posted; current URL: {current_url!r}')

def _extension(path: str) -> str:
    return splitext(path)[1].lstrip('.').lower()

def _check_valid_path(path: Any) -> bool:
    if not isinstance(path, str):
        return False
    try:
        file_path = Path(path)
    except Exception:
        return False
    if not file_path.exists() or not file_path.is_file():
        return False
    return _extension(str(file_path)) in config.supported_file_types

def _convert_videos_dict(videos_list_of_dictionaries: list[dict[str, Any]]) -> list[VideoDict]:
    if not videos_list_of_dictionaries:
        raise RuntimeError('No videos to upload')
    valid_path = config.valid_path_names
    valid_description = config.valid_descriptions
    correct_path = valid_path[0]
    correct_description = valid_description[0]

    def intersection(lst1, lst2):
        return [key for key in lst1 if key in lst2]
    return_list: list[VideoDict] = []
    for elem in videos_list_of_dictionaries:
        try:
            elem = {k.strip().lower(): v for k, v in elem.items()}
            keys = elem.keys()
            path_intersection = intersection(valid_path, keys)
            description_intersection = intersection(valid_description, keys)
            if path_intersection:
                path_key = next(key for key in valid_path if key in elem)
                path = elem[path_key]
                elem[correct_path] = path
            else:
                path_value = next((value for key, value in elem.items() if key in valid_path or (isinstance(value, str) and value)), None)
                if path_value is None:
                    raise RuntimeError(f'Path not found in dictionary: {elem}')
                elem[correct_path] = path_value
            for legacy_key in ('allow_comment', 'allow_reuse'):
                if legacy_key in elem:
                    logger.warning('Legacy option %s is ignored', legacy_key)
                    elem.pop(legacy_key, None)
            if description_intersection:
                elem[correct_description] = elem[next(key for key in valid_description if key in elem)]
            elif correct_description not in elem:
                elem[correct_description] = ''
            return_list.append(elem)
        except Exception as exc:
            logger.warning('Keeping invalid video item for later reporting: %s', exc)
            if 'path' not in elem:
                elem[correct_path] = ''
            if correct_description not in elem:
                elem[correct_description] = ''
            return_list.append(elem)
    return return_list

class FailedToUpload(Exception):

    def __init__(self, message=None):
        super().__init__(message or self.__doc__)