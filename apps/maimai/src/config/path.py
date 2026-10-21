"""
@describe:
@fileName: path.py
@time    : 2025/10/10 16:18
@author  : duke
"""
from src import _CONFIG
import os
import sys
from datetime import datetime


def _project_root():
    # src/config/path.py -> 项目根目录
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


if getattr(sys, 'frozen', False):
    # PyInstaller 打包后
    ROOT_PATH = os.path.dirname(os.path.abspath(sys.executable))
else:
    # 源码运行（含 python main.py / python main.py --dev）
    ROOT_PATH = _project_root()

if _CONFIG['dev']:
    WEB_PATH = os.path.join(ROOT_PATH, 'web_gui/dist')
else:
    WEB_PATH = os.path.join(ROOT_PATH, 'web')
    if not os.path.isdir(WEB_PATH):
        _dist = os.path.join(ROOT_PATH, 'web_gui/dist')
        if os.path.isdir(_dist):
            WEB_PATH = _dist

RSC_DIR = os.path.join(ROOT_PATH, 'resource')
SAVE_PATH = os.path.join(RSC_DIR, 'manager.pkl')
_chrome_driver_name = 'chromedriver.exe' if sys.platform == 'win32' else 'chromedriver'
CHROME_DRIVER_PATH = os.path.join(RSC_DIR, _chrome_driver_name)


LOG_DIR = os.path.join(ROOT_PATH, 'log')
LOG_PATH = os.path.join(LOG_DIR, f'{datetime.now().strftime("%Y-%m-%d")}.log')

SAVE_FILE_DIR = os.path.join(ROOT_PATH, 'save')

if not os.path.exists(LOG_DIR):
    os.mkdir(LOG_DIR)
if not os.path.exists(RSC_DIR):
    os.mkdir(RSC_DIR)

print(f'resource dir: {RSC_DIR}')
print(f'web path: {WEB_PATH}')
