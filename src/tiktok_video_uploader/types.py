# datetime import not required in types
from http import cookiejar
from http.cookiejar import Cookie as HttpCookie
from typing import Literal, TypedDict

HTTPONLY_ATTR = getattr(cookiejar, 'HTTPONLY_ATTR', 'HTTPOnly')

class ProxyDict(TypedDict, total=False):
    scheme: str
    user: str
    password: str
    host: str
    port: str

class VideoDict(TypedDict, total=False):
    path: str
    description: str
    visibility: Literal['everyone', 'friends', 'only_you']

class Cookie(TypedDict, total=False):
    name: str
    value: str
    domain: str
    path: str
    expiry: int
    expires: int
    sameSite: str
    secure: bool
    httpOnly: bool

def _expiry(data: Cookie) -> int | None:
    value = data.get('expiry') or data.get('expires')
    if value is None or value <= 0:
        return None
    return int(value)

def cookie_from_dict(data: Cookie) -> HttpCookie:
    return HttpCookie(0, data['name'], data['value'], None, False, data.get('domain', ''), bool(data.get('domain')), data.get('domain', '').startswith('.'), data.get('path', '/'), bool(data.get('path')), data.get('secure', False), _expiry(data), False, None, None, {HTTPONLY_ATTR: ''} if data.get('httpOnly') else {}, False)