import json
import time
import uuid

import requests

from backend.core.config.httpRetryConfig import HTTP_RETRY_TIMES, HTTP_RETRY_GAP
from backend.core.config.zhilian_api_config import GET_CANDIDATE_LIST, GET_RESUME, CREATE_GREET, GET_JOB_LIST, \
    GET_SESSION_LIST, GET_SESSION_DETAIL, SESSION_LABEL_MAP, SET_MSG_READ, SEND_MSG, SEND_ASK_WX_MSG, \
    SEND_ASK_PHONE_MSG, GET_USER_INFO, GET_VIRTUAL_NUMBER
from backend.core.logger.logger import get_logger
from backend.core.utils.decorator.http_retry import http_retry
from backend.core.utils.msg.dump_im_html import maybe_dump_im_session_html
from backend.core.utils.resume.diagnostics import (
    log_resume_diagnostic,
    stable_data_sha256,
    summarize_education_experiences,
)

logger = get_logger(__name__)


def _first_dict(items):
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return items[0]
    return {}


def _log_candidate_list_response(response, page_no, page_size):
    try:
        response_body = response.json()
    except Exception:
        log_resume_diagnostic(
            logger,
            "zhilian_candidate_list_response",
            page_no=page_no,
            page_size=page_size,
            status_code=getattr(response, "status_code", None),
            response_json=False,
        )
        return

    data = response_body.get("data") if isinstance(response_body, dict) else None
    candidate_list = data.get("list") if isinstance(data, dict) else None
    if not isinstance(candidate_list, list):
        log_resume_diagnostic(
            logger,
            "zhilian_candidate_list_response",
            page_no=page_no,
            page_size=page_size,
            status_code=getattr(response, "status_code", None),
            response_json=True,
            candidate_count=0,
        )
        return

    for candidate in candidate_list:
        if not isinstance(candidate, dict):
            continue
        work_experiences = candidate.get("workExperiences") or []
        first_work = _first_dict(work_experiences)
        log_resume_diagnostic(
            logger,
            "zhilian_candidate_list_item",
            page_no=page_no,
            page_size=page_size,
            status_code=getattr(response, "status_code", None),
            candidate_sha256=stable_data_sha256(candidate),
            user_id=candidate.get("userMasterId"),
            resume_number=candidate.get("resumeNumber"),
            resume_language=candidate.get("resumeLanguage"),
            resume_version=candidate.get("resumeVersion"),
            resume_k_sha256=stable_data_sha256(str(candidate.get("resumeK", ""))),
            resume_t=candidate.get("resumeT"),
            education_experiences=summarize_education_experiences(
                candidate.get("educationExperiences") or []
            ),
            first_work={
                "company": first_work.get("companyName", first_work.get("orgName", "")),
                "position": first_work.get("jobTitle", ""),
            },
        )


