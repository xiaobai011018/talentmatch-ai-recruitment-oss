import unittest
from unittest.mock import patch

from backend.entity.candidate import Candidate


class CandidateDuplicateScreeningPreservationTest(unittest.TestCase):
    @staticmethod
    def _existing_candidate():
        candidate = Candidate(
            name='唐女士',
            currentCompany='测试公司',
            currentPosition='品牌经理',
            schoolName='测试大学',
            major='测试专业',
            rawResume='{}',
            salary='',
            position_id='8588',
            incharge_id='4784',
            now_region='',
        )
        candidate.is_duplicate_with_current_position = True
        candidate.resume_id = 123
        return candidate

    def test_existing_screening_is_not_reassessed_before_first_chat(self):
        candidate = self._existing_candidate()

        with patch.object(candidate, 'check_is_clients'), \
                patch.object(candidate, 'check_screening_is_duplicate_with_resume_code'), \
                patch.object(candidate, 'set_fact_check') as set_fact_check, \
                patch('backend.entity.candidate.chatBot.send') as bot_send, \
                patch('backend.entity.candidate.update_screening_resume') as update_screening:
            result = candidate.evaluate_before_first_chat()

        self.assertEqual(result, 'skipped_duplicate')
        set_fact_check.assert_not_called()
        bot_send.assert_not_called()
        update_screening.assert_not_called()

    def test_existing_screening_is_not_reassessed_during_screening_upload(self):
        candidate = self._existing_candidate()

        with patch.object(candidate, 'check_is_clients'), \
                patch.object(candidate, 'check_screening_is_duplicate_with_resume_code'), \
                patch.object(candidate, 'set_fact_check') as set_fact_check, \
                patch('backend.entity.candidate.chatBot.send') as bot_send, \
                patch('backend.entity.candidate.update_screening_resume') as update_screening:
            result = candidate.upload_screening_resume_to_anyJob()

        self.assertEqual(result, 'skipped_duplicate')
        set_fact_check.assert_not_called()
        bot_send.assert_not_called()
        update_screening.assert_not_called()

    def test_new_candidate_is_still_assessed_before_first_chat(self):
        candidate = self._existing_candidate()
        candidate.is_duplicate_with_current_position = False

        def mark_as_matching():
            candidate.fact_check_comment_label = '匹配'

        with patch.object(candidate, 'check_is_clients'), \
                patch.object(candidate, 'check_screening_is_duplicate_with_resume_code'), \
                patch.object(candidate, 'set_fact_check', side_effect=mark_as_matching) as set_fact_check:
            result = candidate.evaluate_before_first_chat()

        self.assertEqual(result, 'passed')
        set_fact_check.assert_called_once_with()

    def test_new_mismatching_candidate_is_still_skipped_before_first_chat(self):
        candidate = self._existing_candidate()
        candidate.is_duplicate_with_current_position = False

        def mark_as_mismatching():
            candidate.fact_check_comment_label = '不匹配'

        with patch.object(candidate, 'check_is_clients'), \
                patch.object(candidate, 'check_screening_is_duplicate_with_resume_code'), \
                patch.object(candidate, 'set_fact_check', side_effect=mark_as_mismatching) as set_fact_check:
            result = candidate.evaluate_before_first_chat()

        self.assertEqual(result, 'skipped_mismatch')
        set_fact_check.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
