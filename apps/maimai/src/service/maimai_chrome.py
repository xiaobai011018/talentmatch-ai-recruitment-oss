"""
@describe:
@fileName: maimai_chrome.py
@time    : 2025/10/27 上午10:24
@author  : duke
"""
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from src.config.path import CHROME_DRIVER_PATH
from src.config.maimai import MM_COOKIES_DEFAULT_LEN


def _chrome_service():
    if os.path.isfile(CHROME_DRIVER_PATH):
        return Service(CHROME_DRIVER_PATH)
    # 本地无驱动时由 Selenium Manager 自动匹配 Chrome 版本
    return Service()


def login():
    """
    :return: dict of cookies
    """
    wd = webdriver.Chrome(service=_chrome_service())
    wd.get('https://maimai.cn/platform/login')
    cookies = None
    while wd.session_id is not None:
        cookies = wd.get_cookies()
        if len(cookies) > MM_COOKIES_DEFAULT_LEN:
            break
        time.sleep(1)
    wd.quit()

    return cookies
