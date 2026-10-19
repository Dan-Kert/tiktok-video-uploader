from pathlib import Path
from typing import Annotated

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

NonNegativeSeconds = Annotated[int, Field(ge=0)]

class Paths(StrictModel):
    main: HttpUrl
    login: HttpUrl
    upload: HttpUrl

class Disguising(StrictModel):
    user_agent: str

    @field_validator('user_agent')
    @classmethod
    def _ua_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('user_agent must be non-empty')
        return v

class CookiesBanner(StrictModel):
    banner: str
    button: str

class LoginSelectors(StrictModel):
    username_field: str
    password_field: str
    login_button: str
    alert_user_if_failed: bool
    cookie_of_interest: str

class UploadSelectors(StrictModel):
    split_window: str
    upload_video: str
    upload_finished: str
    process_confirmation: str
    description: str
    mention_box: str
    mention_box_user_id: str
    post: str
    post_now: str
    post_confirmation: str
    cookies_banner: CookiesBanner

class Selectors(StrictModel):
    login: LoginSelectors
    upload: UploadSelectors

class TikTokConfig(StrictModel):
    quit_on_end: bool
    valid_path_names: list[str]
    valid_descriptions: list[str]
    implicit_wait: NonNegativeSeconds
    explicit_wait: NonNegativeSeconds
    uploading_wait: NonNegativeSeconds
    captcha_wait: NonNegativeSeconds
    add_hashtag_wait: NonNegativeSeconds
    supported_file_types: list[str]
    paths: Paths
    disguising: Disguising
    selectors: Selectors

    @field_validator('valid_path_names', 'valid_descriptions')
    @classmethod
    def _nonempty_unique(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError('list must be non-empty')
        stripped = [s.strip() for s in v]
        if any((not s for s in stripped)):
            raise ValueError('list entries must be non-empty strings')
        if len(set(map(str.lower, stripped))) != len(stripped):
            raise ValueError('list entries must be unique (case-insensitive)')
        return stripped

    @field_validator('supported_file_types')
    @classmethod
    def _extensions(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError('supported_file_types must be non-empty')
        for ext in v:
            if not ext or any((ch in ext for ch in '. /\\')):
                raise ValueError(f'invalid file extension: {ext!r}')
            if ext.lower() != ext:
                raise ValueError(f'file extensions must be lowercase: {ext!r}')
        if len(set(v)) != len(v):
            raise ValueError('supported_file_types must be unique')
        return v

def load_config(path: str | Path) -> TikTokConfig:
    p = Path(path)
    with p.open('rb') as file:
        data = tomllib.load(file)
    return TikTokConfig.model_validate(data)