def _log_resume_response(response, request_context):
    fields = {
        **request_context,
        "status_code": getattr(response, "status_code", None),
    }
    try:
        response_body = response.json()
    except Exception:
        fields["response_json"] = False
        log_resume_diagnostic(logger, "zhilian_resume_response", **fields)
        return

    data = response_body.get("data") if isinstance(response_body, dict) else None
    if not isinstance(data, dict):
        fields.update({
            "response_json": True,
            "response_code": response_body.get("code") if isinstance(response_body, dict) else None,
            "has_resume_data": False,
        })
        log_resume_diagnostic(logger, "zhilian_resume_response", **fields)
        return

    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    resume = data.get("resume") if isinstance(data.get("resume"), dict) else {}
    work_experiences = resume.get("workExperiences") or []
    purposes = resume.get("purposes") or []
    first_work = _first_dict(work_experiences)
    first_purpose = _first_dict(purposes)
    fields.update({
        "response_json": True,
        "response_code": response_body.get("code"),
        "has_resume_data": True,
        "data_sha256": stable_data_sha256(data),
        "user_id": user.get("id"),
        "resume_id": resume.get("id"),
        "education_experiences": summarize_education_experiences(
            resume.get("educationExperiences") or []
        ),
        "first_work": {
            "company": first_work.get("orgName", ""),
            "position": first_work.get("jobTitle", ""),
        },
        "first_purpose": {
            "salary": first_purpose.get("salaryLabel", ""),
            "location": first_purpose.get("location", ""),
        },
    })
    log_resume_diagnostic(logger, "zhilian_resume_response", **fields)

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def get_candidate_list(cookies, page_no, page_size, **kwargs):
    url = GET_CANDIDATE_LIST
    payload = {
        "filteringChatted": True,
        "filteringRead": False,
        "filteringDownloaded": False,
        "sort": {"type": "COMPLEX", "version": 17},
        "pageNo": page_no,
        "pageSize": page_size,
        "filteringOtherChattedType": "DONT_FILTER",
        "matchLatestWorkExperience": False,
        "searchExperimentalGroup": "EXPERIMENT",
        "frontExperiment": True,
        "firstPageCacheable": False,
        "freeMaskLimit": False,
        "experiment": ""
    }
    payload.update(kwargs)
    response = requests.post(url, cookies=cookies, json=payload)
    _log_candidate_list_response(response, page_no, page_size)
    return response

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def get_resume(cookies, resume_number, resume_K, resume_T, purpose_id, resume_language="1"):
    url = GET_RESUME
    payload = {
        "resumeNumber": resume_number,
        "resumeLanguage": resume_language,
        "k": resume_K,
        "t": resume_T,
        "skipRead": False,
        "sourceId": "null",
        "sourceType": None,
        "isOperator": "rd",
        "condition": {
            "analyseWords": [],
            "intentResults": "[]"
        },
        "enterScene": "",
        "cardData": {
            "purposeId": purpose_id
        },
        "isCampusWidget": False,
        "isPreFetch": False
    }

    request_context = {
        "request_scene": "talent_search",
        "resume_number": resume_number,
        "resume_language": resume_language,
        "resume_k_sha256": stable_data_sha256(str(resume_K)),
        "resume_t": resume_T,
        "purpose_id": purpose_id,
    }
    log_resume_diagnostic(logger, "zhilian_resume_request", **request_context)
    response = requests.post(url, cookies=cookies, json=payload)
    _log_resume_response(response, request_context)
    return response

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def get_session_resume(cookies, job_number, resume_number, resume_language):
    url = GET_RESUME

    payload = {
        "jobNumber": job_number,
        "resumeNumber": resume_number,
        "resumeLanguage": resume_language,
        "k": "",
        "t": "",
        "skipRead": False,
        "isOperator": "rd",
        "enterScene": "IM_SESSION_DETAIL",
        "isCampusWidget": False,
        "isPreFetch": False
    }

    request_context = {
        "request_scene": "im_session_detail",
        "resume_number": resume_number,
        "resume_language": resume_language,
        "job_number": job_number,
    }
    log_resume_diagnostic(logger, "zhilian_resume_request", **request_context)
    response = requests.post(url, cookies=cookies, json=payload)
    _log_resume_response(response, request_context)
    return response


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_virtual_number(cookies, job_number, resume_number, resume_language):
    """获取“打电话”按钮已开放时对应的候选人号码。"""
    payload = {
        "jobNumber": job_number,
        "resumeNumber": resume_number,
        "resumeLanguage": resume_language,
        "isCampusWidget": False,
    }
    return requests.post(GET_VIRTUAL_NUMBER, cookies=cookies, json=payload)


@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def get_job_list(cookies, page_no=1, page_size=6):
    url = GET_JOB_LIST

    payload = {
        "includingDetail": False,
        "includingHotJob": True,
        "states": ["RELEASED"],
        "pageNo": page_no,
        "pageSize": page_size
    }

    return requests.post(url, cookies=cookies, json=payload)

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def create_greet(cookies, job_number, resume_number, resume_language, resume_version):
    url = CREATE_GREET

    payload = {
        "productGroups": [
            {
                "productType": "TALENT_SEARCH",
                "metaType": "TALENT_SEARCH",
                "executionMeta": {
                    "executionType": "IMMEDIATE"
                },
                "productMeta": '[{\"jobNumber\":\"' + job_number + '\",\"resumeNumber\":\"' + resume_number + '\",\"resumeLanguage\":' + str(
                    resume_language) + ',\"resumeVersion\":\"' + str(
                    resume_version) + '\",\"sendSystemAskForContact\":true,\"isEmergCallPerson\":\"0\",\"greetingText\":\"\",\"aiGreeting\":false}]'
            }
        ],
        "supportedAllPaymentType": False,
        "sideBusinessSubtype": "TALENT_SEARCH"
    }

    return requests.post(url, cookies=cookies, json=payload)

def _filter_items(items):
    return [
        {
            "key": key,
            "labelName": label,
            "selected": False,
            "deletable": False,
            "sortable": False,
        }
        for key, label in items
    ]


