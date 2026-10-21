"""Apply local service values to the open-source snapshot, without network calls."""
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 tools/configure_services.py config.local.json')
    config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    allowed = json.loads((ROOT / 'config.example.json').read_text(encoding='utf-8'))
    if not isinstance(config, dict) or set(config) - set(allowed):
        raise SystemExit('Configuration must be an object containing only example keys')
    values = {}
    for key, value in config.items():
        if not isinstance(value, str):
            raise SystemExit('Configuration values must be strings')
        if not value or value == allowed[key]:
            continue
        if key.startswith('https://'):
            parsed = urlsplit(value)
            if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
                    or parsed.password or parsed.path not in ('', '/')
                    or parsed.query or parsed.fragment
                    or not re.fullmatch(r'https://[A-Za-z0-9.:-]+/?', value)):
                raise SystemExit('Service addresses must be HTTPS origins without credentials')
            values[key] = value.rstrip('/')
        else:
            if not re.fullmatch(r'[A-Za-z0-9_+/=.-]+', value):
                raise SystemExit('Model and user IDs must contain only identifier characters')
            values[key] = value
    changed = 0
    for path in (ROOT / 'apps').rglob('*'):
        if not path.is_file() or path.suffix not in ('.js', '.py', '.json', '.html', '.md', '.ts', '.vue'):
            continue
        text = path.read_text(encoding='utf-8')
        updated = text
        for key, value in values.items():
            updated = updated.replace(key, value)
        if updated != text:
            path.write_text(updated, encoding='utf-8')
            changed += 1
    print(f'Updated {changed} files locally. Do not commit configured source or credentials.')


if __name__ == '__main__':
    main()
