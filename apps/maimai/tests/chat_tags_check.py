import json
import unittest
from contextlib import ExitStack
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from src.utils.highest_education import (
    extract_highest_education, extract_screening_education, log_screening_education,
)

from src.exceptions import HTTPRetryException
from src.manager import (
    Manager,
    _chat_tag_without_candidate_reply,
    _redact_contact_text,
    _resume_response_diagnostic,
)
from src.service.user_service import (
    UserService,
    _build_profile_resume,
    _parse_resume_page,
    _resume_card_urls,
)
from tools.diagnose_maimai_network import (
    is_maimai_url,
    safe_text,
    sanitize_url,
    selenium_cookie,
    summarize_body,
)


class ChatTagWithoutCandidateReplyTest(unittest.TestCase):
    def test_no_candidate_reply_defaults_to_unread(self):
        chat_history = (
            '[06月24日 10:31]\n'
            'AI招聘官: 您好，请问最近是否在看新机会呢？\n'
        )

        self.assertEqual(_chat_tag_without_candidate_reply(chat_history), '未读消息')

    def test_read_receipt_without_candidate_reply_is_read_no_reply(self):
        dialogs = [
            {'type': 0, 'is_me': True, 'text': '您好，请问最近是否在看新机会呢？'},
            {'type': 99, 'is_me': False, 'text': '对方已阅读您的消息'},
        ]

        self.assertEqual(
            _chat_tag_without_candidate_reply(dialogs=dialogs),
            '已读不回',
        )

    def test_candidate_reply_keeps_ai_tag_generation_path(self):
        chat_history = (
            '[06月24日 10:31]\n'
            'AI招聘官: 您好，请问最近是否在看新机会呢？\n'
            '[06月24日 10:38]\n'
            '候选人: 可以了解一下。\n'
        )

        self.assertIsNone(_chat_tag_without_candidate_reply(chat_history))


class SavedResumeStatusTest(unittest.TestCase):
    def test_match_levels_use_supported_pending_review_status(self):
        for comment in ('一般匹配', '匹配', '非常匹配'):
            with self.subTest(comment=comment):
                self.assertEqual(
                    Manager._classify_saved_resume_status(comment),
                    '初审待定',
                )

    def test_non_match_and_uncertain_remain_to_be_screened(self):
        for comment in ('不匹配', '不确定'):
            with self.subTest(comment=comment):
                self.assertEqual(
                    Manager._classify_saved_resume_status(comment),
                    '待筛选',
                )


class SavedResumeRetrievalTest(unittest.TestCase):
    def test_retry_forwards_dialog_context_and_preserves_resume_metadata(self):
        manager = Manager()
        user_service = MagicMock()
        dialogs = [{'type': 123, 'is_me': False}]
        candidate = {'id': 123, 'name': '候选人'}
        resume_result = {
            'data': {'work_exps': [{'company': '测试公司'}]},
            'resume_source': 'resume_card_page',
        }
        user_service.get_resume.return_value = resume_result

        with patch('src.manager.random_sleep'):
            result = manager._get_resume_with_retry(
                user_service,
                123,
                dialogs=dialogs,
                candidate=candidate,
                retries=1,
            )

        self.assertIs(result, resume_result)
        user_service.get_resume.assert_called_once_with(
            123, dialogs=dialogs, candidate=candidate)

    def test_save_unwraps_complete_resume_before_upload(self):
        manager = Manager()
        user_service = MagicMock()
        user_service.user = SimpleNamespace(
            id=1, name='招聘账号', job_dict={'8561': object()})
        dialogs = [{'type': 0, 'is_me': False, 'text': '可以了解'}]
        msg = {'id': 456, 'u2': {'id': 123, 'name': '候选人'}}
        resume = {'work_exps': [{'company': '测试公司'}]}
        resume_result = {
            'data': resume,
            'resume_source': 'resume_card_page',
        }
        position = SimpleNamespace(pid='8561', incharge_id=2, requirement='岗位要求')
        user_service.get_dialog.return_value = dialogs
        user_service.get_mobile.return_value = '13800138000'
        manager._resolve_pid_for_save_msg = MagicMock(return_value='8561')
        manager.get_ah_position = MagicMock(return_value=position)
        manager._get_resume_with_retry = MagicMock(return_value=resume_result)
        manager._format_chat_history = MagicMock(return_value='候选人: 可以了解')
        manager._save_resume_to_intent_library = MagicMock(return_value='uploaded_intent')
        manager._read_msg_safe = MagicMock()

        result = manager._process_save_resume_msg(
            user_service, msg, 'all', {'8561'})

        self.assertEqual(result, 'uploaded_intent')
        manager._get_resume_with_retry.assert_called_once_with(
            user_service, 123, dialogs=dialogs, candidate=msg['u2'])
        manager._save_resume_to_intent_library.assert_called_once_with(
            user_service,
            msg,
            position,
            resume,
            '13800138000',
            None,
            '候选人: 可以了解',
        )

    def test_save_blocks_limited_profile_before_ai_and_upload(self):
        manager = Manager()
        user_service = MagicMock()
        user_service.user = SimpleNamespace(
            id=1, name='招聘账号', job_dict={'8561': object()})
        dialogs = [{'type': 0, 'is_me': False, 'text': '可以了解'}]
        msg = {'id': 456, 'u2': {'id': 123, 'name': '候选人'}}
        position = SimpleNamespace(pid='8561', incharge_id=2, requirement='岗位要求')
        user_service.get_dialog.return_value = dialogs
        manager._resolve_pid_for_save_msg = MagicMock(return_value='8561')
        manager.get_ah_position = MagicMock(return_value=position)
        manager._get_resume_with_retry = MagicMock(return_value={
            'data': {'company': '公开资料公司'},
            'resume_source': 'contact_profile_fallback',
            'resume_limited': True,
        })
        manager._save_resume_to_intent_library = MagicMock()
        manager._read_msg_safe = MagicMock()

        result = manager._process_save_resume_msg(
            user_service, msg, 'all', {'8561'})

        self.assertEqual(result, 'skipped')
        manager._get_resume_with_retry.assert_called_once_with(
            user_service, 123, dialogs=dialogs, candidate=msg['u2'])
        manager._save_resume_to_intent_library.assert_not_called()
        manager._read_msg_safe.assert_not_called()


