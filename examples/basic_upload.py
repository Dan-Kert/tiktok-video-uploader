from pathlib import Path

from tiktok_video_uploader import TikTokUploader

ROOT = Path(__file__).resolve().parents[1]
VIDEO_PATH = ROOT / 'video.mp4'
COOKIES_PATH = ROOT / 'cookies.txt'

if __name__ == '__main__':
    if not VIDEO_PATH.exists():
        raise FileNotFoundError(f'Video not found: {VIDEO_PATH}')
    if not COOKIES_PATH.exists():
        raise FileNotFoundError(f'Cookies file not found: {COOKIES_PATH}')

    uploader = TikTokUploader(cookies=str(COOKIES_PATH), headless=False)
    uploader.upload_video(
        filename=str(VIDEO_PATH),
        description='Sample upload from the library #python #tiktok #automation',
        visibility='friends',
    )