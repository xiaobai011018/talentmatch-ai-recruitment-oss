"""
----------------------------------------------------
 File Name:        http_retry
 Author:           hoges
 Created Date:     2025/9/22
 Last Modified:    2025/9/22
 Python Version:   
----------------------------------------------------
"""
import json
import time
import functools
from backend.logger.logger import get_logger
import requests

NETWORK_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.RequestException,
    json.JSONDecodeError
)


def http_retry(HTTP_RETRY_TIMES = 3, HTTP_RETRY_GAP = 1):
    """
    一个重试装饰器
    最大重试次数和重试间隔从 RetryConfig 里读取
    :param exceptions: 需要捕获的异常类型，默认捕获所有 Exception
    """
    logger = get_logger(__name__)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            trace_id = kwargs.get('trace_id') or 'none'
            started_at = time.perf_counter()
            for attempt in range(1, HTTP_RETRY_TIMES + 1):
                try:
                    return func(*args, **kwargs)
                except NETWORK_EXCEPTIONS as e:
                    last_exception = e
                    logger.warning(
                        f"[Retry] trace_id={trace_id} function={func.__qualname__} "
                        f"attempt={attempt}/{HTTP_RETRY_TIMES} exception_type={type(e).__name__} reason={e}"
                    )
                    if attempt < HTTP_RETRY_TIMES:
                        time.sleep(HTTP_RETRY_GAP)
            # 如果所有重试都失败，抛出最后一次异常
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            logger.error(
                f"[Retry] trace_id={trace_id} function={func.__qualname__} status=exhausted "
                f"attempts={HTTP_RETRY_TIMES} elapsed_ms={elapsed_ms} "
                f"exception_type={type(last_exception).__name__} reason={last_exception}",
                exc_info=(type(last_exception), last_exception, last_exception.__traceback__),
            )
            raise last_exception

        return wrapper

    return decorator
