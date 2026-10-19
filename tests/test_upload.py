import os
from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock, patch

from pytest import raises

from tiktok_video_uploader.auth import InsufficientAuth
from tiktok_video_uploader.browsers import close_browser
from tiktok_video_uploader.cli import parse_proxy
from tiktok_video_uploader.types import VideoDict
from tiktok_video_uploader.upload import (
    FailedToUpload,
    TikTokUploader,
    _check_valid_path,
    _convert_videos_dict,
    _dismiss_blocking_modal,
    _post_video,
    upload_video,
    upload_videos,
)

FILENAME = 'test.mp4'

def setup_function() -> None:
    Path(FILENAME).write_bytes(b'test')

def teardown_function() -> None:
    if os.path.exists(FILENAME):
        os.remove(FILENAME)

def test_convert_videos_dict_with_visibility() -> None:
    video_dict = {'path': FILENAME, 'description': 'Private video', 'visibility': 'only_you'}
    array = _convert_videos_dict([video_dict])
    assert array[0]['path'] == FILENAME
    assert array[0]['description'] == 'Private video'
    assert array[0]['visibility'] == 'only_you'

def test_visibility_parameter_validation() -> None:
    valid_visibilities: list[Literal['everyone', 'friends', 'only_you']] = ['everyone', 'friends', 'only_you']
    for visibility in valid_visibilities:
        video_dict = {'path': FILENAME, 'description': f'Video with {visibility} visibility', 'visibility': visibility}
        array = _convert_videos_dict([video_dict])
        assert array[0]['visibility'] == visibility

def test_dismiss_blocking_modal_handles_english_buttons() -> None:
    page = MagicMock()
    overlay = MagicMock()
    overlay.first.wait_for.return_value = None

    not_now_button = MagicMock()
    not_now_button.is_visible.return_value = True
    not_now_button.inner_text.return_value = 'Not now'

    page.locator.side_effect = lambda selector: overlay if 'TUXModal-overlay' in selector else (
        MagicMock(all=lambda: [not_now_button]) if 'TUXModal' in selector else MagicMock(all=lambda: [])
    )

    _dismiss_blocking_modal(page, timeout=1)
    not_now_button.click.assert_called_once()
    page.keyboard.press.assert_not_called()

@patch('tiktok_video_uploader.upload.get_browser')
@patch('tiktok_video_uploader.auth.AuthBackend.authenticate_agent')
@patch('tiktok_video_uploader.upload.complete_upload_form')
def test_upload_video_with_visibility(mock_complete_upload, mock_auth, mock_browser) -> None:
    mock_page = MagicMock()
    mock_browser.return_value = mock_page
    mock_auth.return_value = mock_page
    upload_video(filename=FILENAME, description='Test private video', sessionid='test_session', visibility='only_you')
    mock_complete_upload.assert_called_once()
    call_args = mock_complete_upload.call_args
    assert call_args.kwargs['visibility'] == 'only_you'
    mock_complete_upload.reset_mock()
    upload_video(filename=FILENAME, description='Test friends video', sessionid='test_session', visibility='friends')
    call_args = mock_complete_upload.call_args
    assert call_args.kwargs['visibility'] == 'friends'
    mock_complete_upload.reset_mock()
    upload_video(filename=FILENAME, description='Test public video', sessionid='test_session')
    call_args = mock_complete_upload.call_args
    assert call_args.kwargs['visibility'] is None

def test_set_visibility_dropdown_interaction() -> None:
    from tiktok_video_uploader.upload import _set_visibility

    mock_page = MagicMock()
    dropdown_target = MagicMock()
    dropdown_target.inner_text.return_value = 'Only you'
    dropdown_target.click = MagicMock()
    dropdown = MagicMock()
    dropdown.count.return_value = 1
    dropdown.first = dropdown_target
    option_target = MagicMock()
    option_target.scroll_into_view_if_needed = MagicMock()
    option_target.click = MagicMock()
    option = MagicMock()
    option.count.return_value = 1
    option.first = option_target

    def locator_side_effect(selector: str):
        if 'Select__trigger' in selector or 'Who can see this post' in selector:
            return dropdown
        if 'Only you' in selector or 'Friends' in selector:
            return option
        return MagicMock()

    mock_page.locator.side_effect = locator_side_effect

    _set_visibility(mock_page, 'only_you')
    dropdown_target.click.assert_called_once()
    option_target.scroll_into_view_if_needed.assert_called_once()
    option_target.click.assert_called_once()

