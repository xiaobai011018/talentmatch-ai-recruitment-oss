import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from backend.service.SearchConditionService import SearchConditionService
from backend.utils.filePathUtils import FilePathUtils


class ExcelResultOutputTest(unittest.TestCase):
    def test_frozen_excel_result_dir_is_next_to_executable(self):
        with patch.object(FilePathUtils.sys, 'frozen', True, create=True), \
                patch.object(FilePathUtils.sys, 'executable', '/opt/AnyHelper/liepin-helper-api.exe'):
            result_dir = FilePathUtils.get_excel_result_dir()

        self.assertEqual(
            result_dir,
            Path('/opt/AnyHelper/save/excel_results'),
        )

    def test_excel_mode_creates_one_result_copy_for_all_accounts(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            uploaded_excel = temp_path / 'input.xlsx'
            result_dir = temp_path / 'results'
            pd.DataFrame({
                'name': ['候选人A', '候选人B'],
                'is_chat': [None, None],
                'keywords': ['关键词A', '关键词B'],
                'apply_position': ['岗位4416', '岗位4416'],
            }).to_excel(uploaded_excel, index=False)

            data = SimpleNamespace(
                position_id='',
                limit_count=50,
                conversation_mode='upload',
                excel_file_name_list=[uploaded_excel.name],
                inject_session=SimpleNamespace(
                    cookies_file_name_list=['account-a.json', 'account-b.json'],
                ),
            )

            with patch('backend.service.SearchConditionService.h5_ai_update_status'), \
                    patch('backend.service.SearchConditionService.resolve_excel_path', return_value=uploaded_excel), \
                    patch('backend.service.SearchConditionService.resolve_cookie_path', side_effect=lambda name: temp_path / name), \
                    patch('backend.service.SearchConditionService.get_excel_result_dir', return_value=result_dir), \
                    patch('backend.service.SearchConditionService.Manger') as manger_class:
                manger = manger_class.return_value
                manger.first_conversation_count = 0
                manger.pay_flag = False
                manger.first_conversation_by_excel.side_effect = [(1, True), (2, True)]

                SearchConditionService().first_conversation(data)

            result_files = list(result_dir.glob('*.xlsx'))
            self.assertEqual(len(result_files), 1)
            self.assertNotEqual(result_files[0], uploaded_excel)
            self.assertEqual(pd.read_excel(uploaded_excel)['is_chat'].notna().sum(), 0)

            processed_paths = [Path(call.args[1]) for call in manger.first_conversation_by_excel.call_args_list]
            self.assertEqual(processed_paths, [result_files[0], result_files[0]])


if __name__ == '__main__':
    unittest.main()
