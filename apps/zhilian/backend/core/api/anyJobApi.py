"""
@describe:
@fileName: server_io.py
@time    : 2025/9/17 18:05
@author  : duke
"""
import json
import requests
from requests import Response

from backend.core.config.anyJobConfig import *
from backend.core.utils.decorator.http_retry import http_retry
from backend.core.config.httpRetryConfig import *


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def h5_post(position_id, title, content):
    url = API_H5_POST

    payload = {
        'custom_fields': '{}',
        'position_id': position_id,
        'title': title,
        'content': content,
    }

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def h5_ai_update_status(position_id, ai_process_status: ENUM_H5_AI_STATUS, ai_status=None):
    url = API_H5_AI_UPDATE_STATUS

    payload = {
        'position_id': position_id,
        'ai_process_status': ai_process_status.value,
    }

    if ai_status:
        payload['ai_status'] = ai_status

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_user_role(user_id):
    url = API_GET_USER_ROLE

    payload = {
        'user_id': user_id,
    }

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def add_screening_resume(position_id, incharge_id, status="待联系", coins_cost=2, **kwargs):
    url = API_ADD_SCREENING_RESUME

    payload = {
        'position_id': position_id,
        'incharge_id': incharge_id,
        'status': status,
        'coins_cost': coins_cost,
    }

    payload.update(kwargs)

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_search_conditions(position_id):
    url = API_GET_SEARCH_STRATEGYS

    payload = {
        'position_id': position_id,
    }

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_position_info(position_id):
    url = API_GET_POSITION_INFO

    payload = {
        'position_id': position_id,
    }

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def h5_ai_add_count(position_id, **kwargs):
    """
    :param kwargs: count_resume_reviews, count_conversation, count_replies, count_resume_uploads
    :return:
    """
    url = API_H5_AI_ADD_COUNT

    payload = {
        'position_id': position_id,
    }

    payload.update(kwargs)

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def duplicate(user_id, position_id=None, phone=None, vx=None, smart_keywords=None):
    url = API_DUPLICATE
    payload = {
        'user_id': user_id
    }

    if position_id:
        payload['position_id'] = position_id
    if phone:
        payload['phone'] = phone
    if vx:
        payload['weixin'] = vx
    if smart_keywords:
        payload['smart_keywords'] = smart_keywords

    return requests.post(url, payload)

@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def duplicate_smart_code(user_id, smart_code, position_id=None):
    return duplicate(user_id=user_id, position_id=position_id, smart_keywords=smart_code)

@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def duplicate_screening(user_id, liepin_keywords=None, data_id=None, position_id=None, link=None, smart_keywords=None):
    url = API_DUPLICATE_SCREENING

    payload = {
        'user_id': user_id
    }

    if liepin_keywords:
        payload['liepin_keywords'] = liepin_keywords
    if data_id:
        payload['data_id'] = data_id
    if position_id:
        payload['position_id'] = position_id
    if link:
        payload['link'] = link
    if smart_keywords:
        payload['smart_keywords'] = smart_keywords

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_headhunters(headhuntersKind):
    url = API_GET_HEADHUNTERS

    payload = {
        'headhunters': headhuntersKind
    }

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_positions(hunterId):
    url = API_GET_POSITIONS

    payload = {
        'headhunter_id': hunterId
    }

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_job_data(position_id):
    url = API_GET_JOB_DATA

    payload = {
        'position_id': position_id
    }

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def add_resume(position_id, resume, **kwargs):
    url = API_UPDATE_RESUME
    payload = {
        'position_id': position_id,
        'type': 'position',
        'source': ENUM_CANDIDATE_CLASSIFY.ZHI_LIAN.value,
    }
    payload.update(kwargs)
    files = {
        # 'images': ('resume', resume.encode('utf-8'), 'application/octet-stream')
        'images': ('resume', resume, 'text/plain')
    }

    return requests.post(url, data=payload, files=files)

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def update_resume(resume_id,**kwargs):
    url = API_UPDATE_RESUME
    payload = {
        'resume_id':resume_id
    }
    payload.update(kwargs)
    return requests.post(url,data=payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def update_screening_resume(resume_id, **kwargs):
    url = API_UPDATE_SCREENING_RESUME
    payload = {
        'screening_id': resume_id,
        'source': 'zhilian',
    }
    payload.update(kwargs)

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def update_chat_history(resume_id, chat_history):
    url = API_UPDATE_CHAT_HISTORY
    payload = {
        'resume_id': resume_id,
        'chat_history': chat_history,
    }

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def update_status_tag(resume_id, status_tags):
    url = API_UPDATE_STATUS_TAG
    payload = {
        'resume_id': resume_id,
        'status_tags': status_tags
    }

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_incharge_id_by_position_id(position_id):
    url = API_GET_INCHARGE_ID_BY_POSITION_ID
    payload = {
        'position_id': position_id
    }

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_resume_data(resume_id):
    url = API_GET_RESUME_DATA
    payload = {
        'id': resume_id
    }
    return requests.post(url, payload)


def get_ah_result_dict(response: Response):
    return json.loads(response.content.decode('utf-8'))


# Manual demo removed from repository import; use synthetic fixtures for local testing.
