"""
----------------------------------------------------
 File Name:        http_retry
 Author:           hoges
 Created Date:     2025/9/22
 Last Modified:    2025/9/22
 Python Version:   
----------------------------------------------------
"""
import time
import functools
from backend.core.logger.logger import get_logger

def http_retry(HTTP_RETRY_TIMES = 3, HTTP_RETRY_GAP = 1, exceptions=(Exception,)):
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
            for attempt in range(1, HTTP_RETRY_TIMES + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.info(f"[Retry] 第 {attempt} 次失败: {e}")
                    if attempt < HTTP_RETRY_TIMES:
                        time.sleep(HTTP_RETRY_GAP)
            # 如果所有重试都失败，抛出最后一次异常
            raise last_exception

        return wrapper

    return decorator
