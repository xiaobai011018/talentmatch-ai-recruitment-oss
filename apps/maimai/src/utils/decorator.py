"""
@describe:
@fileName: decorator.py
@time    : 2025/9/19 14:08
@author  : duke
"""
from src.exceptions import HTTPRetryException, AccessForbiddenException, CookiesExpiredException
from src.config.maimai import COOKIES_EXPIRED_KEYWORD
import time


def http_retry(times, gap):
    def decorator(func):
        def wrapper(*args, **kwargs):
            resp = None
            for i in range(times):
                try:
                    resp = func(*args, **kwargs)
                except:
                    if i + 1 < times:
                        continue
                    raise
                if resp.ok or resp.status_code == 200:
                    return resp
                if resp.status_code == 403:
                    if COOKIES_EXPIRED_KEYWORD in resp.reason or COOKIES_EXPIRED_KEYWORD in resp.text:
                        raise CookiesExpiredException(resp)
                    raise AccessForbiddenException(resp)
                time.sleep(gap)
            raise HTTPRetryException(resp, times)

        return wrapper

    return decorator
