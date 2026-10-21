"""
----------------------------------------------------
 File Name:        FilePathUtils
 Author:           hoges
 Created Date:     2025/10/17
 Last Modified:    2025/10/17
 Python Version:   
----------------------------------------------------
"""
import os
from pathlib import Path
import sys


def get_root_path():
    if getattr(sys, 'frozen', False):
        BASE_DIR = sys._MEIPASS
    else:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    return Path(BASE_DIR)

def get_backend_path() -> Path:
    """
    返回 backend 目录路径
    
    Returns:
        Path: backend 目录的 Path 对象
    """
    return get_root_path() / "backend"


def get_frontend_path() -> Path:
    """
    返回 frontend 目录路径
    
    Returns:
        Path: frontend 目录的 Path 对象
    """
    return get_root_path() / "frontend"


def get_save_path() -> Path:
    root_path = get_root_path()
    if getattr(sys,'frozen',False):
        save_path = os.path.join(os.path.dirname(root_path),'save')
    else:
        save_path = os.path.join(root_path,'save')

    return Path(save_path)


def get_excel_result_dir() -> Path:
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = get_root_path()
    return base_dir / 'save' / 'excel_results'


def get_shared_appdata_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "AnyHelper"
    return Path.home() / ".anyhelper"


def resolve_cookie_path(file_name: str) -> Path:
    candidate = Path(str(file_name).strip().strip('"'))
    if candidate.is_file():
        return candidate

    local_path = get_save_path() / "cookies" / candidate.name
    if local_path.is_file():
        return local_path

    shared_path = get_shared_appdata_path() / "cookies" / "liepin" / candidate.name
    if shared_path.is_file():
        return shared_path

    # 返回本地默认路径，保留原有报错语义。
    return local_path


def resolve_excel_path(file_name: str) -> Path:
    candidate = Path(str(file_name).strip().strip('"'))
    if candidate.is_file():
        return candidate

    local_path = get_save_path() / "excel" / candidate.name
    if local_path.is_file():
        return local_path

    shared_path = get_shared_appdata_path() / "excel" / candidate.name
    if shared_path.is_file():
        return shared_path

    return local_path


def get_logs_path() -> Path:
    """
    返回 logs 目录路径
    
    Returns:
        Path: logs 目录的 Path 对象
    """
    return get_backend_path() / "core" / "logs"


def ensure_dir_exists(path: Path) -> Path:
    """
    确保目录存在，如果不存在则创建
    
    Args:
        path: 要确保存在的目录路径
        
    Returns:
        Path: 目录路径对象
    """
    path.mkdir(parents=True, exist_ok=True)
    return path
