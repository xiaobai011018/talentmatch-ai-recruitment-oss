import os
from pathlib import Path


def _load_project_env():
    env_path = Path(__file__).resolve().parents[2] / '.env'
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _get_int_env(key, default):
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


_load_project_env()

GLOBAL_SPIDER_EL_WAIT_TIME = _get_int_env('GLOBAL_SPIDER_EL_WAIT_TIME', 10)

edu_level_map = {
    '博士':'博士'
}