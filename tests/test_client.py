import os
from unittest.mock import MagicMock, patch

from tiktok_video_uploader.upload import TikTokUploader

FILENAME = 'test.mp4'

def setup_function() -> None:
    with open(FILENAME, 'w', encoding='utf-8') as file:
        file.write('test')

def teardown_function() -> None:
    if os.path.exists(FILENAME):
        os.remove(FILENAME)

@patch('tiktok_video_uploader.upload.get_browser')
@patch('tiktok_video_uploader.auth.AuthBackend.authenticate_agent')
@patch('tiktok_video_uploader.upload.complete_upload_form')
def test_tiktok_uploader_lazy_loading(mock_complete_upload, mock_auth, mock_browser) -> None:
    mock_page = MagicMock()
    mock_browser.return_value = mock_page
    mock_auth.return_value = mock_page
    uploader = TikTokUploader(sessionid='test_session')
    mock_browser.assert_not_called()
    uploader.upload_video(FILENAME, description='Test')
    mock_browser.assert_called_once()
    mock_auth.assert_called_once()
    mock_complete_upload.assert_called_once()

@patch('tiktok_video_uploader.upload.get_browser')
@patch('tiktok_video_uploader.auth.AuthBackend.authenticate_agent')
@patch('tiktok_video_uploader.upload.complete_upload_form')
def test_tiktok_uploader_reuse_browser(mock_complete_upload, mock_auth, mock_browser) -> None:
    mock_page = MagicMock()
    mock_browser.return_value = mock_page
    mock_auth.return_value = mock_page
    uploader = TikTokUploader(sessionid='test_session')
    uploader.upload_video(FILENAME, description='Test 1')
    uploader.upload_video(FILENAME, description='Test 2')
    mock_browser.assert_called_once()
    mock_auth.assert_called_once()
    assert mock_complete_upload.call_count == 2