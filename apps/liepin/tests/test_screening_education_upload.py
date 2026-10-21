import copy
import json
import unittest
from datetime import datetime
from unittest.mock import call, patch

import requests

from backend.config.anyJobConfig import API_ADD_SCREENING_RESUME, API_H5_POST
from backend.config.chatBotApiConfig import ENUM_MODEL_ID
from backend.entity.candidate import Candidate


class ScreeningEducationUploadTest(unittest.TestCase):
    @staticmethod
    def candidate():
        return Candidate.from_raw_resume({
            'showName': '张先生',
            'eduExpFormList': [
                {'redSchool': '本科大学', 'redSpecial': '计算机', 'redDegreeName': '本科'},
                {'redSchool': '硕士大学', 'redSpecial': '软件工程', 'redDegreeName': '硕士'},
            ],
        }, [{'rwCompname': '测试公司', 'rwTitle': '工程师'}], 'test-position', 'test-user')

    @staticmethod
    def response(payload):
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(payload).encode('utf-8')
        return response

    def test_payload_only_adds_two_fields_without_changing_candidate(self):
        candidate = self.candidate()
        candidate.simple_resume = '摘要'
        candidate.age = 30
        candidate.salary = '30-40k'
        candidate.recentActiveTime = datetime(2026, 8, 28)
        clean_resume = '清洗简历'
        before = copy.deepcopy(vars(candidate))
        with patch.object(candidate, 'set_simple_resume'), \
                patch('backend.entity.candidate.RegexUtils.extract_location', return_value=['上海']), \
                patch('backend.entity.candidate.RegexUtils.extract_tags', return_value=['研发']):
            payload = candidate._build_screening_resume_payload(clean_resume, '匹配')

        self.assertEqual(payload.pop('school'), '硕士大学')
        self.assertEqual(payload.pop('major'), '软件工程')
        self.assertEqual(payload, {
            'name': '张先生',
            'liepin_keywords': '测试公司 工程师 本科大学 计算机',
            'smart_keywords': '张_测试公司_工程师_本科大学_计算机',
            'current_company': '测试公司',
            'current_position': '工程师',
            'resume_content': clean_resume,
            'ai_summary': '摘要',
            'comment': '匹配',
            'source': candidate._get_screening_source(),
            'activity_time': '2026-08-28',
            'age': 30,
            'salary': '30-40k',
            'location': '上海',
            'tags': '研发',
        })
        self.assertEqual(vars(candidate), before)

    def test_invalid_raw_resume_adds_blank_fields_not_legacy_school_or_ai_text(self):
        candidate = self.candidate()
        candidate.rawResume = '{invalid'
        with patch.object(candidate, 'set_simple_resume'):
            payload = candidate._build_screening_resume_payload('学校：模型学校\n专业：模型专业', '')
        self.assertEqual((payload['school'], payload['major']), ('', ''))
        self.assertEqual(candidate.schoolName, '本科大学')
        self.assertEqual(candidate.major, '计算机')

    def test_both_screening_entry_modes_send_education_through_real_api_adapter(self):
        # 策略首次会话使用 True；Excel 首次会话使用默认 False。
        for already_checked in (False, True):
            with self.subTest(fact_check_already_done=already_checked):
                candidate = self.candidate()
                candidate.diagnostic_trace_id = 'education-test'
                candidate.fact_check_comment_label = '匹配'
                with patch.object(candidate, 'check_is_clients'), \
                        patch.object(candidate, 'check_screening_is_duplicate_with_resume_code'), \
                        patch.object(candidate, 'set_fact_check') as fact_check, \
                        patch.object(candidate, '_build_screening_comment', return_value='匹配'), \
                        patch('backend.entity.candidate.chatBot.send', side_effect=['清洗简历', '摘要']) as bot, \
                        patch('backend.api.anyJobApi.requests.post', return_value=self.response({'code': 0})) as post:
                    result = candidate.upload_screening_resume_to_anyJob(already_checked)

                self.assertEqual(result, 'uploaded')
                self.assertEqual(post.call_count, 2)  # 原有 H5 发帖一次 + 高潜上传一次
                self.assertEqual(post.call_args_list[0].args[0], API_H5_POST)
                self.assertEqual(post.call_args_list[1].args[0], API_ADD_SCREENING_RESUME)
                payload = post.call_args_list[1].args[1]
                self.assertEqual((payload['school'], payload['major']), ('硕士大学', '软件工程'))
                self.assertEqual(payload['coins_cost'], 2)
                self.assertEqual(payload['status'], '待联系')
                self.assertEqual(payload['position_id'], 'test-position')
                self.assertEqual(payload['incharge_id'], 'test-user')
                self.assertEqual(payload['smart_keywords'], '张_测试公司_工程师_本科大学_计算机')
                self.assertNotIn('trace_id', payload)
                self.assertEqual(bot.call_args_list, [
                    call(candidate.rawResume, ENUM_MODEL_ID.GET_CLEAN_RESUME, trace_id='education-test'),
                    call(candidate.rawResume, ENUM_MODEL_ID.GET_SIMPLE_RESUME),
                ])
                self.assertEqual(fact_check.call_count, 0 if already_checked else 1)

    def test_skipped_candidates_do_not_extract_or_upload_education(self):
        for duplicate, label, expected in (
            (True, '匹配', 'skipped_duplicate'), (False, '不匹配', 'skipped_mismatch'),
        ):
            with self.subTest(result=expected):
                candidate = self.candidate()
                candidate.is_duplicate_with_current_position = duplicate
                candidate.fact_check_comment_label = label
                with patch.object(candidate, 'check_is_clients'), \
                        patch.object(candidate, 'check_screening_is_duplicate_with_resume_code'), \
                        patch('backend.entity.candidate.extract_highest_education') as extract, \
                        patch('backend.entity.candidate.chatBot.send') as bot, \
                        patch('backend.api.anyJobApi.requests.post') as post:
                    result = candidate.upload_screening_resume_to_anyJob(True)
                self.assertEqual(result, expected)
                extract.assert_not_called()
                bot.assert_not_called()
                post.assert_not_called()

    def test_existing_screening_chat_sync_does_not_overwrite_education(self):
        candidate = self.candidate()
        candidate.resume_id = 123
        candidate.is_duplicate_with_current_position = True
        with patch.object(candidate, 'check_screening_is_duplicate_with_resume_code'), \
                patch('backend.entity.candidate.extract_highest_education') as extract, \
                patch('backend.entity.candidate.update_screening_resume',
                      return_value=self.response({'code': 0, 'data': {}})) as update:
            result = candidate.sync_high_potential_by_smart_keywords(
                '测试聊天', rule_tag='有意向沟通', activity_time=datetime(2026, 8, 28, 12),
            )
        self.assertTrue(result)
        extract.assert_not_called()
        update.assert_called_once_with(
            123, chat_history='测试聊天', chat_tags='有意向沟通', activity_time='2026-08-28 12:00:00',
        )

    def test_formal_resume_upload_does_not_use_screening_education_fields(self):
        candidate = self.candidate()
        candidate.fact_check_comment_label = '匹配'
        candidate.fact_check_comment = '匹配，测试原因'
        with patch.object(candidate, 'set_incharge_id_by_recommend_id'), \
                patch.object(candidate, '_check_local_upload_ledger'), \
                patch.object(candidate, 'check_is_duplicate_with_smart_keywords'), \
                patch.object(candidate, 'check_is_duplicate_with_phone_vx'), \
                patch.object(candidate, '_capture_current_position_screening_id', return_value=None), \
                patch.object(candidate, 'set_fact_check'), \
                patch.object(candidate, 'get_md_text', return_value='正式简历'), \
                patch.object(candidate, '_record_local_upload_ledger'), \
                patch('backend.entity.candidate.extract_highest_education') as extract, \
                patch('backend.entity.candidate.chatBot.send', return_value='109'), \
                patch('backend.entity.candidate.add_resume',
                      return_value=self.response({'code': 0, 'data': {'resume_id': 456}})) as add, \
                patch('backend.entity.candidate.update_resume', return_value=self.response({'code': 0})), \
                patch('backend.entity.candidate.h5_post'):
            result = candidate.upload_resume_to_anyJob('13800000000', 'test-wechat', '聊天', 'test-user', '测试账号')
        self.assertTrue(result)
        extract.assert_not_called()
        add.assert_called_once()
        payload = add.call_args.kwargs
        self.assertNotIn('school', payload)
        self.assertNotIn('major', payload)
        self.assertEqual(payload['smart_keywords'], '张_测试公司_工程师_本科大学_计算机')
        self.assertEqual(payload['resume'], '正式简历')
        self.assertEqual(payload['phone'], '13800000000')
        self.assertEqual(payload['weixin'], 'test-wechat')


if __name__ == '__main__':
    unittest.main()
