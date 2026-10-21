import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import HTTPException

from backend.router.search_condition_router import delete_cookies_file


class CookieFileDeletionTest(unittest.TestCase):
    def test_deletes_cookie_file_from_cookie_directory(self):
        with TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir)
            cookies_dir = save_path / 'cookies'
            cookies_dir.mkdir()
            cookie_file = cookies_dir / 'cookies张三_converted.txt'
            cookie_file.write_text('[]', encoding='utf-8')

            with patch(
                'backend.router.search_condition_router.get_save_path',
                return_value=save_path,
            ):
                result = delete_cookies_file('cookies张三_converted.txt')

            self.assertEqual(result, {
                'deleted': True,
                'fileName': 'cookies张三_converted.txt',
            })
            self.assertFalse(cookie_file.exists())

    def test_rejects_unsafe_file_names_without_deleting_outside_file(self):
        with TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir)
            outside_file = save_path / 'outside.json'
            outside_file.write_text('[]', encoding='utf-8')

            with patch(
                'backend.router.search_condition_router.get_save_path',
                return_value=save_path,
            ):
                unsafe_names = (
                    '../outside.json',
                    str(outside_file.resolve()),
                    '..\\outside.json',
                )
                for file_name in unsafe_names:
                    with self.subTest(file_name=file_name):
                        with self.assertRaises(HTTPException) as context:
                            delete_cookies_file(file_name)
                        self.assertEqual(context.exception.status_code, 400)

            self.assertTrue(outside_file.exists())

    def test_does_not_delete_cookie_directory(self):
        with TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir)
            directory = save_path / 'cookies' / 'nested'
            directory.mkdir(parents=True)

            with patch(
                'backend.router.search_condition_router.get_save_path',
                return_value=save_path,
            ):
                with self.assertRaises(HTTPException) as context:
                    delete_cookies_file('nested')

            self.assertEqual(context.exception.status_code, 404)
            self.assertTrue(directory.is_dir())

    def test_rejects_symlink_to_file_outside_cookie_directory(self):
        with TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir)
            cookies_dir = save_path / 'cookies'
            cookies_dir.mkdir()
            outside_file = save_path / 'outside.json'
            outside_file.write_text('[]', encoding='utf-8')
            link = cookies_dir / 'outside-link.json'
            link.symlink_to(outside_file)

            with patch(
                'backend.router.search_condition_router.get_save_path',
                return_value=save_path,
            ):
                with self.assertRaises(HTTPException) as context:
                    delete_cookies_file(link.name)

            self.assertEqual(context.exception.status_code, 400)
            self.assertTrue(outside_file.exists())

    def test_returns_not_found_for_missing_file(self):
        with TemporaryDirectory() as temp_dir:
            with patch(
                'backend.router.search_condition_router.get_save_path',
                return_value=Path(temp_dir),
            ):
                with self.assertRaises(HTTPException) as context:
                    delete_cookies_file('missing.json')

        self.assertEqual(context.exception.status_code, 404)


if __name__ == '__main__':
    unittest.main()
