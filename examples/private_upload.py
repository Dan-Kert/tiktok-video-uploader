from pathlib import Path

from tiktok_video_uploader import TikTokUploader

ROOT = Path(__file__).resolve().parents[1]
COOKIES_PATH = ROOT / 'cookies.txt'

if __name__ == '__main__':
    if not COOKIES_PATH.exists():
        raise FileNotFoundError(f'Cookies file not found: {COOKIES_PATH}')

    uploader = TikTokUploader(cookies=str(COOKIES_PATH), headless=False)
    uploader.upload_video(
        filename=str(ROOT / 'video_private.mp4'),
        description='Only visible to me #private',
        visibility='only_you',
    )
    uploader.upload_video(
        filename=str(ROOT / 'video_friends.mp4'),
        description='Visible only to friends #friends',
        visibility='friends',
    )