def test_check_valid_path_requires_existing_file(tmp_path):
    missing = tmp_path / 'missing.mp4'
    assert _check_valid_path(str(missing)) is False
    valid = tmp_path / 'valid.mp4'
    valid.write_bytes(b'1234')
    assert _check_valid_path(str(valid)) is True

def test_parse_proxy_handles_password_with_special_chars() -> None:
    parsed = parse_proxy('user:p@ss@word@127.0.0.1:8080')
    assert parsed['user'] == 'user'
    assert parsed['password'] == 'p@ss@word'
    assert parsed['host'] == '127.0.0.1'
    assert parsed['port'] == '8080'

def test_insufficient_auth_has_default_message() -> None:
    exc = InsufficientAuth()
    assert 'Authentication' in str(exc) or 'auth' in str(exc).lower()

def test_post_video_raises_on_false_success() -> None:
    page = MagicMock()
    post_btn = MagicMock()
    post_btn.get_attribute.side_effect = ['false', None]
    page.locator.return_value = post_btn
    page.url = 'https://www.tiktok.com/creator-center/upload?lang=en'
    page.wait_for_url.side_effect = [Exception('no redirect'), Exception('no redirect')]

    with raises(FailedToUpload):
        _post_video(page)

def test_post_video_ignores_upload_url_after_confirmation() -> None:
    page = MagicMock()
    post_btn = MagicMock()
    post_btn.first = post_btn
    post_btn.get_attribute.side_effect = ['false', None]
    page.locator.return_value = post_btn
    page.url = 'https://www.tiktok.com/creator-center/upload?lang=en'
    page.wait_for_url.side_effect = [Exception('no redirect'), Exception('no redirect')]
    confirmation = MagicMock()
    confirmation.first = confirmation
    confirmation.wait_for.return_value = None
    page.locator.side_effect = lambda selector: confirmation if 'post_confirmation' in selector else post_btn

    _post_video(page)

def test_close_browser_stops_playwright() -> None:
    page = MagicMock()
    browser = MagicMock()
    playwright = MagicMock()
    page.context.browser = browser
    page._playwright = playwright

    close_browser(page)

    browser.close.assert_called_once()
    playwright.stop.assert_called_once()

def test_main_requests_password_before_validate(monkeypatch) -> None:
    class DummyUploader:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def upload_video(self, **kwargs):
            return True

    monkeypatch.setattr('sys.argv', ['tiktok-uploader', '-v', 'video.mp4', '-u', 'user'])
    monkeypatch.setattr('os.path.exists', lambda _: True)
    monkeypatch.setattr('tiktok_video_uploader.cli.getpass.getpass', lambda prompt: 'secret')
    monkeypatch.setattr('tiktok_video_uploader.cli.TikTokUploader', DummyUploader)
    called = {}

    def fake_validate(args):
        called['password'] = args.password

    monkeypatch.setattr('tiktok_video_uploader.cli.validate_uploader_args', fake_validate)
    from tiktok_video_uploader import cli
    cli.main()
    assert called['password'] == 'secret'

def test_upload_videos_invalid_path_is_only_reported_once() -> None:
    uploader = TikTokUploader(sessionid='abc')
    uploader._page = MagicMock()
    failed = uploader.upload_videos([{'path': 'missing.mp4'}])
    assert len(failed) == 1
    assert failed[0]['path'] == 'missing.mp4'

def test_set_visibility_none_does_nothing() -> None:
    from tiktok_video_uploader.upload import _set_visibility

    page = MagicMock()
    _set_visibility(page, None)
    page.locator.assert_not_called()

def test_video_dict_type_with_visibility() -> None:
    video: VideoDict = {'path': FILENAME, 'description': 'Test video', 'visibility': 'only_you'}
    assert video['visibility'] == 'only_you'
    visibility_options: list[Literal['everyone', 'friends', 'only_you']] = ['everyone', 'friends', 'only_you']
    for visibility_value in visibility_options:
        test_video: VideoDict = {'path': FILENAME, 'visibility': visibility_value}
        assert test_video['visibility'] == visibility_value

@patch('tiktok_video_uploader.upload.TikTokUploader.upload_videos')
@patch('tiktok_video_uploader.upload.TikTokUploader.close')
@patch('tiktok_video_uploader.auth.AuthBackend.authenticate_agent')
def test_upload_videos_with_browser_agent_authenticates(mock_authenticate_agent, _mock_close, mock_upload_videos) -> None:
    browser_agent = MagicMock()
    mock_authenticate_agent.return_value = browser_agent
    mock_upload_videos.return_value = []
    upload_videos(videos=[{'path': FILENAME}], sessionid='test_session', browser_agent=browser_agent)
    mock_authenticate_agent.assert_called_once_with(browser_agent)