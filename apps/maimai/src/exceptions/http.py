"""
@describe:
@fileName: http.py
@time    : 2025/9/19 14:12
@author  : duke
"""


class HTTPRetryException(RuntimeError):
    def __init__(self, resp, retry):
        super().__init__(f'code: {resp.status_code}, reason: {resp.reason}, text: {resp.text}, retry: {retry}')
        self.resp = resp


class InvalidRespJsonException(RuntimeError):
    def __init__(self, data, *args):
        super().__init__(*args)
        self.data = data


class AccessForbiddenException(RuntimeError):
    def __init__(self, resp, *args):
        super().__init__(*args)
        self.resp = resp


class CookiesExpiredException(AccessForbiddenException):
    def __init__(self, resp, *args):
        super().__init__(resp, *args)
