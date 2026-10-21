__version__ = "2.1.55"
__author__ = "Duke"

_CONFIG = {
    "dev": False,
}

# 静态提升
# from .manager import Manager
# from .config.http import TEMPLATE_FLASK_RESP
# from .exceptions import *
# from .config.web_gui import ROOT_PATH, WEB_PATH, PORT


# 动态导入
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 仅类型检查，不实际执行
    from .manager import Manager
    from .config.http import TEMPLATE_FLASK_RESP
    from .config.path import ROOT_PATH, WEB_PATH, SAVE_PATH, RSC_DIR, SAVE_FILE_DIR
    from .config.web_gui import PORT
else:
    # 注册表
    _LAZY_IMPORTS = {
        'Manager': ('.manager', 'Manager'),
        'TEMPLATE_FLASK_RESP': ('.config.http', 'TEMPLATE_FLASK_RESP'),
        'ROOT_PATH': ('.config.path', 'ROOT_PATH'),
        'WEB_PATH': ('.config.path', 'WEB_PATH'),
        'SAVE_PATH': ('.config.path', 'SAVE_PATH'),
        'SAVE_FILE_DIR': ('.config.path', 'SAVE_FILE_DIR'),
        'RSC_DIR': ('.config.path', 'RSC_DIR'),
        'PORT': ('.config.web_gui', 'PORT'),
    }

_import_cache = {}


# 不存在属性访问控制
def __getattr__(name):
    if name in _LAZY_IMPORTS:
        if name not in _import_cache:
            module_path, attr_name = _LAZY_IMPORTS[name]
            module = __import__(f'src{module_path}', fromlist=[attr_name])
            _import_cache[name] = getattr(module, attr_name)
        return _import_cache[name]

    raise AttributeError(f"module 'src' has no attribute '{name}'")


# 显式控制 import * 行为
__all__ = ['_CONFIG'] + list(_LAZY_IMPORTS.keys())