@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def get_session_list(
        cookies,
        page_no,
        page_size,
        filter_top,
        active_session_id='',
        is_unread=False,
        job_number=None,
        initiated_by_me=False,
):
    url = GET_SESSION_LIST

    if initiated_by_me:
        message_type_items = _filter_items([
            ("MESSAGE_TYPE_ALL", "不限"),
            ("MESSAGE_TYPE_INITIATED_BY_ME", "我发起"),
            ("MESSAGE_TYPE_INITIATED_BY_TALENT", "人才发起"),
            ("MESSAGE_TYPE_COLLEAGUE", "同事聊天"),
            ("MESSAGE_TYPE_MY_PUBLISHED", "我发布的职位"),
            ("MESSAGE_TYPE_ONLY_DELIVERY", "有投递会话"),
            ("MESSAGE_TYPE_ONLY_CHAT", "仅聊天会话"),
            ("MESSAGE_TYPE_USER_ACTIVE_CALL", "求职者主动来电"),
        ])
        payload = {
            "pageNo": page_no,
            "pageSize": page_size,
            "sessionType": None,
            "filterMore": [
                {
                    "extra": None,
                    "groupCode": "MESSAGE_TYPE",
                    "groupName": "消息类型",
                    "selectionType": "RADIO",
                    "trackingEventType": "",
                    "items": message_type_items,
                    "selectedValue": "MESSAGE_TYPE_INITIATED_BY_ME",
                    "selectedValues": [],
                },
                {
                    "extra": None,
                    "groupCode": "CONTACT",
                    "groupName": "联系方式",
                    "selectionType": "CHECKBOX",
                    "trackingEventType": "",
                    "items": _filter_items([
                        ("CONTACT_ALL", "不限"),
                        ("CONTACT_WECHAT", "已获取微信"),
                        ("CONTACT_PHONE", "已获取电话"),
                    ]),
                    "selectedValue": None,
                    "selectedValues": [],
                },
                {
                    "extra": None,
                    "groupCode": "MESSAGE_TIME",
                    "groupName": "消息时间",
                    "selectionType": "RADIO",
                    "trackingEventType": "",
                    "items": _filter_items([
                        ("MESSAGE_TIME_ALL", "不限"),
                        ("MESSAGE_TIME_TODAY", "今天"),
                        ("MESSAGE_TIME_LAST_3_DAYS", "最近3天"),
                        ("MESSAGE_TIME_LAST_7_DAYS", "最近7天"),
                        ("MESSAGE_TIME_LAST_30_DAYS", "最近30天"),
                        ("MESSAGE_TIME_OVER_30_DAYS", "超过30天"),
                    ]),
                    "selectedValue": None,
                    "selectedValues": [],
                },
            ],
            "aiHostingStates": [],
            "isServer": False,
            "groupSelectorVal": "",
            "singleVisionDirectRecommend": None,
            "componentFilter": json.dumps(
                {
                    "filterGroups": [
                        {
                            "extra": None,
                            "groupCode": "MESSAGE_TYPE",
                            "groupName": "消息类型",
                            "selectionType": "RADIO",
                            "trackingEventType": "",
                            "items": _filter_items([
                                ("MESSAGE_TYPE_INITIATED_BY_ME", "我发起"),
                            ]),
                            "selectedValues": [],
                        }
                    ]
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "includeResume": True,
        }
    else:
        payload = {
            "pageNo": page_no,
            "pageSize": page_size,
            "activeSessionId": active_session_id,
            "sessionType": None,
            "filterTop": "all",
            "aiHostingStates": [],
            "isServer": False,
            "groupSelectorVal": "",
            "singleVisionDirectRecommend": None,
            "componentFilter": "",
            "includeResume": True
        }
        if not filter_top == 'all':
            payload['filterTop'] = filter_top
            payload['componentFilter'] = (
                    '{\"filterGroups\":[{\"extra\":null,\"groupCode\":\"DEFAULT\",\"groupName\":\"\",\"selectionType\":\"RADIO\",\"trackingEventType\":\"\",\"items\":[{\"key\":\"' + filter_top + '\",\"labelName\":\"' +
                    SESSION_LABEL_MAP[filter_top] + '\",\"selected\":false,\"deletable\":false,\"sortable\":true}]}]}')
    if job_number:
        payload['jobNumber'] = job_number
    if is_unread:
        payload['userIds'] = []
        payload['withUnread'] = True

    return requests.post(url, cookies=cookies, json=payload)

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def get_session_html(cookies, session_id):
    url = f'https://rd6.zhaopin.com/app/im?sessionId={session_id}'

    response = requests.get(url, cookies=cookies)
    maybe_dump_im_session_html(session_id, response.text)
    return response

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def get_session_detail(cookies, session_id, mark_read=False, include_resume_detail=False):
    url = GET_SESSION_DETAIL

    payload = {
        "sessionId": session_id,
        "isCampusWidget": False,
        "markRead": mark_read,
        "includeResumeDetail": include_resume_detail
    }

    return requests.post(url, cookies=cookies, json=payload)

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def set_msg_read(cookies, candidate_id):
    url = SET_MSG_READ

    payload = {
        "targetChannelId": candidate_id,
        "targetChannelType": "P2P",
        "ignoreSessionNotExistException": False
    }

    return requests.post(url, cookies=cookies, json=payload)

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def send_msg(cookies, content, session_id):
    url = SEND_MSG

    payload = {
        "content": content,
        "sessionId": session_id,
        "sendMessageId": uuid.uuid4().hex
    }

    return requests.post(url,cookies=cookies, json=payload)

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def send_ask_wx_msg(cookies, session_id,we_chat = 'AnyHelper_CW'):
    url = SEND_ASK_WX_MSG

    payload = {
        "sessionId": session_id,
        "weChat": we_chat
    }

    return requests.post(url,cookies=cookies,json=payload)

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def send_sak_phone_msg(cookies,session_id):
    url = SEND_ASK_PHONE_MSG

    payload = {
        "sessionId": session_id
    }

    return requests.post(url,cookies=cookies,json=payload)


# Manual demo removed from repository import; use synthetic fixtures for local testing.
