"""离线验证高潜学校/专业字段及原上传、查重行为保持不变。"""
import copy
import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from backend.core.config.anyJobConfig import API_ADD_SCREENING_RESUME
from backend.core.config.chatBotApiConfig import ENUM_MODEL_ID
from backend.core.entity.candidate import Candidate
from backend.core.utils.resume.highest_education import get_highest_education_fields
from backend.manger import Manger
from scripts.test_screening_payload_age_salary import _raw_resume


class EducationSelectionTests(unittest.TestCase):
    def test_highest_degree_not_first_and_input_unchanged(self):
        records = [
            {'schoolName': '本科学校', 'major': '本科专业', 'educationLabel': '本科'},
            {'schoolName': '硕士学校', 'major': '硕士专业', 'educationLabel': '硕士'},
        ]
        original = copy.deepcopy(records)
        self.assertEqual(get_highest_education_fields(records), {'school': '硕士学校', 'major': '硕士专业'})
        self.assertEqual(records, original)

    def test_zhilian_codes_are_not_numerically_ranked(self):
        for code in (1, '1'):
            with self.subTest(code=code):
                records = [
                    {'schoolName': '中专学校', 'education': 12},
                    {'schoolName': 'MBA学校', 'education': '10'},
                    {'schoolName': '博士学校', 'major': '博士专业', 'education': code},
                    {'schoolName': '本科学校', 'education': 4},
                ]
                self.assertEqual(get_highest_education_fields(records), {'school': '博士学校', 'major': '博士专业'})

    def test_chinese_english_degree_order_and_mba(self):
        records = [
            {'schoolName': 'Bachelor School', 'educationLabel': 'Bachelor of Science'},
            {'schoolName': 'MBA School', 'educationLabel': 'MBA/EMBA'},
            {'schoolName': 'PhD School', 'educationLabel': 'Ph.D.'},
        ]
        self.assertEqual(get_highest_education_fields(records[:2])['school'], 'MBA School')
        self.assertEqual(get_highest_education_fields(records)['school'], 'PhD School')
        records.append({'schoolName': '博士后学校', 'educationLabel': '博士后'})
        self.assertEqual(get_highest_education_fields(records)['school'], '博士后学校')

    def test_equal_degrees_keep_first_without_mixing_major(self):
        records = [
            {'schoolName': '第一学校', 'major': '', 'education': 3},
            {'schoolName': '第二学校', 'major': '第二专业', 'educationLabel': 'MBA'},
            {'schoolName': '本科学校', 'major': '本科专业', 'educationLabel': '本科'},
        ]
        self.assertEqual(get_highest_education_fields(records), {'school': '第一学校', 'major': ''})

    def test_missing_school_does_not_borrow_from_lower_degree(self):
        records = [
            {'schoolName': '本科学校', 'major': '本科专业', 'education': 4},
            {'schoolName': None, 'major': '博士专业', 'education': 1},
        ]
        self.assertEqual(get_highest_education_fields(records), {'school': '', 'major': '博士专业'})

    def test_unknown_degrees_do_not_guess_among_multiple_records(self):
        records = [
            {'schoolName': '学校甲', 'education': 999},
            {'schoolName': '学校乙', 'major': '专业乙', 'educationLabel': '未知'},
        ]
        self.assertEqual(get_highest_education_fields(records), {'school': '', 'major': ''})
        self.assertEqual(get_highest_education_fields(records[:1]), {'school': '学校甲', 'major': ''})

    def test_invalid_values_and_malformed_records_are_safe(self):
        for records in (None, '', {}, [], [None, 'invalid', [], {}], [
            {'schoolName': ' 暂无 ', 'major': '--'},
            {'schoolName': {'name': '错误类型'}, 'major': ['错误类型']},
        ]):
            with self.subTest(records=records):
                self.assertEqual(get_highest_education_fields(records), {'school': '', 'major': ''})

    def test_structured_alias_and_whitespace(self):
        records = [{'schoolName': '  测试\n大学  ', 'major': '--', 'majorName': ' Computer   Science ', 'educationLevel': '硕士'}]
        self.assertEqual(get_highest_education_fields(records), {'school': '测试 大学', 'major': 'Computer Science'})