class SecondContactResumeDiagnosticTest(unittest.TestCase):
    def test_resume_card_page_parser_returns_data_without_tokens(self):
        payload = {
            'data': {
                'result': 'ok',
                'card': {
                    'realname': '候选人',
                    'trackable_token': 'card-secret',
                },
                'work_exps': [{'company': '测试公司'}],
                'share_url': 'https://maimai.cn/profile?share_token=url-secret&fr=resume',
            },
            'auth_info': {
                '_csrf_token': 'csrf-secret',
            },
        }
        encoded_payload = json.dumps(json.dumps(payload, ensure_ascii=False))
        html = f'<script>share_data = JSON.parse({encoded_payload});</script>'

        result = _parse_resume_page(html)
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertEqual(result['result'], 'ok')
        self.assertEqual(result['resume_source'], 'resume_card_page')
        self.assertEqual(result['data']['card']['realname'], '候选人')
        self.assertNotIn('trackable_token', serialized)
        self.assertNotIn('card-secret', serialized)
        self.assertNotIn('csrf-secret', serialized)
        self.assertNotIn('share_token', serialized)
        self.assertNotIn('url-secret', serialized)
        self.assertIn('fr=resume', result['data']['share_url'])

    def test_resume_card_urls_accept_only_candidate_maimai_resume_pages(self):
        dialogs = [
            {
                'type': 123,
                'is_me': False,
                'common_card': {
                    'global_click_web_url': (
                        'https://maimai.cn/profile/resume_detail'
                        '?target_uid=123&trackable_token=secret'
                    ),
                },
            },
            {
                'type': 123,
                'is_me': True,
                'common_card': {
                    'global_click_web_url': 'https://maimai.cn/profile/resume_detail?mine=1',
                },
            },
            {
                'type': 123,
                'is_me': False,
                'common_card': {
                    'global_click_web_url': 'https://example.com/profile/resume_detail',
                },
            },
        ]

        urls = _resume_card_urls(dialogs)

        self.assertEqual(len(urls), 1)
        self.assertIn('target_uid=123', urls[0])

    def test_user_service_prefers_resume_card_page_over_legacy_api(self):
        payload = {
            'data': {
                'result': 'ok',
                'card': {'realname': '候选人'},
            },
        }
        encoded_payload = json.dumps(json.dumps(payload, ensure_ascii=False))
        page_response = SimpleNamespace(
            text=f'<script>share_data = JSON.parse({encoded_payload});</script>',
        )
        service = UserService.__new__(UserService)
        service.proxy = MagicMock()
        service.proxy.get_resume_page.return_value = page_response
        dialogs = [{
            'type': 123,
            'is_me': False,
            'common_card': {
                'global_click_web_url': 'https://maimai.cn/profile/resume_detail?target_uid=123',
            },
        }]

        result, response = service.get_resume(123, dialogs=dialogs, with_response=True)

        self.assertEqual(result['data']['card']['realname'], '候选人')
        self.assertIs(response, page_response)
        service.proxy.get_resume.assert_not_called()

    def test_user_service_falls_back_to_legacy_api_when_card_page_is_invalid(self):
        page_response = SimpleNamespace(text='<html>缺少 share_data</html>')
        legacy_response = SimpleNamespace(text='{"result":"ok","data":{"name":"候选人"}}')
        service = UserService.__new__(UserService)
        service.proxy = MagicMock()
        service.proxy.get_resume_page.return_value = page_response
        service.proxy.get_contact.return_value = SimpleNamespace(
            text='{"data":{"card":{"trackable_token":"legacy-token"}}}')
        service.proxy.get_resume.return_value = legacy_response
        dialogs = [{
            'type': 123,
            'is_me': False,
            'common_card': {
                'global_click_web_url': 'https://maimai.cn/profile/resume_detail?target_uid=123',
            },
        }]

        result, response = service.get_resume(123, dialogs=dialogs, with_response=True)

        self.assertEqual(result['data']['name'], '候选人')
        self.assertIs(response, legacy_response)
        service.proxy.get_resume.assert_called_once_with(123, 'legacy-token')

    def test_profile_resume_combines_contact_card_and_candidate_without_tokens(self):
        result = _build_profile_resume(
            {
                'data': {
                    'card': {
                        'id': 123,
                        'realname': '候选人',
                        'company': '当前公司',
                        'trackable_token': 'contact-secret',
                    },
                },
            },
            {
                'id': 123,
                'name': '消息昵称',
                'position': '运营主管',
                'trackable_token': 'message-secret',
            },
        )
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertEqual(result['result'], 'ok')
        self.assertTrue(result['resume_limited'])
        self.assertEqual(result['resume_source'], 'contact_profile_fallback')
        self.assertEqual(result['data']['card']['realname'], '候选人')
        self.assertEqual(result['data']['card']['position'], '运营主管')
        self.assertNotIn('trackable_token', serialized)
        self.assertNotIn('contact-secret', serialized)
        self.assertNotIn('message-secret', serialized)

    def test_user_service_uses_profile_when_legacy_resume_is_forbidden(self):
        contact_response = SimpleNamespace(
            text=json.dumps({
                'data': {
                    'card': {
                        'id': 123,
                        'company': '当前公司',
                        'trackable_token': 'legacy-token',
                    },
                },
            }),
        )
        forbidden_response = SimpleNamespace(
            text=json.dumps({
                'error_code': 10003,
                'error': 'No right to access.',
                'detail': 'not permitted',
            }),
        )
        service = UserService.__new__(UserService)
        service.proxy = MagicMock()
        service.proxy.get_contact.return_value = contact_response
        service.proxy.get_resume.return_value = forbidden_response

        result, response = service.get_resume(
            123,
            candidate={'id': 123, 'name': '候选人'},
            with_response=True,
        )

        self.assertEqual(result['data']['card']['company'], '当前公司')
        self.assertEqual(result['data']['card']['name'], '候选人')
        self.assertTrue(result['resume_limited'])
        self.assertIs(response, contact_response)
        service.proxy.get_resume.assert_called_once_with(123, 'legacy-token')

    def test_user_service_uses_message_profile_when_contact_request_fails(self):
        service = UserService.__new__(UserService)
        service.proxy = MagicMock()
        service.proxy.get_contact.side_effect = HTTPRetryException(
            SimpleNamespace(
                status_code=404,
                reason='Not Found',
                text='not found',
            ),
            3,
        )

        result = service.get_resume(
            123,
            candidate={
                'id': 123,
                'name': '候选人',
                'company': '消息公司',
                'position': '产品经理',
                'trackable_token': 'message-secret',
            },
        )

        self.assertEqual(result['data']['card']['company'], '消息公司')
        self.assertEqual(result['data']['card']['position'], '产品经理')
        self.assertTrue(result['resume_limited'])
        self.assertNotIn('trackable_token', json.dumps(result, ensure_ascii=False))
        service.proxy.get_resume.assert_not_called()

    def test_resume_diagnostic_excludes_body_and_redacts_sensitive_error_text(self):
        response = SimpleNamespace(
            status_code=200,
            headers={'content-type': 'application/json'},
            text='完整响应中包含简历正文、手机号13800138000和秘密令牌',
        )
        payload = {
            'result': 'fail',
            'error_code': 10003,
            'detail': 'not permitted',
            'message': '手机号：13800138000，trackable_token=secret-token',
            'data': {'resume': '不应写入日志的简历正文'},
        }

        diagnostic = _resume_response_diagnostic(payload, response)
        serialized = json.dumps(diagnostic, ensure_ascii=False)

        self.assertEqual(diagnostic['http_status'], 200)
        self.assertEqual(diagnostic['body_length'], len(response.text))
        self.assertNotIn('不应写入日志的简历正文', serialized)
        self.assertNotIn('13800138000', serialized)
        self.assertNotIn('secret-token', serialized)
        self.assertIn('[REDACTED]', serialized)
        self.assertEqual(diagnostic['error_fields']['error_code'], '10003')
        self.assertEqual(diagnostic['error_fields']['detail'], 'not permitted')

    def test_second_contact_logs_missing_resume_data_and_skips_sending(self):
        class MemoryLogger:
            def __init__(self):
                self.lines = []

            def write_line(self, message, active=False):
                self.lines.append((message, active))

        manager = Manager()
        manager.logger = MemoryLogger()
        message = {
            'id': 9001,
            'latest_dialog_timestamp': 9999999999,
            'u2': {'id': 12345678, 'name': '候选人A'},
        }
        dialogs = [
            {
                'type': 124,
                'is_me': True,
                'text': '',
                'common_card': {'center': {'title': '测试岗位8561'}},
                'uptimestamp': 1,
            },
            {'type': 0, 'is_me': True, 'text': '首次招呼', 'uptimestamp': 2},
        ]
        resume_response = SimpleNamespace(
            status_code=200,
            headers={'content-type': 'application/json'},
            text='{"result":"fail","reason":"resume unavailable"}',
        )
        service = MagicMock()
        service.user = SimpleNamespace(
            id=1,
            name='测试账号',
            job_dict={'8561': SimpleNamespace()},
        )
        service.get_msgs.side_effect = [[message], []]
        service.get_mobile.return_value = None
        service.get_dialog.return_value = dialogs
        service.get_resume.return_value = (
            {'result': 'fail', 'reason': 'resume unavailable'},
            resume_response,
        )
        manager.user_services = {1: service}
        manager.get_ah_position = MagicMock(
            return_value=SimpleNamespace(pid='8561', incharge_id=834))

        with patch('src.manager.random_sleep'):
            result = manager.second_contact(user_ids=[1])

        log_text = '\n'.join(message for message, _ in manager.logger.lines)
        self.assertEqual(result, {'测试账号': 0})
        service.get_resume.assert_called_once_with(
            12345678,
            dialogs=dialogs,
            candidate=message['u2'],
            with_response=True,
        )
        service.add_dialog.assert_not_called()
        self.assertIn('二次激活简历接口缺少有效data', log_text)
        self.assertIn('"http_status": 200', log_text)
        self.assertIn('"top_level_keys": ["reason", "result"]', log_text)
        self.assertIn('"reason": "resume unavailable"', log_text)
        self.assertIn('uid_tail=5678', log_text)

    def test_second_contact_continues_with_limited_public_profile(self):
        class MemoryLogger:
            def __init__(self):
                self.lines = []

            def write_line(self, message, active=False):
                self.lines.append(message)

        manager = Manager()
        manager.logger = MemoryLogger()
        message = {
            'id': 9003,
            'latest_dialog_timestamp': 9999999999,
            'u2': {
                'id': 12345678,
                'name': '候选人A',
                'company': '测试公司',
                'position': '运营主管',
            },
        }
        dialogs = [
            {
                'type': 124,
                'is_me': True,
                'text': '',
                'common_card': {'center': {'title': '测试岗位8561'}},
                'uptimestamp': 1,
            },
            {'type': 0, 'is_me': True, 'text': '首次招呼', 'uptimestamp': 2},
        ]
        service = MagicMock()
        service.user = SimpleNamespace(
            id=1,
            name='测试账号',
            job_dict={'8561': SimpleNamespace()},
        )
        service.get_msgs.side_effect = [[message], []]
        service.get_mobile.return_value = None
        service.get_dialog.return_value = dialogs
        service.get_resume.return_value = ({
            'result': 'ok',
            'data': {
                'card': {
                    'id': 12345678,
                    'company': '测试公司',
                    'position': '运营主管',
                },
            },
            'resume_source': 'contact_profile_fallback',
            'resume_limited': True,
        }, None)
        manager.user_services = {1: service}
        position = SimpleNamespace(
            pid='8561',
            incharge_id=834,
            second_requirement='请生成二次激活消息。',
        )

        with patch('src.manager.random_sleep'), \
                patch.object(manager, 'get_ah_position', return_value=position), \
                patch(
                    'src.manager.ah_io.duplicate_screening',
                    return_value=SimpleNamespace(
                        text=json.dumps({'duplicate': 'no'}),
                    ),
                ), \
                patch('src.manager.ah_io.h5_ai_update_status'), \
                patch(
                    'src.manager.bot_io.send',
                    return_value=SimpleNamespace(
                        text=json.dumps({
                            'choices': [{
                                'message': {'content': '最近还在看新机会吗？'},
                            }],
                        }),
                    ),
                ):
            result = manager.second_contact(user_ids=[1])

        log_text = '\n'.join(manager.logger.lines)
        self.assertEqual(result, {'测试账号': 1})
        service.get_resume.assert_called_once_with(
            12345678,
            dialogs=dialogs,
            candidate=message['u2'],
            with_response=True,
        )
        service.add_dialog.assert_called_once_with(
            9003,
            '最近还在看新机会吗？',
        )
        self.assertNotIn('未获得完整简历', log_text)
        self.assertIn('成功二次激活', log_text)

    def test_second_contact_logs_http_metadata_when_resume_request_raises(self):
        class MemoryLogger:
            def __init__(self):
                self.lines = []

            def write_line(self, message, active=False):
                self.lines.append(message)

        class ResumeRequestError(RuntimeError):
            def __init__(self, response):
                super().__init__('request failed')
                self.resp = response

        manager = Manager()
        manager.logger = MemoryLogger()
        message = {
            'id': 9002,
            'latest_dialog_timestamp': 9999999999,
            'u2': {'id': 87654321, 'name': '候选人B'},
        }
        dialogs = [
            {
                'type': 124,
                'is_me': True,
                'text': '',
                'common_card': {'center': {'title': '测试岗位8561'}},
                'uptimestamp': 1,
            },
            {'type': 0, 'is_me': True, 'text': '首次招呼', 'uptimestamp': 2},
        ]
        response = SimpleNamespace(
            status_code=403,
            headers={'content-type': 'application/json'},
            text='响应正文不会被写入日志',
        )
        service = MagicMock()
        service.user = SimpleNamespace(
            id=1,
            name='测试账号',
            job_dict={'8561': SimpleNamespace()},
        )
        service.get_msgs.side_effect = [[message], []]
        service.get_mobile.return_value = None
        service.get_dialog.return_value = dialogs
        service.get_resume.side_effect = ResumeRequestError(response)
        manager.user_services = {1: service}
        manager.get_ah_position = MagicMock(
            return_value=SimpleNamespace(pid='8561', incharge_id=834))

        with patch('src.manager.random_sleep'):
            result = manager.second_contact(user_ids=[1])

        log_text = '\n'.join(manager.logger.lines)
        self.assertEqual(result, {'测试账号': 0})
        service.add_dialog.assert_not_called()
        self.assertIn('二次激活简历接口调用失败', log_text)
        self.assertIn('"http_status": 403', log_text)
        self.assertIn('"error_type": "ResumeRequestError"', log_text)
        self.assertNotIn(response.text, log_text)


