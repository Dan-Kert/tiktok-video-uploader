# TikTok Video Uploader

Python toolkit for uploading videos to TikTok through a real browser session and browser-authenticated state.

This project uses Playwright and interacts with TikTok through the web UI. It is not an official TikTok API client.

## Features

- Upload a single video or multiple videos in one run
- Set a description and optional visibility (`everyone`, `friends`, `only_you`)
- Authenticate with a cookies file, session ID, cookies list/string, or username/password
- Use it from the CLI or import it as a Python library
- Works with Chromium, Chrome, Firefox, WebKit, and Edge via Playwright

## Requirements

- Python 3.12+
- Playwright browser binaries installed
- A valid TikTok account with usable cookies or a session

## Installation

```bash
python -m pip install -e .
python -m playwright install
```

For local development:

```bash
python -m pip install -e '.[dev]'
```

## Quick start

### Supported options

| Option | CLI form | Python form | Purpose |
| --- | --- | --- | --- |
| video | `-v`, `--video` | `filename` | Path to the video file |
| description | `-d`, `--description` | `description` | Caption / text for the post |
| visibility | `--visibility` | `visibility` | Optional visibility: `everyone`, `friends`, `only_you` |
| proxy | `--proxy` | `proxy` | Proxy in `user:pass@host:port` or `host:port` format |
| cookies | `-c`, `--cookies` | `cookies` | Path to a cookies file |
| sessionid | `-s`, `--sessionid` | `sessionid` | TikTok session ID |
| username | `-u`, `--username` | `username` | TikTok login name or email |
| password | `-p`, `--password` | `password` | TikTok password |
| browser | `--browser` | `browser` | Browser engine: `chromium`, `chrome`, `firefox`, `webkit`, `edge` |
| attach | `-a`, `--attach` | `headless=False` | Open browser window instead of headless mode |
| verbose | `-V`, `--verbose` | logging config | Extra debug output |

### Command structure

```bash
tiktok-uploader -v <video_path> -d "<description>" -c <cookies.txt> [--visibility <everyone|friends|only_you>] [--proxy <proxy>] [--browser <browser>] [--attach] [-V]
```

Examples:

```bash
tiktok-uploader -v video.mp4 -d "Hello from TikTok uploader #python" -c cookies.txt

tiktok-uploader -v video.mp4 -d "Only for friends" -c cookies.txt --visibility friends --attach

tiktok-uploader -v video.mp4 -d "Upload via browser session" -s <sessionid> --browser chromium -V
```

### Python library

```python
from tiktok_video_uploader import TikTokUploader

uploader = TikTokUploader(cookies='cookies.txt', headless=False)
result = uploader.upload_video(
    filename='video.mp4',
    description='My first upload from Python #python #tiktok',
    visibility='friends',
)

print('Upload success:', result)
```

### Batch upload

```python
from tiktok_video_uploader import TikTokUploader
from tiktok_video_uploader.types import VideoDict

videos: list[VideoDict] = [
    {'path': 'video1.mp4', 'description': 'First upload #python'},
    {'path': 'video2.mp4', 'description': 'Second upload #automation', 'visibility': 'friends'},
]

uploader = TikTokUploader(cookies='cookies.txt', headless=False)
failed = uploader.upload_videos(videos)
print(f'Failed uploads: {failed}')
```

### CLI help

```bash
python -m tiktok_video_uploader --help
```

Or after installing the package:

```bash
tiktok-uploader --help
```

## Authentication

The library supports:

- cookies file (`--cookies` / `cookies=`)
- session ID (`--sessionid` / `sessionid=`)
- cookies list or cookies string
- username + password

Using a real browser session and cookies is the most reliable option because TikTok login and upload flow depend on browser state.

## Notes

- This project does not use an official TikTok public API.
- It relies on browser automation and user-authenticated browser state.
- TikTok selectors can change, so uploads may require periodic updates.
- Use only with your own account and in line with TikTok rules and platform policies.
- Legacy toggles like old “AI”, “allow-comment”, or “allow-reuse” flags are intentionally not part of the current interface.

## Example scripts

Scripts are available in the [examples](examples) folder:

- [examples/basic_upload.py](examples/basic_upload.py)
- [examples/multiple_videos_at_once.py](examples/multiple_videos_at_once.py)
- [examples/private_upload.py](examples/private_upload.py)
- [examples/series_upload.py](examples/series_upload.py)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Repository

- GitHub: https://github.com/Dan-Kert/tiktok-video-uploader