class ScreeningUploadTests(unittest.TestCase):
    def setUp(self):
        self.raw = _raw_resume()
        self.raw['resume']['educationExperiences'].append(
            {'schoolName': '浙江大学', 'major': '人工智能', 'education': 3, 'educationLabel': '硕士'}
        )
        self.clean_resume = '**期待薪资**：99K-120K/月\n**居住地**：上海\n**优势标签**：后端\n**推荐语**：匹配'

        def fake_send(_msg, chatbot_id):
            if chatbot_id == ENUM_MODEL_ID.GET_CLEAN_SALARY.value:
                return '30'
            if chatbot_id == ENUM_MODEL_ID.GET_CLEAN_RESUME:
                return self.clean_resume
            raise AssertionError(f'Unexpected additional model call: {chatbot_id}')

        self.send = self.enterContext(patch('backend.core.entity.candidate.chatBot.send', side_effect=fake_send))
        self.post = self.enterContext(patch('backend.core.api.anyJobApi.requests.post', return_value=Mock(status_code=200, json=lambda: {})))
        self.enterContext(patch('backend.core.entity.candidate.h5_post'))
        self.candidate = Candidate.from_raw_resume(self.raw, '123', '834')
        self.candidate.check_is_clients = Mock()
        self.candidate.check_screening_is_duplicate_with_smart_keywords = Mock()
        self.candidate.set_fact_check = Mock()
        self.candidate.fact_check_comment_label = '匹配'
        self.candidate.fact_check_comment = '匹配，a，b，原因'
        self.candidate.set_simple_resume = Mock()
        self.candidate.simple_resume = '简历摘要'

    def test_actual_api_payload_only_adds_school_and_major(self):
        identity = (self.candidate.schoolName, self.candidate.major,
                    self.candidate.smart_keywords, list(self.candidate.smart_keywords_candidates))
        self.candidate.upload_screening_resume_to_anyJob()
        self.post.assert_called_once()
        url, payload = self.post.call_args.args
        self.assertEqual(url, API_ADD_SCREENING_RESUME)
        self.assertEqual(payload.pop('school'), '浙江大学')
        self.assertEqual(payload.pop('major'), '人工智能')
        self.assertEqual(payload, {
            'position_id': '123', 'incharge_id': '834', 'status': '待联系', 'coins_cost': 2,
            'name': '张三', 'liepin_keywords': '测试科技 研发工程师 复旦大学 计算机',
            'smart_keywords': '张_测试科技_研发工程师_复旦大学_计算机',
            'current_company': '测试科技', 'current_position': '研发工程师',
            'resume_content': self.clean_resume, 'ai_summary': '简历摘要',
            'comment': '匹配，原因', 'source': 'zhilian',
            'activity_time': datetime.fromtimestamp(self.raw['user']['lastActiveTime'] / 1000).strftime('%Y-%m-%d'),
            'salary': '30', 'age': 39, 'location': '上海', 'tags': '后端',
        })
        self.assertEqual(identity, (self.candidate.schoolName, self.candidate.major,
                                   self.candidate.smart_keywords, self.candidate.smart_keywords_candidates))
        self.assertEqual(json.loads(self.candidate.rawResume), self.raw)
        self.assertEqual(self.send.call_count, 2)  # 仍只有原来的薪资及简历清洗调用。

    def test_empty_education_still_uploads_both_empty_fields(self):
        self.raw['resume']['educationExperiences'] = []
        self.candidate.rawResume = json.dumps(self.raw)
        self.candidate.upload_screening_resume_to_anyJob()
        payload = self.post.call_args.args[1]
        self.assertEqual((payload['school'], payload['major']), ('', ''))

    def test_duplicate_and_mismatch_still_skip_upload(self):
        with patch('backend.core.entity.candidate.get_highest_education_fields') as extract:
            self.candidate.is_duplicate_pass = True
            self.candidate.upload_screening_resume_to_anyJob()
            self.candidate.set_fact_check.assert_not_called()
            self.candidate.is_duplicate_pass = False
            self.candidate.fact_check_comment_label = '不匹配'
            self.candidate.upload_screening_resume_to_anyJob()
            self.post.assert_not_called()
            extract.assert_not_called()

    def test_existing_screening_sync_does_not_overwrite_education(self):
        self.candidate.is_duplicate_with_current_position = True
        self.candidate.resume_id = '200'
        with (
            patch('backend.core.entity.candidate.get_highest_education_fields', side_effect=AssertionError('education must not run in update flow')),
            patch('backend.core.entity.candidate.update_screening_resume') as update,
        ):
            self.candidate.sync_high_potential_by_smart_keywords('候选人说：您好', rule_tag='有意向沟通')
        update.assert_called_once_with('200', chat_history='候选人说：您好', chat_tags='有意向沟通')

    def test_manager_screening_entry_reaches_upload_with_string_save_path(self):
        manager = Manger()
        manager.set_cookies = Mock()
        manager.get_page_count = Mock(return_value=1)
        manager.set_candidate_list = Mock()
        manager.set_resume_list = Mock(side_effect=lambda: setattr(manager, 'current_resume_list', [self.raw]))
        self.candidate.to_excel_row = Mock()
        with (
            patch('backend.manger.time.sleep'),
            patch('backend.manger.Candidate.from_raw_resume', return_value=self.candidate),
            patch('backend.manger.h5_ai_add_count') as count,
            patch('backend.manger.path_util.get_save_path', return_value='/offline-test/save'),
        ):
            manager.upload_screening('unused-cookie', {}, '834', '123', '测试岗位')
        payload = self.post.call_args.args[1]
        self.assertEqual((payload['school'], payload['major']), ('浙江大学', '人工智能'))
        count.assert_called_once_with('123', count_resume_reviews=1)
        export_path = Path(self.candidate.to_excel_row.call_args.args[0])
        self.assertEqual(export_path.parent, Path('/offline-test/save/candidate'))
        self.assertEqual(export_path.suffix, '.xlsx')

    def test_first_conversation_and_excel_also_upload_education(self):
        source_candidate = {
            'resumeNumber': 'RN-1', 'resumeLanguage': 1, 'resumeVersion': 1,
            'resumeK': 'fake-k', 'resumeT': 'fake-t', 'purposes': [{'purposeId': 'purpose-1'}],
        }
        for mode in ('strategy', 'excel'):
            with self.subTest(mode=mode):
                self.post.reset_mock()
                manager = Manger()
                manager.set_cookies = Mock()

                def set_job(*_args, **_kwargs):
                    manager.current_position = {'position_id': '123'}
                    manager.current_job_number = 'JOB-1'
                    return True

                manager.check_and_set_job = Mock(side_effect=set_job)
                manager.get_page_count = Mock(return_value=1)
                manager.set_candidate_list = Mock(side_effect=lambda *_args, **_kwargs: setattr(
                    manager, 'current_candidate_list', [source_candidate]
                ))
                with (
                    patch('backend.manger.time.sleep'),
                    patch('backend.manger.Candidate.from_raw_resume', return_value=self.candidate),
                    patch('backend.manger.create_greet', return_value=Mock(text='{"code":200}')),
                    patch('backend.manger.get_resume', return_value=Mock(text=json.dumps({'data': self.raw}))),
                    patch('backend.manger.get_candidate_list', return_value=Mock(text=json.dumps({'data': {'total': 1, 'list': [source_candidate]}}))),
                    patch('backend.manger.get_incharge_id_by_position_id', return_value=Mock(content=b'{"results":[{"incharge_id":"834"}]}')),
                    patch('backend.manger.h5_ai_add_count') as count,
                ):
                    if mode == 'strategy':
                        manager.first_conversation('unused-cookie', {}, '123', 50)
                    else:
                        result = manager.first_conversation_with_excel('unused-cookie', Mock(to_dict=lambda: {}), '123', 50)
                        self.assertEqual(result, 0)
                self.post.assert_called_once()
                payload = self.post.call_args.args[1]
                self.assertEqual((payload['school'], payload['major']), ('浙江大学', '人工智能'))
                self.assertEqual(manager.first_conversation_count, 1)
                count.assert_any_call('123', count_conversations=1)
                count.assert_any_call('123', count_resume_reviews=1)


if __name__ == '__main__':
    unittest.main()
