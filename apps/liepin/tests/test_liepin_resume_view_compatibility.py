import json
import unittest
from unittest.mock import patch

import requests

from backend.api.lp import UserProxy
from backend.config.lp import API_LP_GET_RESUME_DETAIL


class LiepinResumeViewCompatibilityTest(unittest.TestCase):
    def test_response_is_normalized_and_reuses_work_experiences(self):
        proxy = UserProxy([])
        raw_response = requests.Response()
        raw_response.status_code = 200
        raw_response._content = json.dumps({
            'flag': 1,
            'data': {
                'resumeDetailVo': {
                    'encodeResId': 'resume-id',
                    'encodeUsercId': 'user-id',
                    'lastLoginTime': '2026/07/09',
                    'baseInfo': {
                        'name': '测试候选人',
                        'title': '测试职位',
                        'dqName': '上海',
                    },
                    'workExperiences': [{'rwCompname': '测试公司'}],
                    'eduExperiences': [{
                        'redSchool': '测试大学', 'redSpecial': '计算机', 'redDegreeName': '硕士',
                    }],
                    'jobWantInfos': [{'wantSalaryShow': '30-40k'}],
                }
            }
        }, ensure_ascii=False).encode('utf-8')

        calls = []

        def fake_post(api_name, url, payload=None, expected_top_level_key=None, timeout=None):
            calls.append((api_name, url, payload))
            return raw_response

        with patch.object(proxy, '_post', side_effect=fake_post):
            detail_response = proxy.get_resume_detail('resume-id')
            detail = detail_response.json()['data']
            work_response = proxy.get_work_exp('测试职位', 'resume-id')

        self.assertTrue(API_LP_GET_RESUME_DETAIL.endswith('.pc.resume-view'))
        self.assertEqual(len(calls), 1)
        self.assertEqual(detail['showName'], '测试候选人')
        self.assertEqual(detail['basicInfoForm']['resJobtitle'], '测试职位')
        self.assertEqual(detail['basicInfoForm']['dqName'], '上海')
        self.assertEqual(detail['eduExpFormList'][0]['redSchool'], '测试大学')
        self.assertEqual(detail['eduExpFormList'][0]['redSpecial'], '计算机')
        self.assertEqual(detail['eduExpFormList'][0]['redDegreeName'], '硕士')
        self.assertEqual(detail['resExpectInfoDtos'][0]['wantSalaryShow'], '30-40k')
        self.assertEqual(detail['usercIdEncode'], 'user-id')
        self.assertEqual(work_response.json()['data'], [{'rwCompname': '测试公司'}])


if __name__ == '__main__':
    unittest.main()
