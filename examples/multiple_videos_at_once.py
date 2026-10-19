from pathlib import Path

from tiktok_video_uploader import TikTokUploader
from tiktok_video_uploader.types import VideoDict

ROOT = Path(__file__).resolve().parents[1]
COOKIES_PATH = ROOT / 'cookies.txt'
VIDEOS: list[VideoDict] = [
    {'path': str(ROOT / 'video1.mp4'), 'description': 'First upload in a batch #python #automation'},
    {
        'path': str(ROOT / 'video2.mp4'),
        'description': 'Second upload in a batch #contentcreator',
        'visibility': 'friends',
    },
]

if __name__ == '__main__':
    for item in VIDEOS:
        if not Path(item['path']).exists():
            raise FileNotFoundError(f"Video not found: {item['path']}")
    if not COOKIES_PATH.exists():
        raise FileNotFoundError(f'Cookies file not found: {COOKIES_PATH}')

    uploader = TikTokUploader(cookies=str(COOKIES_PATH), headless=False)
    failed = uploader.upload_videos(VIDEOS)
    if failed:
        print('Failed videos:', failed)
    else:
        print('All videos uploaded successfully.')