class NetworkDiagnosticPrivacyTest(unittest.TestCase):
    def test_capture_scope_accepts_only_maimai_hosts(self):
        self.assertTrue(is_maimai_url('https://maimai.cn/api/ent/talent/basic'))
        self.assertTrue(is_maimai_url('https://api.maimai.cn/example'))
        self.assertFalse(is_maimai_url('https://maimai.cn.example.com/example'))
        self.assertFalse(is_maimai_url('https://example.com/maimai.cn/example'))

    def test_sanitize_url_keeps_only_uid_tail_and_query_names(self):
        result = sanitize_url(
            'https://maimai.cn/contact/comment_list/12345678'
            '?jsononly=1&trackable_token=secret-token'
        )

        serialized = json.dumps(result, ensure_ascii=False)
        self.assertIn('***5678', serialized)
        self.assertIn('trackable_token', result['query_parameter_names'])
        self.assertNotIn('12345678', serialized)
        self.assertNotIn('secret-token', serialized)

    def test_summarize_body_does_not_keep_resume_or_contact_values(self):
        body = json.dumps({
            'data': {'resume': '完整简历正文'},
            'error_code': 10003,
            'error': '手机号：13800138000，trackable_token=secret-token',
            'detail': 'not permitted',
        }, ensure_ascii=False)

        result = summarize_body(body)
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertTrue(result['has_data'])
        self.assertNotIn('完整简历正文', serialized)
        self.assertNotIn('13800138000', serialized)
        self.assertNotIn('secret-token', serialized)
        self.assertEqual(result['error_fields']['error_code'], '10003')
        self.assertEqual(result['error_fields']['detail'], 'not permitted')

    def test_safe_text_hides_complex_values(self):
        self.assertEqual(safe_text({'secret': 'value'}), '<dict>')
        self.assertEqual(safe_text('candidate_uid=12345678'), 'candidate_uid=***5678')

    def test_selenium_cookie_maps_supported_fields_without_mutating_value(self):
        result = selenium_cookie({
            'name': 'session',
            'value': 'secret',
            'domain': '.maimai.cn',
            'path': '/',
            'secure': True,
            'httpOnly': True,
            'sameSite': 'no_restriction',
        })

        self.assertEqual(result['value'], 'secret')
        self.assertEqual(result['sameSite'], 'None')
        self.assertTrue(result['secure'])


class AutoReplyDialogFilterTest(unittest.TestCase):
    def test_deleted_outreach_and_resume_cards_do_not_trigger_reply(self):
        dialogs = [
            {
                'type': 124,
                'is_me': 1,
                'text': '[消息删除]',
                'common_card': {'center': {'title': '软件工程师8561'}},
                'uptimestamp': 1783410077,
            },
            {
                'type': 123,
                'is_me': 1,
                'text': '[消息删除]',
                'common_card': {
                    'center': {'content': '我们正在招软件工程师8561人才，可以要一份你的简历吗？'}
                },
                'uptimestamp': 1783410077,
            },
            {
                'type': 116,
                'is_me': 0,
                'text': '您好，我有兴趣聊聊这个职位',
                'uptimestamp': 1783410156,
            },
            {
                'type': 123,
                'is_me': 0,
                'text': '对方向您发送简历      ',
                'common_card': {'center': {'title': '对方向您发送简历      '}},
                'uptimestamp': 1783410158,
            },
        ]

        _, speaker = Manager._get_last_reply_turn(dialogs)

        self.assertIsNone(speaker)
        self.assertFalse(Manager._has_recruiter_outreach(dialogs))
        self.assertTrue(all('[消息删除]' not in (Manager._dialog_to_chat_line(d) or '') for d in dialogs))
        self.assertNotIn('[消息删除]', Manager._format_chat_history(dialogs))

    def test_resume_update_hint_does_not_trigger_reply(self):
        dialogs = [
            {'type': 118, 'is_me': 0, 'text': '对方最近更新了简历，求职意向强烈，期待您的回复'},
        ]

        _, speaker = Manager._get_last_reply_turn(dialogs)

        self.assertIsNone(speaker)
        self.assertEqual(Manager._format_chat_history(dialogs), '')

    def test_real_candidate_text_reply_still_triggers_reply(self):
        dialogs = [
            {'type': 0, 'is_me': 1, 'text': '您好，请问最近是否在看新机会呢？'},
            {'type': 0, 'is_me': 0, 'text': '可以了解一下。'},
        ]

        _, speaker = Manager._get_last_reply_turn(dialogs)

        self.assertEqual(speaker, 'candidate')
        self.assertTrue(Manager._has_recruiter_outreach(dialogs))

    def test_deleted_job_card_does_not_make_later_me_text_helper_initiated(self):
        manager = Manager()
        dialogs = [
            {
                'type': 124,
                'is_me': 1,
                'text': '[消息删除]',
                'common_card': {'center': {'title': '软件工程师8561'}},
            },
            {'type': 0, 'is_me': 1, 'text': '收到'},
        ]

        self.assertFalse(manager._is_helper_initiated_conversation(123, '8561', dialogs))


class SaveResumeTimeRangeTest(unittest.TestCase):
    def test_descending_messages_skip_newer_and_stop_after_older_boundary(self):
        manager = Manager()
        in_range = {
            'id': 2,
            'u2': {'id': 102, 'name': '范围内候选人'},
            'latest_dialog_timestamp': datetime(2026, 8, 17, 12).timestamp(),
        }
        user_service = MagicMock()
        user_service.user = SimpleNamespace(
            id=1, name='测试账号', job_dict={'8561': object()})
        user_service.get_all_msgs.return_value = [
            {
                'id': 1,
                'u2': {'id': 101, 'name': '范围后候选人'},
                'latest_dialog_timestamp': datetime(2026, 8, 18, 9).timestamp(),
            },
            in_range,
            {
                'id': 3,
                'u2': {'id': 103, 'name': '范围前候选人'},
                'latest_dialog_timestamp': datetime(2026, 8, 14, 23).timestamp(),
            },
        ]
        user_service.get_msgs.return_value = []
        manager.user_services = {1: user_service}
        manager._process_save_resume_msg = MagicMock(return_value='uploaded_intent')

        with patch('src.manager.random_sleep'):
            result = manager.save_resume(
                reply_mode='all',
                start_time='2026-08-15 00:00:00',
                end_time='2026-08-17 23:59:59',
                user_ids=[1],
            )

        self.assertEqual(result, {'scanned': 1, 'succ_count': 1, 'skip_count': 0})
        manager._process_save_resume_msg.assert_called_once_with(
            user_service, in_range, 'all', {'8561'}, fixed_pid=None)


