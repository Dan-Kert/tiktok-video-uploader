import logging
from os.path import abspath, dirname, join

from .settings import load_config

config_dir = abspath(dirname(__file__))
config = load_config(join(config_dir, 'config.toml'))

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

__all__ = ['TikTokUploader', 'upload_video', 'upload_videos']


def __getattr__(name: str):
    if name in __all__:
        from .upload import TikTokUploader, upload_video, upload_videos

        values = {
            'TikTokUploader': TikTokUploader,
            'upload_video': upload_video,
            'upload_videos': upload_videos,
        }
        value = values[name]
        globals()[name] = value
        return value
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')