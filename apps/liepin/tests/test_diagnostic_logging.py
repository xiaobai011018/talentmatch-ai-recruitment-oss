import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import ANY, Mock, patch

import pandas as pd

from backend.api.anyJobApi import add_screening_resume, summarize_anyjob_response
from backend.entity.candidate import Candidate
from backend.manger import Manger


class DiagnosticLoggingTest(unittest.TestCase):
    @staticmethod
    def _response(payload, status_code=200):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = payload
        return response

    def test_anyjob_response_summary_extracts_diagnostic_fields(self):
        response = self._response({
            'code': 0,
            'message': '成功',
            'data': {
                'screening_id': 251234,
                'results': [{'id': 1}],
            },
        })

        summary = summarize_anyjob_response(response)

        self.assertEqual(summary['http_status'], 200)
        self.assertEqual(summary['code'], 0)
        self.assertEqual(summary['message'], '成功')
        self.assertEqual(summary['results_count'], 1)
        self.assertEqual(summary['screening_id'], 251234)

    @patch('backend.api.anyJobApi.requests.post')
    def test_trace_id_is_logged_but_not_sent_as_business_payload(self, post):
        response = self._response({'code': 0, 'data': {'screening_id': 251234}})
        post.return_value = response

        result = add_screening_resume(
            position_id=8605,
            incharge_id=8190,
            trace_id='run-r1-c1',
            name='张先生',
        )

        self.assertIs(result, response)
        sent_payload = post.call_args.args[1]
        self.assertEqual(sent_payload['position_id'], 8605)
        self.assertEqual(sent_payload['incharge_id'], 8190)
        self.assertNotIn('trace_id', sent_payload)

    def test_screening_upload_propagates_trace_id_without_changing_result(self):
        candidate = Candidate(
            name='张先生',
            currentCompany='测试公司',
            currentPosition='财务总监',
            schoolName='测试大学',
            major='会计学',
            rawResume='{}',
            salary='',
            position_id=8605,
            incharge_id=8190,
            now_region='',
        )
        candidate.diagnostic_trace_id = 'run-r1-c1'

        h5_response = self._response({'code': 0, 'message': '成功'})
        upload_response = self._response({'code': 0, 'data': {'screening_id': 251234}})

        with patch.object(candidate, 'check_is_clients'), \
                patch.object(candidate, 'check_screening_is_duplicate_with_resume_code'), \
                patch.object(candidate, 'set_fact_check') as fact_check, \
                patch.object(candidate, '_build_screening_comment', return_value='匹配'), \
                patch.object(candidate, '_build_screening_resume_payload', return_value={'name': '张先生'}), \
                patch('backend.entity.candidate.chatBot.send', return_value='清洗后简历') as bot_send, \
                patch('backend.entity.candidate.h5_post', return_value=h5_response) as h5_post, \
                patch('backend.entity.candidate.add_screening_resume', return_value=upload_response) as upload:
            fact_check.side_effect = lambda: setattr(candidate, 'fact_check_comment_label', '匹配')
            result = candidate.upload_screening_resume_to_anyJob()

        self.assertEqual(result, 'uploaded')
        bot_send.assert_called_once_with(
            '{}',
            ANY,
            trace_id='run-r1-c1',
        )
        self.assertEqual(h5_post.call_args.kwargs['trace_id'], 'run-r1-c1')
        self.assertEqual(upload.call_args.kwargs['trace_id'], 'run-r1-c1')

    def test_excel_status_save_writes_existing_is_chat_column(self):
        df = pd.DataFrame({'name': ['张先生'], 'is_chat': [None]})

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'result.xlsx'
            Manger._save_excel_chat_status(
                df,
                str(output_path),
                row=0,
                status=1,
                run_id='run1',
                trace_id='run1-r0',
            )
            saved = pd.read_excel(output_path)

        self.assertEqual(list(saved.columns), ['name', 'is_chat'])
        self.assertEqual(saved.at[0, 'is_chat'], 1)


if __name__ == '__main__':
    unittest.main()
