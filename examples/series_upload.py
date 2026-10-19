from pathlib import Path

from tiktok_video_uploader import TikTokUploader

ROOT = Path(__file__).resolve().parents[1]
COOKIES_PATH = ROOT / 'cookies.txt'
QUEUE = [
    {'path': str(ROOT / 'video1.mp4'), 'description': 'Daily upload #1'},
    {'path': str(ROOT / 'video2.mp4'), 'description': 'Daily upload #2'},
    {'path': str(ROOT / 'video3.mp4'), 'description': 'Daily upload #3'},
]

if __name__ == '__main__':
    if not COOKIES_PATH.exists():
        raise FileNotFoundError(f'Cookies file not found: {COOKIES_PATH}')
    for item in QUEUE:
        if not Path(item['path']).exists():
            raise FileNotFoundError(f"Video not found: {item['path']}")

    uploader = TikTokUploader(cookies=str(COOKIES_PATH), headless=False)
    failed = uploader.upload_videos(QUEUE)
    if failed:
        print('Failed uploads:', failed)
    else:
        print('Queue processed successfully.')