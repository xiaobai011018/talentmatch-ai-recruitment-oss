import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.manger import Manger
from backend.utils.msg.history_msg import get_clean_history_msg, get_wx_and_phone


class StopAfterHistoryLookup(Exception):
    pass


class SecondConversationUserProxyReuseTest(unittest.TestCase):
    @staticmethod
    def _session_response():
        return SimpleNamespace(text=json.dumps({
            'data': {
                'list': [{
                    'unReadCnt': 0,
                    'oppositeImId': 'candidate-im-id',
                    'name': '测试候选人',
                }]
            }
        }))

    @staticmethod
    def _set_cookies(manger, _cookies_path):
        manger.current_cookies = [{'name': 'cookie', 'value': 'value'}]

    def test_all_jobs_filter_reuses_main_user_proxy(self):
        proxy = Mock()
        proxy.search_condition_session_list.return_value = self._session_response()

        def set_job_list(manger):
            manger.current_job_list = [{
                'jobName': '测试职位',
                'jobId': 'job-id',
                'jobKind': 'job-kind',
            }]

        with (
            patch.object(Manger, 'set_cookies', self._set_cookies),
            patch.object(Manger, 'set_job_list', set_job_list),
            patch.object(Manger, 'second_conversation_session_list') as process_sessions,
            patch('backend.manger.RegexUtils.get_position_id', return_value='position-id'),
            patch('backend.manger.lp.UserProxy', return_value=proxy),
            patch('backend.manger.get_clean_history_msg', return_value=([], [], [])) as clean_history,
            patch('backend.manger.get_wx_and_phone', return_value=('', '')) as contact_info,
        ):
            manger = Manger()
            manger.second_conversation('cookies.json', 'all')

        clean_history.assert_called_once_with(
            manger.current_cookies,
            'candidate-im-id',
            lp_api=proxy,
        )
        contact_info.assert_called_once_with(
            manger.current_cookies,
            'candidate-im-id',
            lp_api=proxy,
        )
        process_sessions.assert_called_once_with(proxy, 'position-id')

    def test_single_job_filter_reuses_main_user_proxy(self):
        proxy = Mock()
        proxy.search_condition_session_list.return_value = self._session_response()

        def check_and_set_job(manger, _position_id):
            manger.current_job_id = 'job-id'
            manger.current_job_kind = 'job-kind'
            return True

        with (
            patch.object(Manger, 'set_cookies', self._set_cookies),
            patch.object(Manger, 'set_job_list'),
            patch.object(Manger, 'check_and_set_job', check_and_set_job),
            patch.object(Manger, 'second_conversation_session_list') as process_sessions,
            patch('backend.manger.lp.UserProxy', return_value=proxy),
            patch('backend.manger.get_clean_history_msg', return_value=([], [], [])) as clean_history,
            patch('backend.manger.get_wx_and_phone', return_value=('', '')) as contact_info,
        ):
            manger = Manger()
            manger.second_conversation('cookies.json', 'single', 'position-id')

        clean_history.assert_called_once_with(
            manger.current_cookies,
            'candidate-im-id',
            lp_api=proxy,
        )
        contact_info.assert_called_once_with(
            manger.current_cookies,
            'candidate-im-id',
            lp_api=proxy,
        )
        process_sessions.assert_called_once_with(proxy, 'position-id')

    def test_processing_reuses_passed_user_proxy_for_history(self):
        proxy = Mock()
        manger = Manger()
        manger.current_cookies = [{'name': 'cookie', 'value': 'value'}]
        manger.current_session_list = [{'oppositeImId': 'candidate-im-id'}]

        with (
            patch.object(Manger, '_get_session_encode_res_id', return_value='resume-id'),
            patch('backend.manger.h5_ai_update_status'),
            patch('backend.manger.get_job_data', return_value={}),
            patch('backend.manger.get_ah_result_dict', return_value={
                'results': [{
                    'summary': '深匹要求：测试要求',
                    'name_summary': '【公司信息】测试公司',
                }]
            }),
            patch(
                'backend.manger.get_clean_history_msg',
                side_effect=StopAfterHistoryLookup,
            ) as clean_history,
        ):
            with self.assertRaises(StopAfterHistoryLookup):
                manger.second_conversation_session_list(proxy, 'position-id')

        clean_history.assert_called_once_with(
            manger.current_cookies,
            'candidate-im-id',
            lp_api=proxy,
        )

    def test_history_helpers_do_not_create_proxy_when_one_is_supplied(self):
        response = Mock()
        response.json.return_value = {'data': {'list': []}}
        proxy = Mock()
        proxy.get_chat_his.return_value = response

        with patch(
            'backend.utils.msg.history_msg.lp.UserProxy',
            side_effect=AssertionError('unexpected fallback UserProxy'),
        ):
            self.assertEqual(
                get_clean_history_msg([], 'candidate-im-id', lp_api=proxy),
                ([], [], []),
            )
            self.assertEqual(
                get_wx_and_phone([], 'candidate-im-id', lp_api=proxy),
                ('', ''),
            )


if __name__ == '__main__':
    unittest.main()