class ContactPrivacyTest(unittest.TestCase):
    @staticmethod
    def _json_response(payload):
        return SimpleNamespace(text=json.dumps(payload, ensure_ascii=False))

    def _queue_upload_data(self):
        candidate = {
            'uid': 123,
            'resume': {'name': '候选人', 'company': '测试公司'},
            'mobile': '13800138000',
            'vx': 'wx_candidate',
            'chat_history': '候选人: 手机号：13800138000，微信号：wx_candidate',
            'position': SimpleNamespace(pid='8561', incharge_id='834', requirement='岗位要求'),
            'salary': None,
        }
        bot_responses = [
            self._json_response({'choices': [{'message': {'content': '姓名：候选人\n手机号：13800138000'}}]}),
            self._json_response({'choices': [{'message': {'content': '匹配'}}]}),
            self._json_response({'choices': [{'message': {'content': '匹配，判断，适合岗位'}}]}),
            self._json_response({'choices': [{'message': {'content': '104'}}]}),
        ]
        return candidate, bot_responses

    def test_contact_card_keeps_only_unlock_placeholder(self):
        dialog = {
            'type': 123,
            'is_me': 0,
            'text': '对方同意交换联系方式，手机号：13800138000，微信号：wx_candidate',
            'common_card': {
                'center': {
                    'title': '对方同意交换联系方式',
                    'content': '13800138000 / wx_candidate',
                },
            },
            'uptimestamp': 1783410158,
        }

        line = Manager._dialog_to_chat_line(dialog)

        self.assertIn('已交换联系方式（解锁后查看）', line)
        self.assertNotIn('13800138000', line)
        self.assertNotIn('wx_candidate', line)

    def test_contact_request_is_not_marked_as_already_exchanged(self):
        dialog = {
            'type': 123,
            'is_me': 0,
            'text': '我希望与您交换联系方式',
            'common_card': {'center': {'title': '我希望与您交换联系方式'}},
            'uptimestamp': 1783410158,
        }

        line = Manager._dialog_to_chat_line(dialog)

        self.assertIn('请求交换联系方式', line)
        self.assertNotIn('已交换联系方式', line)

        chat_history = Manager._format_chat_history([dialog])
        self.assertIn('请求交换联系方式', chat_history)
        self.assertNotIn('已交换联系方式', chat_history)

    def test_unrelated_card_is_not_added_to_saved_chat_history(self):
        dialog = {
            'type': 123,
            'is_me': 0,
            'text': '对方向您发送简历',
            'common_card': {'center': {'title': '对方向您发送简历'}},
            'uptimestamp': 1783410158,
        }

        self.assertEqual(Manager._format_chat_history([dialog]), '')

    def test_wechat_is_extracted_from_card_content(self):
        dialog = {
            'type': 123,
            'is_me': 0,
            'text': '这是我的微信号',
            'common_card': {'center': {'content': 'wx_candidate'}},
            'uptimestamp': 1783410158,
        }

        self.assertEqual(Manager._find_vx_from_dialogs([dialog]), 'wx_candidate')
        self.assertIn('已交换联系方式', Manager._dialog_to_chat_line(dialog))

    def test_wechat_extraction_stops_before_explanation(self):
        dialog = {
            'type': 0,
            'is_me': 0,
            'text': '微信号：wx_candidate，添加时请备注招聘',
        }

        self.assertEqual(Manager._find_vx_from_dialogs([dialog]), 'wx_candidate')

    def test_deleted_and_recruiter_wechat_are_not_candidate_contacts(self):
        dialogs = [
            {
                'type': 123,
                'is_me': 0,
                'text': '[消息删除]',
                'common_card': {'center': {'content': '微信号：wx_deleted'}},
            },
            {
                'type': 123,
                'is_me': 1,
                'text': '职位沟通',
                'common_card': {'center': {'content': '微信号：wx_recruiter'}},
            },
        ]

        self.assertIsNone(Manager._find_vx_from_dialogs(dialogs))

    def test_wechat_without_separator_remains_supported_and_redacted(self):
        text = '微信号wx_candidate'
        dialog = {'type': 0, 'is_me': 0, 'text': text}

        self.assertEqual(Manager._find_vx_from_dialogs([dialog]), 'wx_candidate')
        self.assertNotIn('wx_candidate', _redact_contact_text(text))

    def test_overlong_wechat_is_rejected_but_still_redacted(self):
        wechat = 'a' * 33
        text = f'微信号：{wechat}'
        dialog = {'type': 0, 'is_me': 0, 'text': text}

        self.assertIsNone(Manager._find_vx_from_dialogs([dialog]))
        self.assertNotIn(wechat, _redact_contact_text(text))

    def test_plain_text_phone_and_wechat_are_redacted(self):
        text = '可以联系我，手机号：13800138000，微信号：wx_candidate。'

        redacted = _redact_contact_text(text)

        self.assertNotIn('13800138000', redacted)
        self.assertNotIn('wx_candidate', redacted)
        self.assertIn('解锁后查看', redacted)

    def test_formatted_phone_numbers_are_redacted(self):
        for phone in ('138 0013 8000', '138-0013-8000', '+86 13800138000'):
            with self.subTest(phone=phone):
                redacted = _redact_contact_text(f'手机号：{phone}')
                self.assertNotIn(phone, redacted)
                self.assertIn('解锁后查看', redacted)

    def test_plain_text_phone_is_extracted_and_normalized(self):
        for phone in ('13800138000', '138 0013 8000', '138-0013-8000', '+86 13800138000'):
            with self.subTest(phone=phone):
                dialogs = [{'type': 0, 'is_me': 0, 'text': f'手机号：{phone}'}]
                self.assertEqual(Manager._find_mobile_from_dialogs(dialogs), '13800138000')

    def test_phone_is_not_extracted_from_recruiter_or_deleted_message(self):
        dialogs = [
            {'type': 0, 'is_me': 1, 'text': '手机号：13800138000'},
            {'type': 0, 'is_me': 0, 'text': '[消息删除]'},
        ]

        self.assertIsNone(Manager._find_mobile_from_dialogs(dialogs))

    def test_unlabelled_number_inside_unrelated_text_is_not_a_phone(self):
        dialogs = [{'type': 0, 'is_me': 0, 'text': '订单号13800138000已经处理'}]

        self.assertIsNone(Manager._find_mobile_from_dialogs(dialogs))

    def test_saved_chat_history_redacts_plain_text_contact(self):
        dialogs = [{
            'type': 0,
            'is_me': 0,
            'text': '电话 13800138000，微信号：wx_candidate',
            'uptimestamp': 1783410158,
        }]

        chat_history = Manager._format_chat_history(dialogs)

        self.assertNotIn('13800138000', chat_history)
        self.assertNotIn('wx_candidate', chat_history)
        self.assertIn('解锁后查看', chat_history)

    def test_saved_chat_history_keeps_contact_card_placeholder(self):
        dialogs = [{
            'type': 123,
            'is_me': 0,
            'text': '这是我的微信号：13800138000',
            'common_card': {
                'center': {'content': '这是我的微信号：13800138000'},
                'bottom': {
                    'style1': {
                        'buttons': [{
                            'text': '复制微信',
                            'action': {
                                'copy': {
                                    'title': '这是我的微信号：13800138000',
                                    'copy_value': '13800138000',
                                },
                            },
                        }],
                    },
                },
            },
            'uptimestamp': 1783410158,
        }]

        chat_history = Manager._format_chat_history(dialogs)
        vx = Manager._find_vx_from_dialogs(dialogs)

        self.assertEqual(vx, '13800138000')
        self.assertIn('已交换联系方式（解锁后查看）', chat_history)
        self.assertNotIn('13800138000', chat_history)
    def test_queue_upload_keeps_contacts_in_resume_only(self):
        manager = Manager()
        candidate, bot_responses = self._queue_upload_data()
        add_response = self._json_response({'data': [90867]})

        with patch.object(manager, '_is_intent_upload_blocked', return_value=(False, '')), \
                patch.object(manager, '_mark_intent_uploaded'), \
                patch('src.manager.bot_io.send', side_effect=bot_responses), \
                patch('src.manager.ah_io.h5_ai_update_status'), \
                patch('src.manager.ah_io.get_user_role',
                      return_value=self._json_response({'type': 'client'})), \
                patch('src.manager.ah_io.add_resume', return_value=add_response) as add_resume, \
                patch('src.manager.ah_io.update_resume') as update_resume, \
                patch('src.manager.ah_io.h5_post'):
            manager._upload_resume(candidate)

        args, kwargs = add_resume.call_args
        self.assertIn('### 手机号: 13800138000', args[1])
        self.assertIn('### 微信号: wx_candidate', args[1])
        self.assertNotIn('13800138000', kwargs['chat_history'])
        self.assertNotIn('wx_candidate', kwargs['chat_history'])
        self.assertNotIn('phone', kwargs)
        self.assertNotIn('weixin', kwargs)
        self.assertEqual(kwargs['status'], '初审待定')
        update_resume.assert_not_called()

    def test_auto_reply_queues_complete_resume_without_job_preferences(self):
        manager = Manager()
        dialogs = [
            {
                'type': 0,
                'is_me': 1,
                'text': '您好，请问最近是否在看机会？',
                'uptimestamp': 1783410000,
                'last_did': 1,
            },
            {
                'type': 123,
                'is_me': 0,
                'text': '这是我的微信号：wx_candidate',
                'common_card': {'center': {'content': '这是我的微信号：wx_candidate'}},
                'uptimestamp': 1783410158,
                'last_did': 2,
            },
        ]
        msg = {'id': 456, 'u2': {'id': 123, 'name': '候选人'}}
        resume = {'name': '候选人', 'company': '测试公司', 'resume': {}}
        user_service = SimpleNamespace(
            user=SimpleNamespace(id=1, name='测试账号', job_dict={'8561': object()}),
            refresh=MagicMock(),
            get_msgs=MagicMock(return_value=[msg]),
            get_dialog=MagicMock(return_value=dialogs),
            get_resume=MagicMock(return_value={
                'data': resume,
                'resume_source': 'resume_card_page',
            }),
            get_mobile=MagicMock(return_value=None),
            read_msg=MagicMock(),
            add_dialog=MagicMock(return_value=3),
        )
        manager.user_services = {1: user_service}
        position = SimpleNamespace(
            pid='8561', incharge_id='834', jd='岗位描述', name='测试岗位')

        with patch('src.manager.random_sleep'), \
                patch.object(manager, '_resolve_pid_for_msg', return_value='8561'), \
                patch.object(manager, '_is_helper_initiated_conversation', return_value=True), \
                patch.object(manager, 'get_ah_position', return_value=position), \
                patch.object(manager, '_is_intent_upload_blocked', return_value=(False, '')), \
                patch.object(manager, '_persist_manager') as persist_manager, \
                patch('src.manager.bot_io.send', return_value=self._json_response({
                    'choices': [{'message': {'content': '收到，谢谢。'}}],
                })), \
                patch('src.manager.ah_io.h5_ai_update_status'), \
                patch('src.manager.ah_io.h5_ai_add_count'), \
                patch('src.manager.ah_io.h5_post'), \
                patch('src.manager.ah_io.duplicate_screening', return_value=self._json_response({
                    'duplicate': 'no',
                })):
            manager._auto_reply()

        self.assertIn(123, manager.candidates)
        self.assertIs(manager.candidates[123]['resume'], resume)
        self.assertIsNone(manager.candidates[123]['salary'])
        user_service.get_resume.assert_called_once_with(
            123, dialogs=dialogs, candidate=msg['u2'])
        persist_manager.assert_called_once_with()

    def test_auto_reply_does_not_queue_limited_profile(self):
        manager = Manager()
        dialogs = [
            {
                'type': 0,
                'is_me': 1,
                'text': '您好，请问最近是否在看机会？',
                'uptimestamp': 1783410000,
                'last_did': 1,
            },
            {
                'type': 123,
                'is_me': 0,
                'text': '这是我的微信号：wx_candidate',
                'common_card': {'center': {'content': '这是我的微信号：wx_candidate'}},
                'uptimestamp': 1783410158,
                'last_did': 2,
            },
        ]
        msg = {'id': 456, 'u2': {'id': 123, 'name': '候选人'}}
        user_service = SimpleNamespace(
            user=SimpleNamespace(id=1, name='测试账号', job_dict={'8561': object()}),
            refresh=MagicMock(),
            get_msgs=MagicMock(return_value=[msg]),
            get_dialog=MagicMock(return_value=dialogs),
            get_resume=MagicMock(return_value={
                'data': {'card': {'realname': '候选人'}},
                'resume_source': 'contact_profile_fallback',
                'resume_limited': True,
            }),
            get_mobile=MagicMock(return_value=None),
            read_msg=MagicMock(),
            add_dialog=MagicMock(return_value=3),
        )
        manager.user_services = {1: user_service}
        position = SimpleNamespace(
            pid='8561', incharge_id='834', jd='岗位描述', name='测试岗位')

        with patch('src.manager.random_sleep'), \
                patch.object(manager, '_resolve_pid_for_msg', return_value='8561'), \
                patch.object(manager, '_is_helper_initiated_conversation', return_value=True), \
                patch.object(manager, 'get_ah_position', return_value=position), \
                patch.object(manager, '_is_intent_upload_blocked', return_value=(False, '')), \
                patch.object(manager, '_persist_manager') as persist_manager, \
                patch('src.manager.bot_io.send', return_value=self._json_response({
                    'choices': [{'message': {'content': '收到，谢谢。'}}],
                })), \
                patch('src.manager.ah_io.h5_ai_update_status'), \
                patch('src.manager.ah_io.h5_ai_add_count'), \
                patch('src.manager.ah_io.h5_post'), \
                patch('src.manager.ah_io.duplicate_screening', return_value=self._json_response({
                    'duplicate': 'no',
                })):
            manager._auto_reply()

        self.assertEqual(manager.candidates, {})
        user_service.get_resume.assert_called_once_with(
            123, dialogs=dialogs, candidate=msg['u2'])
        persist_manager.assert_not_called()

    def test_empty_queue_returns_zero_stats(self):
        manager = Manager()

        result = manager.process_upload_resume()

        self.assertEqual(result, {
            'queued': 0,
            'processed': 0,
            'succeeded': 0,
            'skipped': 0,
            'failed': 0,
            'remaining': 0,
        })

    def test_empty_upload_response_keeps_candidate_for_retry(self):
        manager = Manager()
        candidate, bot_responses = self._queue_upload_data()
        manager.candidates = {123: candidate}

        with patch.object(manager, '_is_intent_upload_blocked', return_value=(False, '')), \
                patch.object(manager, '_persist_manager') as persist_manager, \
                patch('src.manager.bot_io.send', side_effect=bot_responses), \
                patch('src.manager.ah_io.h5_ai_update_status'), \
                patch('src.manager.ah_io.get_user_role',
                      return_value=self._json_response({'type': 'client'})), \
                patch('src.manager.ah_io.add_resume', return_value=SimpleNamespace(text='')):
            result = manager.process_upload_resume()

        self.assertEqual(result['failed'], 1)
        self.assertEqual(result['remaining'], 1)
        self.assertIn(123, manager.candidates)
        persist_manager.assert_called_once_with()

    def test_successful_queue_upload_returns_stats_and_clears_queue(self):
        manager = Manager()
        candidate, bot_responses = self._queue_upload_data()
        manager.candidates = {123: candidate}

        with patch.object(manager, '_is_intent_upload_blocked', return_value=(False, '')), \
                patch.object(manager, '_mark_intent_uploaded'), \
                patch.object(manager, '_persist_manager') as persist_manager, \
                patch('src.manager.bot_io.send', side_effect=bot_responses), \
                patch('src.manager.ah_io.h5_ai_update_status'), \
                patch('src.manager.ah_io.get_user_role',
                      return_value=self._json_response({'type': 'client'})), \
                patch('src.manager.ah_io.add_resume', return_value=self._json_response({
                    'data': [90867],
                })), \
                patch('src.manager.ah_io.h5_post'):
            result = manager.process_upload_resume()

        self.assertEqual(result, {
            'queued': 1,
            'processed': 1,
            'succeeded': 1,
            'skipped': 0,
            'failed': 0,
            'remaining': 0,
        })
        self.assertEqual(manager.candidates, {})
        persist_manager.assert_called_once_with()

    def test_save_resume_non_match_uses_general_match_comment(self):
        manager = Manager()
        user_service = SimpleNamespace(user=SimpleNamespace(name='测试账号'))
        msg = {'u2': {'id': 123, 'name': '候选人'}}
        position = SimpleNamespace(pid='8561', incharge_id='834', requirement='岗位要求')
        resume = {'name': '候选人', 'company': '测试公司', 'job_preferences': {}}
        bot_responses = [
            self._json_response({'choices': [{'message': {'content': '姓名：候选人'}}]}),
            self._json_response({'choices': [{'message': {'content': '不匹配'}}]}),
            self._json_response({
                'choices': [{'message': {'content': '不匹配，因为缺少岗位要求的相关经验'}}],
            }),
            self._json_response({'choices': [{'message': {'content': '104'}}]}),
        ]

        with patch('src.manager.bot_io.send', side_effect=bot_responses), \
                patch.object(manager, '_find_intent_duplicate_current_position_record',
                             return_value=None), \
                patch('src.manager.ah_io.get_user_role',
                      return_value=self._json_response({'type': 'client'})), \
                patch('src.manager.ah_io.add_resume',
                      return_value=self._json_response({'data': [90870]})) as add_resume, \
                patch.object(manager, '_mark_intent_uploaded'), \
                patch('src.manager.ah_io.h5_post'):
            result = manager._save_resume_to_intent_library(
                user_service,
                msg,
                position,
                resume,
                '13800138000',
                'wx_candidate',
                '候选人: [已交换联系方式（解锁后查看）]',
            )

        self.assertEqual(result, 'uploaded_intent')
        _, kwargs = add_resume.call_args
        self.assertEqual(kwargs['status'], '待筛选')
        self.assertIn('一般匹配', kwargs['comment'])
        self.assertNotIn('不匹配', kwargs['comment'])

    def test_save_resume_new_record_keeps_contacts_in_resume_only(self):
        manager = Manager()
        user_service = SimpleNamespace(user=SimpleNamespace(name='测试账号'))
        msg = {'u2': {'id': 123, 'name': '候选人'}}
        position = SimpleNamespace(pid='8561', incharge_id='834', requirement='岗位要求')
        resume = {
            'name': '候选人',
            'company': '测试公司',
            'job_preferences': {},
        }
        bot_responses = [
            self._json_response({'choices': [{'message': {'content': '姓名：候选人'}}]}),
            self._json_response({'choices': [{'message': {'content': '匹配'}}]}),
            self._json_response({'choices': [{'message': {'content': '匹配，判断，适合岗位'}}]}),
            self._json_response({'choices': [{'message': {'content': '104'}}]}),
        ]
        with patch('src.manager.bot_io.send', side_effect=bot_responses), \
                patch.object(manager, '_find_intent_duplicate_current_position_record',
                             return_value=None), \
                patch('src.manager.ah_io.get_user_role',
                      return_value=self._json_response({'type': 'client'})), \
                patch('src.manager.ah_io.add_resume',
                      return_value=self._json_response({'data': [90869]})) as add_resume, \
                patch('src.manager.ah_io.update_resume') as update_resume, \
                patch.object(manager, '_mark_intent_uploaded'), \
                patch('src.manager.ah_io.h5_post'):
            result = manager._save_resume_to_intent_library(
                user_service,
                msg,
                position,
                resume,
                '13800138000',
                'wx_candidate',
                '候选人: [已交换联系方式（解锁后查看）]',
            )

        self.assertEqual(result, 'uploaded_intent')
        args, kwargs = add_resume.call_args
        self.assertIn('### 手机号: 13800138000', args[1])
        self.assertIn('### 微信号: wx_candidate', args[1])
        self.assertNotIn('13800138000', kwargs['chat_history'])
        self.assertNotIn('wx_candidate', kwargs['chat_history'])
        self.assertNotIn('phone', kwargs)
        self.assertNotIn('weixin', kwargs)
        self.assertEqual(kwargs['status'], '初审待定')
        update_resume.assert_not_called()

    def test_existing_intent_record_does_not_use_unsupported_contact_fields(self):
        manager = Manager()
        user_service = SimpleNamespace(user=SimpleNamespace(name='测试账号'))
        msg = {'u2': {'id': 123, 'name': '候选人'}}
        position = SimpleNamespace(pid='8561', incharge_id='834', requirement='岗位要求')
        resume = {'name': '候选人', 'company': '测试公司'}
        bot_responses = [
            self._json_response({'choices': [{'message': {'content': '姓名：候选人'}}]}),
            self._json_response({'choices': [{'message': {'content': '匹配'}}]}),
            self._json_response({'choices': [{'message': {'content': '匹配，判断，适合岗位'}}]}),
            self._json_response({'choices': [{'message': {'content': '104'}}]}),
        ]

        with patch('src.manager.bot_io.send', side_effect=bot_responses), \
                patch.object(manager, '_find_intent_duplicate_current_position_record',
                             return_value={'id': 90866}), \
                patch('src.manager.ah_io.update_chat_history'), \
                patch('src.manager.ah_io.update_resume') as update_resume:
            result = manager._save_resume_to_intent_library(
                user_service,
                msg,
                position,
                resume,
                '13800138000',
                'wx_candidate',
                '候选人: [已交换联系方式（解锁后查看）]',
            )

        self.assertEqual(result, 'updated_intent')
        _, kwargs = update_resume.call_args
        self.assertEqual(kwargs['status'], '初审待定')
        self.assertNotIn('phone', kwargs)
        self.assertNotIn('weixin', kwargs)

    def test_auto_reply_duplicate_keeps_redacted_history_without_contact_update(self):
        manager = Manager()
        dialogs = [
            {
                'type': 0,
                'is_me': 1,
                'text': '您好，请问最近是否在看机会？',
                'uptimestamp': 1783410000,
                'last_did': 1,
            },
            {
                'type': 123,
                'is_me': 0,
                'text': '这是我的微信号：13800138000',
                'common_card': {'center': {'content': '这是我的微信号：13800138000'}},
                'uptimestamp': 1783410158,
                'last_did': 2,
            },
        ]
        msg = {'id': 456, 'u2': {'id': 123, 'name': '候选人'}}
        resume = {
            'name': '候选人',
            'company': '测试公司',
            'resume': {},
            'job_preferences': {},
        }
        user_service = SimpleNamespace(
            user=SimpleNamespace(id=1, name='测试账号', job_dict={'8561': object()}),
            refresh=MagicMock(),
            get_msgs=MagicMock(return_value=[msg]),
            get_dialog=MagicMock(return_value=dialogs),
            get_resume=MagicMock(return_value={'data': resume}),
            get_mobile=MagicMock(return_value=None),
            read_msg=MagicMock(),
            add_dialog=MagicMock(return_value=3),
        )
        manager.user_services = {1: user_service}
        position = SimpleNamespace(
            pid='8561', incharge_id='834', jd='岗位描述', name='测试岗位')
        bot_responses = [
            self._json_response({'choices': [{'message': {'content': '收到，谢谢。'}}]}),
            self._json_response({'choices': [{'message': {'content': '104'}}]}),
        ]

        with patch('src.manager.random_sleep'), \
                patch.object(manager, '_resolve_pid_for_msg', return_value='8561'), \
                patch.object(manager, '_is_helper_initiated_conversation', return_value=True), \
                patch.object(manager, 'get_ah_position', return_value=position), \
                patch.object(manager, '_is_intent_upload_blocked',
                             return_value=(True, '意向人才查重重复')), \
                patch.object(manager, '_remove_candidate_from_queue'), \
                patch('src.manager.bot_io.send', side_effect=bot_responses), \
                patch('src.manager.ah_io.h5_ai_update_status'), \
                patch('src.manager.ah_io.h5_ai_add_count'), \
                patch('src.manager.ah_io.h5_post'), \
                patch('src.manager.ah_io.duplicate_screening', return_value=self._json_response({
                    'duplicate': 'no',
                })), \
                patch('src.manager.ah_io.duplicate', return_value=self._json_response({
                    'data': [{'id': 90866}],
                })), \
                patch('src.manager.ah_io.update_chat_history') as update_chat_history, \
                patch('src.manager.ah_io.update_resume') as update_resume:
            manager._auto_reply()

        _, history = update_chat_history.call_args.args
        self.assertIn('已交换联系方式（解锁后查看）', history)
        self.assertNotIn('13800138000', history)
        _, kwargs = update_resume.call_args
        self.assertNotIn('phone', kwargs)
        self.assertNotIn('weixin', kwargs)

    def test_duplicate_update_does_not_use_unsupported_contact_fields(self):
        manager = Manager()
        position = SimpleNamespace(pid='8561', incharge_id='834')

        with patch('src.manager.ah_io.duplicate', return_value=self._json_response({
                    'data': [{'id': 90866}],
                })), \
                patch('src.manager.ah_io.update_chat_history'), \
                patch('src.manager.bot_io.send', return_value=self._json_response({
                    'choices': [{'message': {'content': '104'}}],
                })), \
                patch('src.manager.ah_io.update_resume') as update_resume:
            manager._update_intent_duplicate(
                position,
                None,
                '13800138000',
                '候选人: [已交换联系方式（解锁后查看）]',
                '候选人',
            )

        _, kwargs = update_resume.call_args
        self.assertNotIn('phone', kwargs)
        self.assertNotIn('weixin', kwargs)


