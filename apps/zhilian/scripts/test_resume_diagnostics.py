# -*- coding: utf-8 -*-
"""校验简历诊断日志可串联请求与解析，且不泄露敏感字段。"""
import json

import backend.core.api.zhilian_api as zhilian_api
import backend.core.entity.candidate as candidate_module
from backend.core.entity.candidate import Candidate
from backend.core.utils.resume.diagnostics import stable_data_sha256


def _resume_data():
    return {
        "user": {
            "id": 10001,
            "name": "李先生",
            "phone": "13800000000",
            "lastActiveTime": 1784518291547,
            "cityName": "资阳",
        },
        "resume": {
            "id": 20002,
            "educationExperiences": [
                {
                    "schoolName": "美国佩丁大学",
                    "major": "金融学",
                    "educationLabel": "MBA/EMBA",
                    "educationTimeLabel": "2020.07 - 2022.07",
                },
                {
                    "schoolName": "西南财经大学",
                    "major": "财务管理",
                    "educationLabel": "本科",
                    "educationTimeLabel": "2005.07 - 2009.06",
                },
            ],
            "workExperiences": [
                {
                    "orgName": "攀枝花钛白化工有限公司（拟上市）",
                    "jobTitle": "财务总监",
                }
            ],
            "purposes": [],
        },
    }


class _FakeResponse:
    status_code = 200

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def main() -> None:
    api_events = []
    candidate_events = []
    original_post = zhilian_api.requests.post
    original_api_log = zhilian_api.log_resume_diagnostic
    original_candidate_log = candidate_module.log_resume_diagnostic

    data = _resume_data()
    list_item = {
        "userMasterId": 10001,
        "resumeNumber": "RN-001",
        "resumeLanguage": 1,
        "resumeVersion": 3,
        "resumeK": "secret-resume-k",
        "resumeT": "1784536635591",
        "educationExperiences": [
            {
                "schoolName": "美国佩丁大学",
                "majorName": "金融学",
                "educationLevel": "MBA/EMBA",
            }
        ],
        "workExperiences": [
            {
                "companyName": "攀枝花钛白化工有限公司",
                "jobTitle": "财务总监",
            }
        ],
    }

    try:
        def fake_post(url, *_args, **_kwargs):
            if url == zhilian_api.GET_CANDIDATE_LIST:
                return _FakeResponse({
                    "code": 200,
                    "data": {"list": [list_item]},
                })
            return _FakeResponse({
                "code": 200,
                "data": data,
            })

        zhilian_api.requests.post = fake_post
        zhilian_api.log_resume_diagnostic = (
            lambda _logger, event, **fields: api_events.append({"event": event, **fields})
        )
        candidate_module.log_resume_diagnostic = (
            lambda _logger, event, **fields: candidate_events.append({"event": event, **fields})
        )

        zhilian_api.get_candidate_list(
            cookies={"secret-cookie": "must-not-be-logged"},
            page_no=1,
            page_size=20,
        )
        zhilian_api.get_resume(
            cookies={"secret-cookie": "must-not-be-logged"},
            resume_number="RN-001",
            resume_K="secret-resume-k",
            resume_T="1784536635591",
            purpose_id="purpose-001",
        )
        candidate = Candidate.from_raw_resume(data, position_id="8605", incharge_id="8190")

        assert [event["event"] for event in api_events] == [
            "zhilian_candidate_list_item",
            "zhilian_resume_request",
            "zhilian_resume_response",
        ]
        assert api_events[0]["resume_number"] == "RN-001"
        assert api_events[0]["education_experiences"][0]["school_name"] == "美国佩丁大学"
        assert api_events[2]["data_sha256"] == candidate.resume_payload_sha256
        assert api_events[2]["education_experiences"][0]["school_name"] == "美国佩丁大学"

        parsed = candidate_events[0]
        assert parsed["event"] == "candidate_resume_parsed"
        assert parsed["selected_education_index"] == 0
        assert parsed["selected_school"] == "美国佩丁大学"
        assert parsed["smart_keywords"] == (
            "李_攀枝花钛白化工有限公司(拟上市)_财务总监_美国佩丁大学_金融学"
        )
        assert parsed["data_sha256"] == stable_data_sha256(data)

        serialized_logs = json.dumps(
            {"api": api_events, "candidate": candidate_events},
            ensure_ascii=False,
        )
        assert "secret-cookie" not in serialized_logs
        assert "must-not-be-logged" not in serialized_logs
        assert "secret-resume-k" not in serialized_logs
        assert "13800000000" not in serialized_logs
        print("resume diagnostic assertions passed")
    finally:
        zhilian_api.requests.post = original_post
        zhilian_api.log_resume_diagnostic = original_api_log
        candidate_module.log_resume_diagnostic = original_candidate_log


if __name__ == "__main__":
    main()
