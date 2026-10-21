import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.core.router.search_condition_router import delete_cookies_file
from backend.core.utils.path_util import path_util


def _expect_http_error(status_code, callback):
    try:
        callback()
    except HTTPException as exc:
        assert exc.status_code == status_code, exc
    else:
        raise AssertionError(f"expected HTTP {status_code}")


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        cookies_dir = root / "cookies"
        cookies_dir.mkdir()
        cookie_file = cookies_dir / "cookies张三_converted.txt"
        cookie_file.write_text("[]", encoding="utf-8")
        outside_file = root / "outside.txt"
        outside_file.write_text("keep", encoding="utf-8")

        with patch.object(path_util, "get_cookies_path", return_value=str(cookies_dir)):
            result = delete_cookies_file(cookie_file.name)
            assert result["fileName"] == cookie_file.name
            assert not cookie_file.exists()

            _expect_http_error(404, lambda: delete_cookies_file(cookie_file.name))
            _expect_http_error(400, lambda: delete_cookies_file("../outside.txt"))

        assert outside_file.read_text(encoding="utf-8") == "keep"

    print("cookie delete tests passed")


if __name__ == "__main__":
    main()
