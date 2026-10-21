import unittest
from unittest.mock import Mock, patch

from backend.entity.candidate import Candidate


class CandidateChatTagSelectionTest(unittest.TestCase):
    def test_rule_tag_wins_when_model_only_claims_interest(self):
        self.assertEqual(
            Candidate._select_single_chat_tag('未读消息', '有意向沟通'),
            '未读消息',
        )
        self.assertEqual(
            Candidate._select_single_chat_tag('已读不回', '有意向沟通'),
            '已读不回',
        )

    def test_rule_tag_wins_when_model_claims_negative_intent(self):
        self.assertEqual(
            Candidate._select_single_chat_tag('有意向沟通', '薪资不符合'),
            '有意向沟通',
        )
        self.assertEqual(
            Candidate._select_single_chat_tag('未读消息', '岗位不匹配'),
            '未读消息',
        )

    def test_model_tag_is_used_when_rule_tag_is_empty(self):
        self.assertEqual(
            Candidate._select_single_chat_tag('', '有意向沟通'),
            '有意向沟通',
        )

    def test_default_tag_when_no_valid_tag_exists(self):
        self.assertEqual(
            Candidate._select_single_chat_tag('', ''),
            '被联系过了',
        )

    @staticmethod
    def _candidate_for_sync():
        candidate = Candidate(
            name='张先生',
            currentCompany='测试公司',
            currentPosition='测试岗位',
            schoolName='测试大学',
            major='测试专业',
            rawResume='{}',
            salary='',
            position_id='7369',
            incharge_id='4784',
            now_region='',
        )
        candidate.is_duplicate_with_current_position = True
        candidate.resume_id = 123
        return candidate

    def test_rule_tag_skips_model_call_when_syncing_high_potential(self):
        candidate = self._candidate_for_sync()
        response = Mock(status_code=200)
        response.json.return_value = {'code': 200}

        with patch.object(candidate, 'check_screening_is_duplicate_with_resume_code'), \
                patch('backend.entity.candidate.chatBot.send') as bot_send, \
                patch('backend.entity.candidate.update_screening_resume', return_value=response) as update_resume:
            self.assertTrue(candidate.sync_high_potential_by_smart_keywords(
                chat_history='AI招聘官：您好',
                rule_tag='未读消息',
            ))

        bot_send.assert_not_called()
        update_resume.assert_called_once_with(
            123,
            chat_history='AI招聘官：您好',
            chat_tags='未读消息',
        )

    def test_empty_rule_tag_calls_model_when_syncing_high_potential(self):
        candidate = self._candidate_for_sync()
        response = Mock(status_code=200)
        response.json.return_value = {'code': 200}

        with patch.object(candidate, 'check_screening_is_duplicate_with_resume_code'), \
                patch('backend.entity.candidate.chatBot.send', return_value='岗位不匹配') as bot_send, \
                patch('backend.entity.candidate.update_screening_resume', return_value=response) as update_resume:
            self.assertTrue(candidate.sync_high_potential_by_smart_keywords(
                chat_history='候选人：不太匹配',
                rule_tag='',
            ))

        bot_send.assert_called_once()
        update_resume.assert_called_once_with(
            123,
            chat_history='候选人：不太匹配',
            chat_tags='岗位不匹配',
        )


if __name__ == '__main__':
    unittest.main()