class HighestEducationTest(unittest.TestCase):
    def test_missing_major_is_completed_from_same_school_and_degree(self):
        source = {'edu': [{'school': '安徽建筑大学', 'degree': '本科'}]}
        before = json.dumps(source)
        cleaned = ('教育经历\n时间：2007-09 - 2011-08\n学历：本科\n'
                   '专业：应用物理学\n大学名称：安徽建筑大学')
        self.assertEqual(extract_highest_education(source, cleaned),
                         {'school': '安徽建筑大学', 'major': '应用物理学'})
        self.assertEqual(json.dumps(source), before)

    def test_matching_degree_alias_and_json_source_can_complete_major(self):
        self.assertEqual(extract_highest_education(
            {'school': 'MIT', 'degree': '本科'},
            json.dumps({'Education': [{'School': 'MIT', 'Degree': 'Bachelor', 'Field': 'Physics'}]})),
            {'school': 'MIT', 'major': 'Physics'})

    def test_only_matching_record_is_used_even_if_fallback_has_higher_degree(self):
        self.assertEqual(extract_highest_education(
            {'school': '甲大学', 'degree': '本科'}, [
                {'school': '乙大学', 'degree': '硕士', 'major': '金融'},
                {'school': '甲大学', 'degree': '本科', 'major': '物理'},
            ]), {'school': '甲大学', 'major': '物理'})

    def test_completion_requires_known_matching_school_and_degree(self):
        for fallback in (
            {'school': '乙大学', 'degree': '本科', 'major': '物理'},
            {'school': '甲大学', 'degree': '硕士', 'major': '物理'},
            {'school': '甲大学', 'major': '物理'},
            {'degree': '本科', 'major': '物理'},
            {'school': '甲大学', 'degree': '本科', 'major': '暂无'},
        ):
            with self.subTest(fallback=fallback):
                self.assertEqual(extract_highest_education(
                    {'school': '甲大学', 'degree': '本科'}, fallback),
                    {'school': '甲大学', 'major': ''})
        self.assertEqual(extract_highest_education(
            {'school': '甲大学'}, {'school': '甲大学', 'major': '物理'}),
            {'school': '甲大学', 'major': ''})

    def test_single_school_with_unknown_degree_uses_complete_clean_education(self):
        cleaned = ('## 教育经历\n\n**时间**：2014-09 - 2018-06\n'
                   '**学历**：本科\n**专业**：计算机科学与技术\n**大学名称**：江南大学')
        for degree in (None, '', '未填写', '未知编码', 0, 4, '2'):
            source = {'edu': [{'school': '江南大学', 'degree': degree}]}
            before = json.dumps(source)
            with self.subTest(degree=degree):
                self.assertEqual(extract_highest_education(source, cleaned),
                                 {'school': '江南大学', 'major': '计算机科学与技术'})
                self.assertEqual(json.dumps(source), before)
        self.assertEqual(extract_highest_education({'school': '江南大学'}, cleaned),
                         {'school': '江南大学', 'major': '计算机科学与技术'})

    def test_unknown_degree_fallback_rejects_other_school_and_incomplete_record(self):
        for fallback in (
            {'school': '其他大学', 'degree': '本科', 'major': '物理'},
            {'school': '江南大学', 'major': '物理'},
            {'school': '江南大学', 'degree': '其他', 'major': '物理'},
            {'school': '江南大学', 'degree': '本科', 'major': '--'},
            {'degree': '本科', 'major': '物理'},
        ):
            with self.subTest(fallback=fallback):
                self.assertEqual(extract_highest_education({'school': '江南大学'}, fallback),
                                 {'school': '江南大学', 'major': ''})

    def test_unknown_degree_does_not_choose_between_multiple_fallback_records(self):
        complete = {'school': '江南大学', 'degree': '本科', 'major': '物理'}
        for second in (
            dict(complete, degree='硕士'),
            dict(complete, major='数学'),
            dict(complete, school='其他大学'),
            {'school': '江南大学'},
        ):
            with self.subTest(second=second):
                self.assertEqual(extract_highest_education(
                    {'school': '江南大学'}, [complete, second]),
                    {'school': '江南大学', 'major': ''})

    def test_unknown_degree_multiple_sources_must_agree_on_degree_and_major(self):
        complete = {'school': '江南大学', 'degree': '本科', 'major': '物理'}
        for second in (dict(complete, degree='硕士'), dict(complete, major='数学')):
            with self.subTest(second=second):
                self.assertEqual(extract_highest_education(
                    {'school': '江南大学'}, complete, second),
                    {'school': '江南大学', 'major': ''})
        self.assertEqual(extract_highest_education(
            {'school': '江南大学'}, complete, dict(complete, degree='Bachelor')),
            {'school': '江南大学', 'major': '物理'})

    def test_unknown_degree_existing_major_is_preserved(self):
        self.assertEqual(extract_highest_education(
            {'school': '江南大学', 'major': '数学'},
            {'school': '江南大学', 'degree': '本科', 'major': '物理'}),
            {'school': '江南大学', 'major': '数学'})

    def test_multiple_matching_records_in_either_source_are_not_merged(self):
        missing = {'school': '甲大学', 'degree': '本科'}
        complete = dict(missing, major='物理')
        for first, second in (([missing, missing], complete),
                              (missing, [complete, missing]),
                              (missing, [complete, dict(missing, major='数学')])):
            with self.subTest(first=first, second=second):
                self.assertEqual(extract_highest_education(first, second),
                                 {'school': '甲大学', 'major': ''})

    def test_conflicting_fallback_sources_do_not_guess_major(self):
        missing = {'school': '甲大学', 'degree': '本科'}
        self.assertEqual(extract_highest_education(
            missing, dict(missing, major='物理'), dict(missing, major='数学')),
            {'school': '甲大学', 'major': ''})

    def test_existing_major_is_never_overwritten_by_same_school_fallback(self):
        self.assertEqual(extract_highest_education(
            {'school': '甲大学', 'degree': '本科', 'major': '数学'},
            {'school': '甲大学', 'degree': '本科', 'major': '物理'}),
            {'school': '甲大学', 'major': '数学'})

    def test_highest_degree_keeps_school_and_major_together(self):
        result = extract_highest_education({'edu': [
            {'school': '本科学校', 'degree': '本科', 'major': '教育学'},
            {'school': '硕士学校', 'degree': '硕士', 'major': 'MBA'},
        ]})
        self.assertEqual(result, {'school': '硕士学校', 'major': 'MBA'})

    def test_english_degrees_and_same_rank_keep_source_order(self):
        self.assertEqual(extract_highest_education([
            {'School': 'Stanford', 'Degree': 'Master of Science', 'Field': 'CS'},
            {'School': 'MIT', 'Degree': 'Ph.D.', 'Field': 'AI'},
            {'School': 'Oxford', 'Degree': 'Ph.D.', 'Field': 'Physics'},
        ]), {'school': 'MIT', 'major': 'AI'})

    def test_missing_major_does_not_borrow_from_lower_degree_or_fallback(self):
        self.assertEqual(extract_highest_education([
            {'school': '博士学校', 'degree': '博士'},
            {'school': '本科学校', 'degree': '本科', 'major': '软件工程'},
        ], '学校：其他学校\n专业：其他专业'), {'school': '博士学校', 'major': ''})

    def test_missing_school_keeps_major_from_highest_record(self):
        self.assertEqual(extract_highest_education([
            {'degree': '硕士', 'major': '计算机科学'},
            {'degree': '本科', 'school': '本科学校', 'major': '软件工程'},
        ]), {'school': '', 'major': '计算机科学'})

    def test_single_unknown_degree_is_usable_but_multiple_are_ambiguous(self):
        record = {'university': '浙江大学', 'field': '数学'}
        self.assertEqual(extract_highest_education([record]),
                         {'school': '浙江大学', 'major': '数学'})
        self.assertEqual(extract_highest_education([record, {'school': '另一所学校'}]),
                         {'school': '', 'major': ''})

    def test_maimai_text_ignores_school_badges(self):
        self.assertEqual(extract_highest_education(
            '教育经历\n西班牙武康大学\n硕士，MBA\n2022-03至2024-03\n'
            'ta有3个好友在此学校\n华东师范大学\n985\n211\n本科，教育学原理\n'
            '2009-01至2012-01\n职业标签\n人力资源管理'),
            {'school': '西班牙武康大学', 'major': 'MBA'})

    def test_markdown_supports_school_before_and_after_degree(self):
        cases = [
            ('## 教育经历\n### 北京大学\n**学历**：硕士\n**专业**：计算机科学\n'
             '## 工作经历\n某公司', {'school': '北京大学', 'major': '计算机科学'}),
            ('## 教育经历\n**时间**：2016 - 2017\n**学历**：硕士\n'
             '**专业**：Marketing\n**大学名称**：Lancaster University\n---\n'
             '**时间**：2012 - 2016\n**学历**：本科\n**专业**：English\n'
             '**大学名称**：另一所大学',
             {'school': 'Lancaster University', 'major': 'Marketing'}),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(extract_highest_education(source), expected)

    def test_text_does_not_borrow_major_from_next_school(self):
        self.assertEqual(extract_highest_education(
            '教育经历\n学校：博士学校\n学历：博士\n学校：本科学校\n专业：数学\n学历：本科'),
            {'school': '博士学校', 'major': ''})

    def test_markdown_blank_lines_do_not_lose_school(self):
        self.assertEqual(extract_highest_education(
            '## 教育经历\n\n### 北京大学\n\n**学历**：硕士\n\n**专业**：数学'),
            {'school': '北京大学', 'major': '数学'})

    def test_major_text_does_not_change_degree_rank(self):
        self.assertEqual(extract_highest_education(
            '教育经历\n北京大学\n本科，博士后管理研究\n2010-01至2014-01\n'
            '复旦大学\n硕士，数学'), {'school': '复旦大学', 'major': '数学'})

    def test_imba_major_does_not_hide_following_school_in_two_degree_resume(self):
        text = ('## 教育经历\n\n**时间**：2015-09 - 2017-06\n**学历**：硕士\n'
                '**专业**：IMBA\n**大学名称**：复旦大学\n\n---\n\n'
                '**时间**：2005-01 - 2009-01\n**学历**：本科\n'
                '**专业**：信息管理与信息系统\n**大学名称**：中国地质大学（北京）')
        self.assertEqual(extract_highest_education(text),
                         {'school': '复旦大学', 'major': 'IMBA'})

    def test_labeled_major_is_not_a_degree_boundary_in_either_direction(self):
        for major in ('IMBA', 'MBA', 'EMBA', '博士后管理研究', 'Master Data Management'):
            for text in (
                f'教育经历\n学历：硕士\n专业：{major}\n大学名称：复旦大学',
                f'教育经历\n大学名称：复旦大学\n专业：{major}\n学历：硕士',
            ):
                with self.subTest(text=text):
                    self.assertEqual(extract_highest_education(text)['school'], '复旦大学')

    def test_labeled_school_with_degree_word_is_still_a_school(self):
        self.assertEqual(extract_highest_education(
            '教育经历\n学历：硕士\n专业：数学\n大学名称：Master University'),
            {'school': 'Master University', 'major': '数学'})

    def test_labeled_education_fields_can_appear_in_any_order(self):
        from itertools import permutations
        fields = ['学历：硕士', '专业：IMBA', '大学名称：复旦大学']
        for lines in permutations(fields):
            with self.subTest(lines=lines):
                self.assertEqual(extract_highest_education('教育经历\n' + '\n'.join(lines)),
                                 {'school': '复旦大学', 'major': 'IMBA'})

    def test_labeled_fields_are_not_limited_to_two_or_four_following_lines(self):
        self.assertEqual(extract_highest_education(
            '教育经历\n时间：2015-09 - 2017-06\n学历：硕士\n985\n211\n双一流\n'
            '专业：IMBA\n大学名称：复旦大学'),
            {'school': '复旦大学', 'major': 'IMBA'})

    def test_imba_does_not_cross_real_education_boundaries_to_borrow_school(self):
        for boundary in ('---', '时间：2005-01 - 2009-01', '学历：本科'):
            with self.subTest(boundary=boundary):
                self.assertEqual(extract_highest_education(
                    '教育经历\n学历：硕士\n专业：IMBA\n' + boundary +
                    '\n大学名称：中国地质大学（北京）\n学历：本科\n专业：信息管理'),
                    {'school': '', 'major': 'IMBA'})

    def test_only_education_section_supplies_degree_records(self):
        self.assertEqual(extract_highest_education(
            '工作经历\n某科技公司\n负责硕士人才招聘\n项目经历\n校园招聘'),
            {'school': '', 'major': ''})

    def test_empty_and_malformed_values_do_not_block_extraction(self):
        for source in (None, 1, True, [], {}, '无教育信息',
                       {'school': {'name': '未知学校'}, 'major': ['数学']},
                       {'edu': [None, 'invalid', {'school': '暂无', 'major': '--'}]}):
            with self.subTest(source=source):
                self.assertEqual(extract_highest_education(source), {'school': '', 'major': ''})

    def test_structured_source_precedes_cleaned_resume_without_mutation(self):
        source = {'educations': [{'school': '原始学校', 'degree': '本科', 'major': '数学'}]}
        before = json.dumps(source)
        self.assertEqual(extract_highest_education(source, '学校：AI学校\n专业：AI专业'),
                         {'school': '原始学校', 'major': '数学'})
        self.assertEqual(json.dumps(source), before)

    def test_json_text_and_labeled_text_fallback(self):
        self.assertEqual(extract_highest_education(json.dumps(
            {'Education': [{'School': 'MIT', 'Degree': 'Ph.D.', 'Field': 'AI'}]})),
            {'school': 'MIT', 'major': 'AI'})
        self.assertEqual(extract_highest_education({}, 'School: Oxford\nMajor: Economics'),
                         {'school': 'Oxford', 'major': 'Economics'})

    def test_ambiguous_labeled_fields_are_not_guessed(self):
        self.assertEqual(extract_highest_education('学校：甲\n学校：乙\n专业：数学'),
                         {'school': '', 'major': ''})


class ScreeningEducationSourceTest(unittest.TestCase):
    def test_four_reported_education_examples_match_uploaded_resume(self):
        cases = [
            ('安徽建筑大学', '本科', '应用物理学'),
            ('江南大学', '本科', '计算机科学与技术'),
            ('复旦大学', '硕士', 'IMBA'),
            ('台湾崐山大学', '本科', '空间设计'),
        ]
        for school, degree, major in cases:
            with self.subTest(school=school):
                uploaded = f'教育经历\n时间：2011-09 - 2015-06\n学历：{degree}\n专业：{major}\n大学名称：{school}'
                fields, selection = extract_screening_education(
                    {'school': '原始拼写或过期学校', 'degree': 2}, uploaded)
                self.assertEqual(fields, {'school': school, 'major': major})
                self.assertEqual(selection['source'], 'uploaded_resume')
                self.assertEqual(selection['reason'], 'complete')

    def test_unparseable_or_empty_education_section_does_not_use_raw_fields(self):
        for uploaded in ('教育经历\n暂无', '教育经历\n学校：--\n专业：--',
                         '教育经历\n学校：甲大学\n学校：乙大学'):
            with self.subTest(uploaded=uploaded):
                fields, selection = extract_screening_education(
                    {'school': '原始大学', 'degree': '本科', 'major': '原始专业'}, uploaded)
                self.assertEqual(fields, {'school': '', 'major': ''})
                self.assertEqual(selection['source'], 'uploaded_resume')
                self.assertEqual(selection['reason'], 'unresolved')

    def test_highest_record_with_no_fields_is_not_replaced_by_lower_record(self):
        fields, selection = extract_screening_education({},
            '教育经历\n学历：硕士\n---\n学历：本科\n学校：甲大学\n专业：数学')
        self.assertEqual(fields, {'school': '', 'major': ''})
        self.assertEqual(selection['reason'], 'incomplete')

    def test_raw_is_only_a_whole_record_fallback_when_uploaded_education_absent(self):
        fields, selection = extract_screening_education(
            {'edu': [{'school': '甲大学', 'degree': '硕士', 'major': '数学'}]},
            '工作经历\n某公司\n推荐信息\n擅长产品设计')
        self.assertEqual(fields, {'school': '甲大学', 'major': '数学'})
        self.assertEqual(selection['source'], 'raw_resume_fallback')

    def test_diagnostics_cannot_break_upload_and_do_not_log_resume_or_response_body(self):
        logger = MagicMock()
        fields, selection = extract_screening_education({}, '教育经历\n学历：本科\n学校：甲大学\n专业：数学')
        response = MagicMock(status_code=200)
        response.json.return_value = {'success': False, 'resume': 'secret resume', 'phone': '13800138000'}
        log_screening_education(logger, 'upload_response', 8666, 101, fields, selection, response)
        message = logger.write_line.call_args.args[0]
        event = json.loads(message.removeprefix('高潜教育诊断 '))
        self.assertEqual(event['http_status'], 200)
        self.assertIs(event['business_success'], False)
        self.assertNotIn('secret resume', message)
        self.assertNotIn('13800138000', message)
        logger.write_line.side_effect = OSError('disk unavailable')
        log_screening_education(logger, 'upload_request', 8666, 101, fields, selection)

    def test_http_200_without_explicit_business_success_is_not_saved_confirmation(self):
        response = MagicMock(status_code=200)
        response.json.side_effect = ValueError('non-JSON response')
        logger = MagicMock()
        log_screening_education(logger, 'upload_response', 8666, 101,
                               {'school': '甲大学', 'major': '数学'}, {}, response)
        event = json.loads(logger.write_line.call_args.args[0].removeprefix('高潜教育诊断 '))
        self.assertIsNone(event['business_success'])


class FirstContactEducationUploadTest(unittest.TestCase):
    @staticmethod
    def _response(payload):
        # 使用真实 Response，防止 mock 掩盖 AI 响应未解包的问题。
        from requests import Response
        response = Response()
        response.status_code = 200
        response._content = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        response.encoding = 'utf-8'
        return response

    def _run_first_contact(self, education=None, comments=None, client=False, duplicate=False,
                           clean_education='', malformed_first=False):
        comments = comments or ['是，判断合理，确实非常匹配，经验符合']
        uids = [101 + i for i in range(len(comments))]
        manager = Manager()
        manager.logger = MagicMock()
        service = MagicMock()
        service.user = SimpleNamespace(id=1, name='测试账号')
        service.get_jname_by_pid.return_value = '测试岗位8561'
        service.search_candidate.side_effect = [
            {'total': len(uids)},
            {'all_uids': uids, 'list': [{'id': uid} for uid in uids]},
            {'all_uids': []},
        ]
        service.batch_send_job.return_value = {
            'succ_count': len(uids),
            'data': [{str(uid): {'mid': uid + 1000}} for uid in uids],
        }
        resume = {
            'name': '候选人', 'current_company': {'company': '测试公司', 'position': '工程师'},
            'age': 30, 'edu': education or [],
        }
        service.get_resume.return_value = {'data': resume}
        manager.user_services = {1: service}
        manager.get_search_conditions = MagicMock(return_value={1: object()})
        manager.get_ah_position = MagicMock(return_value=SimpleNamespace(
            pid=8561, incharge_id=42, requirement='深匹要求：软件工程'))
        fact_comments = iter(comments)
        bot_calls = []

        def bot_send(prompt, bot_id):
            from src.config.bot import ENUM_MODEL_ID as Bot
            bot_calls.append((prompt, bot_id))
            outputs = {
                Bot.RESUME_BATCH_PRE_CHECK.value: ','.join(map(str, uids)),
                Bot.MATCH_CHECK_FIRST.value: '匹配，首轮实际结论',
                Bot.CLEAN_SCREENING_RESUME.value: f'{clean_education}\n## 推荐信息\n**推荐语**：工程经验丰富',
                Bot.AI_SUMMARY_RESUME.value: '**期待薪资**：20K\n**居住地**：上海\n**优势标签**：研发',
            }
            if bot_id == Bot.MATCH_CHECK_FIRST.value and malformed_first:
                return self._response({'error': 'invalid response'})
            output = next(fact_comments) if bot_id == Bot.MATCH_CHECK_SECOND.value else outputs[bot_id]
            return self._response({'choices': [{'message': {'content': output}}]})

        with ExitStack() as stack:
            stack.enter_context(patch('requests.sessions.Session.request',
                                     side_effect=AssertionError('Live network forbidden')))
            stack.enter_context(patch('src.manager.random_sleep'))
            stack.enter_context(patch('src.manager.bot_io.send', side_effect=bot_send))
            stack.enter_context(patch('src.manager.get_incharge_id_by_pid',
                                     return_value=self._response({'results': [{'incharge_id': 42}]})))
            stack.enter_context(patch('src.manager.get_user_role', return_value=self._response(
                {'type': 'client' if client else 'hunter'})))
            stack.enter_context(patch('src.manager.ah_io.get_position_info', return_value=self._response(
                {'results': [{'summary': '深匹要求：软件工程'}]})))
            stack.enter_context(patch('src.manager.ah_io.duplicate_screening', return_value=self._response({
                'duplicate': 'yes' if duplicate else 'no',
                'records': [{'Position': '其他岗位', 'position_id': '9999'}] if duplicate else [],
            })))
            for target in ('src.manager.h5_post', 'src.manager.ah_io.h5_ai_update_status',
                           'src.manager.ah_io.h5_ai_add_count'):
                stack.enter_context(patch(target))
            post = stack.enter_context(patch('src.io.anyhelper.requests.post',
                                            return_value=self._response({'success': True})))
            update = stack.enter_context(patch('src.manager.ah_io.update_screening_resume'))
            intent = stack.enter_context(patch('src.manager.ah_io.add_resume'))
            result = manager.first_contact('8561', [1], '您好', user_ids=[1])
            update.assert_not_called()
            intent.assert_not_called()
            return result, post.call_args_list, bot_calls, manager

    def test_actual_form_payload_adds_education_and_keeps_existing_fields(self):
        result, calls, bots, manager = self._run_first_contact(education=[
            {'school': '本科学校', 'degree': '本科', 'major': '数学'},
            {'school': '硕士学校', 'degree': '硕士', 'major': '计算机'},
        ])
        self.assertEqual(result, (1, 1, []))
        self.assertEqual(len(calls), 1)
        url, payload = calls[0].args
        self.assertEqual(url, 'https://talent.example.invalid/api/add_screening_resume.php')
        self.assertEqual(payload, {
            'position_id': '8561', 'incharge_id': 42, 'status': '待联系', 'coins_cost': 2,
            'name': '候选人', 'liepin_keywords': '101', 'current_company': '测试公司',
            'current_position': '工程师', 'resume_content': '\n## 推荐信息\n**推荐语**：工程经验丰富',
            'ai_summary': '**期待薪资**：20K\n**居住地**：上海\n**优势标签**：研发',
            'comment': '非常匹配，经验符合', 'source': 'maimai',
            'salary': '20K', 'age': 30, 'location': '上海', 'tags': '研发',
            'school': '硕士学校', 'major': '计算机',
        })
        self.assertEqual(len(bots), 5)  # 不为两个新字段增加 AI 调用。
        self.assertIn('首轮实际结论', bots[2][0])
        self.assertNotIn('<Response', bots[2][0])
        self.assertEqual(manager.candidates, {})
        self.assertEqual(manager.intent_uploaded_keys, set())
        self.assertEqual(manager.pid_candidate_contacted_sets['8561'], {101})

    def test_missing_education_still_uploads_with_empty_strings(self):
        result, calls, _, _ = self._run_first_contact()
        self.assertEqual(result, (1, 1, []))
        self.assertEqual(calls[0].args[1]['school'], '')
        self.assertEqual(calls[0].args[1]['major'], '')

    def test_completed_major_reaches_upload_without_extra_ai_calls(self):
        result, calls, bots, manager = self._run_first_contact(
            education=[{'school': '安徽建筑大学', 'degree': '本科'}],
            clean_education='教育经历\n时间：2007-09 - 2011-08\n学历：本科\n专业：应用物理学\n大学名称：安徽建筑大学')
        self.assertEqual(result, (1, 1, []))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[1]['school'], '安徽建筑大学')
        self.assertEqual(calls[0].args[1]['major'], '应用物理学')
        self.assertEqual(calls[0].args[1]['status'], '待联系')
        self.assertEqual(len(bots), 5)
        self.assertEqual(manager.pid_candidate_contacted_sets['8561'], {101})

    def test_different_raw_degree_does_not_override_uploaded_education(self):
        result, calls, bots, _ = self._run_first_contact(
            education=[{'school': '甲大学', 'degree': '硕士'}],
            clean_education='教育经历\n学校：甲大学\n学历：本科\n专业：物理')
        self.assertEqual(result, (1, 1, []))
        self.assertEqual(calls[0].args[1]['school'], '甲大学')
        self.assertEqual(calls[0].args[1]['major'], '物理')
        self.assertEqual(len(bots), 5)

    def test_unknown_degree_completion_only_changes_education_payload(self):
        cleaned = ('教育经历\n时间：2014-09 - 2018-06\n学历：本科\n'
                   '专业：计算机科学与技术\n大学名称：江南大学')
        baseline, before_calls, before_bots, before_manager = self._run_first_contact(
            education=[{'school': '江南大学', 'degree': '本科', 'major': '计算机科学与技术'}],
            clean_education=cleaned)
        for source in ({'school': '江南大学'}, {'school': '江南大学', 'degree': 2}):
            with self.subTest(source=source):
                result, calls, bots, manager = self._run_first_contact(
                    education=[source], clean_education=cleaned)
                self.assertEqual(result, baseline)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0].args, before_calls[0].args)
                self.assertEqual(calls[0].args[1]['major'], '计算机科学与技术')
                self.assertEqual([bot_id for _, bot_id in bots],
                                 [bot_id for _, bot_id in before_bots])
                self.assertEqual(manager.pid_candidate_contacted_sets,
                                 before_manager.pid_candidate_contacted_sets)
                self.assertEqual(manager.candidates, before_manager.candidates)
                self.assertEqual(manager.intent_uploaded_keys, before_manager.intent_uploaded_keys)

    def test_imba_clean_resume_upload_matches_complete_structured_education(self):
        cleaned = ('教育经历\n时间：2015-09 - 2017-06\n学历：硕士\n专业：IMBA\n'
                   '大学名称：复旦大学\n---\n时间：2005-01 - 2009-01\n学历：本科\n'
                   '专业：信息管理与信息系统\n大学名称：中国地质大学（北京）')
        baseline, expected_calls, expected_bots, expected_manager = self._run_first_contact(
            education=[{'school': '复旦大学', 'degree': '硕士', 'major': 'IMBA'}],
            clean_education=cleaned)
        for education in ([], [{'school': '复旦大学', 'degree': '硕士'}]):
            with self.subTest(education=education):
                result, calls, bots, manager = self._run_first_contact(
                    education=education, clean_education=cleaned)
                self.assertEqual(result, baseline)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0].args[1]['school'], '复旦大学')
                self.assertEqual(calls[0].args[1]['major'], 'IMBA')
                self.assertEqual(calls[0].args, expected_calls[0].args)
                self.assertEqual([bot_id for _, bot_id in bots],
                                 [bot_id for _, bot_id in expected_bots])
                self.assertEqual(manager.pid_candidate_contacted_sets,
                                 expected_manager.pid_candidate_contacted_sets)

    def test_card_education_comes_from_exact_uploaded_resume_not_raw_school_spelling(self):
        cleaned = ('教育经历\n时间：2011-09 - 2015-06\n学历：本科\n'
                   '专业：空间设计\n大学名称：台湾崐山大学')
        result, calls, bots, _ = self._run_first_contact(
            education=[{'school': '台湾崑山大學', 'degree': '本科'}],
            clean_education=cleaned)
        self.assertEqual(result, (1, 1, []))
        self.assertEqual(calls[0].args[1]['school'], '台湾崐山大学')
        self.assertEqual(calls[0].args[1]['major'], '空间设计')
        self.assertTrue(calls[0].args[1]['resume_content'].startswith(cleaned))
        self.assertEqual(len(bots), 5)

    def test_upload_diagnostics_match_actual_sent_education_fields(self):
        cleaned = '教育经历\n专业：IMBA\n大学名称：复旦大学\n学历：硕士'
        result, calls, bots, manager = self._run_first_contact(clean_education=cleaned)
        self.assertEqual(result, (1, 1, []))
        self.assertEqual(calls[0].args[1]['school'], '复旦大学')
        self.assertEqual(calls[0].args[1]['major'], 'IMBA')
        events = [json.loads(call.args[0].removeprefix('高潜教育诊断 '))
                  for call in manager.logger.write_line.call_args_list
                  if call.args[0].startswith('高潜教育诊断 ')]
        self.assertEqual([event['stage'] for event in events], ['upload_request', 'upload_response'])
        for event in events:
            self.assertEqual(event['school'], calls[0].args[1]['school'])
            self.assertEqual(event['major'], calls[0].args[1]['major'])
            self.assertEqual(event['source'], 'uploaded_resume')
        self.assertEqual(events[1]['http_status'], 200)
        self.assertEqual(len(bots), 5)

    def test_uploaded_resume_highest_degree_wins_over_lower_raw_summary(self):
        cleaned = ('教育经历\n学历：硕士\n专业：IMBA\n大学名称：复旦大学\n---\n'
                   '学历：本科\n专业：信息管理与信息系统\n大学名称：中国地质大学（北京）')
        result, calls, _, _ = self._run_first_contact(
            education=[{'school': '中国地质大学（北京）', 'degree': '本科', 'major': '信息管理与信息系统'}],
            clean_education=cleaned)
        self.assertEqual(result, (1, 1, []))
        self.assertEqual(calls[0].args[1]['school'], '复旦大学')
        self.assertEqual(calls[0].args[1]['major'], 'IMBA')

    def test_incomplete_uploaded_education_does_not_mix_in_raw_degree_major(self):
        result, calls, _, _ = self._run_first_contact(
            education=[{'school': '复旦大学', 'degree': '本科', 'major': '软件工程'}],
            clean_education='教育经历\n学历：硕士\n大学名称：复旦大学')
        self.assertEqual(result, (1, 1, []))
        self.assertEqual(calls[0].args[1]['school'], '复旦大学')
        self.assertEqual(calls[0].args[1]['major'], '')

    def test_clean_resume_fallback_and_client_comment_are_preserved(self):
        result, calls, _, _ = self._run_first_contact(
            client=True, clean_education='## 教育经历\n复旦大学\n本科，软件工程')
        self.assertEqual(result, (1, 1, []))
        self.assertEqual(calls[0].args[1]['school'], '复旦大学')
        self.assertEqual(calls[0].args[1]['major'], '软件工程')
        self.assertEqual(calls[0].args[1]['comment'], '非常匹配，工程经验丰富')

    def test_nonmatching_candidate_does_not_stop_next_upload(self):
        result, calls, _, manager = self._run_first_contact(comments=[
            '否，不合理，判断结果应为不匹配，经验不足', '是，判断合理，确实匹配，经验符合'])
        self.assertEqual(result, (2, 2, []))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[1]['liepin_keywords'], '102')
        self.assertEqual(manager.pid_candidate_contacted_sets['8561'], {101, 102})

    def test_duplicate_client_remains_skipped(self):
        result, calls, bots, _ = self._run_first_contact(client=True, duplicate=True)
        self.assertEqual(result, (1, 1, []))
        self.assertEqual(calls, [])
        self.assertEqual(len(bots), 1)

    def test_duplicate_hunter_keeps_existing_duplicate_comment(self):
        result, calls, _, _ = self._run_first_contact(duplicate=True)
        self.assertEqual(result, (1, 1, []))
        self.assertEqual(calls[0].args[1]['comment'],
                         '重复：其他岗位，是，判断合理，确实非常匹配，经验符合')

    def test_malformed_ai_response_does_not_upload_unchecked_candidate(self):
        result, calls, _, _ = self._run_first_contact(malformed_first=True)
        self.assertEqual(result[:2], (1, 1))
        self.assertEqual(len(result[2]), 1)
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
