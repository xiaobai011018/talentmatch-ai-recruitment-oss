# -*- coding: utf-8 -*-
"""校验上传高潜 payload 中年龄/薪资字段来源（不调用外部 API）。"""
from backend.core.config.chatBotApiConfig import ENUM_MODEL_ID
import backend.core.entity.candidate as candidate_module
from backend.core.entity.candidate import Candidate


def _raw_resume():
    return {
        "user": {
            "name": "张三",
            "age": 39,
            "ageLabel": "39岁",
            "userActiveTag": None,
            "lastActiveTime": 1760922015220,
            "gender": 1,
            "genderLabel": "男",
            "email": "",
            "birthYear": 1986,
            "birthMonth": 2,
            "birthYearMonthLabel": "1986年2月",
            "nationality": 489,
            "careerState": 1,
            "careerStateLabel": "在职-正在找工作",
            "maxEducation": 4,
            "maxEducationLabel": "本科",
            "yearStartWorking": 2009,
            "monthStartWorking": 7,
            "workYears": 17,
            "workMonths": 196,
            "workYearsLabel": "16年",
            "cityId": 538,
            "cityLabel": "现居上海",
            "cityName": "上海",
            "districtName": "",
            "streetId": 0,
            "cityDistrictId": 0,
            "cityDistrictLabel": "",
        },
        "candidate": None,
        "resume": {
            "language": 1,
            "name": "张三",
            "resumeType": "TOP",
            "resumeLevel": "WHITE",
            "educationExperienceTitle": "教育经历",
            "educationExperiences": [
                {"schoolName": "复旦大学", "major": "计算机", "education": 4, "educationLabel": "本科"}
            ],
            "workExperiences": [
                {
                    "orgName": "测试科技",
                    "orgNameHighlights": [],
                    "simpleOrgName": "测试科技",
                    "industryType": "",
                    "description": "后端开发",
                    "descriptionHighlights": [],
                    "jobTitle": "研发工程师",
                    "jobTitleHighlights": [],
                    "jobSubTitle": "",
                    "jobSubtype": "",
                    "jobSubtypeHighlight": {"name": ""},
                    "salary": "",
                    "salaryDescription": "",
                    "salaryLabel": "",
                    "beginTime": 0,
                    "endTime": 0,
                    "timeLabel": "",
                }
            ],
            "projectExperienceTitle": "项目经历",
            "projectExperienceDescriptionTitle": "项目描述",
            "projectExperiences": [],
            "languageSkillTitle": "语言能力",
            "languageSkillListeningTitle": "听说",
            "languageSkillLiteracyTitle": "读写",
            "languageSkills": [],
            "purposes": [{"salaryLabel": "25K-35K/月"}],
        },
    }


def main() -> None:
    captured = {}
    original_send = candidate_module.chatBot.send
    original_add_screening_resume = candidate_module.add_screening_resume
    original_h5_post = candidate_module.h5_post

    def fake_send(_msg, chatbot_id):
        if chatbot_id == ENUM_MODEL_ID.GET_CLEAN_SALARY.value:
            return "30"
        if chatbot_id == ENUM_MODEL_ID.GET_CLEAN_RESUME:
            return (
                "**期待薪资**：99K-120K/月\n"
                "**居住地**：上海\n"
                "**优势标签**：后端\n"
                "**推荐语**：匹配"
            )
        return ""

    def fake_add_screening_resume(**kwargs):
        captured.update(kwargs)

    try:
        candidate_module.chatBot.send = fake_send
        candidate_module.add_screening_resume = fake_add_screening_resume
        candidate_module.h5_post = lambda *args, **kwargs: None

        candidate = Candidate.from_raw_resume(_raw_resume(), "123", "834")
        assert candidate.age == 39
        assert candidate.salary == "30"

        candidate.check_is_clients = lambda: None
        candidate.check_screening_is_duplicate_with_smart_keywords = lambda: setattr(candidate, "is_duplicate_pass", False)
        candidate.set_fact_check = lambda: (
            setattr(candidate, "fact_check_comment_label", "匹配"),
            setattr(candidate, "fact_check_comment", "匹配，a，b，原因"),
        )
        candidate.set_simple_resume = lambda: setattr(candidate, "simple_resume", "简历摘要")

        candidate.upload_screening_resume_to_anyJob()

        assert captured["age"] == 39
        assert captured["salary"] == "30"
        assert captured["position_id"] == "123"
        assert captured["incharge_id"] == "834"
        print("screening payload age/salary assertions passed")
    finally:
        candidate_module.chatBot.send = original_send
        candidate_module.add_screening_resume = original_add_screening_resume
        candidate_module.h5_post = original_h5_post


if __name__ == "__main__":
    main()
