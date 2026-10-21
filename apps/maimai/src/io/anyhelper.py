"""
@describe:
@fileName: server_io.py
@time    : 2025/9/17 18:05
@author  : duke
"""
import requests
from src.config.anyhelper import *
from src.utils.decorator import http_retry
from src.config.http import *


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def h5_post(position_id, title, content):
    url = API_H5_POST

    payload = {
        'custom_fields': '{}',
        'position_id': position_id,
        'title': title,
        'content': content,
    }

    return requests.post(url, payload, timeout=HTTP_TIME_OUT_AH)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def h5_ai_update_status(position_id, ai_process_status: ENUM_H5_AI_STATUS, ai_status=None):
    url = API_H5_AI_UPDATE_STATUS

    payload = {
        'position_id': position_id,
        'ai_process_status': ai_process_status.value,
    }

    if ai_status:
        payload['ai_status'] = ai_status

    return requests.post(url, payload, timeout=HTTP_TIME_OUT_AH)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def add_screening_resume(position_id,incharge_id,status = "待联系", coins_cost=2,**kwargs):
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
def get_search_condition(position_id):
    url = API_GET_SEARCH_STRATEGY

    payload = {
        'position_id': position_id,
    }

    return requests.post(url, payload, timeout=HTTP_TIME_OUT_AH)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_incharge_id_by_pid(position_id):
    url = API_GET_INCHARGE_ID

    payload = {
        'position_id': position_id,
    }

    return requests.post(url, payload, timeout=HTTP_TIME_OUT_AH)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_position_info(position_id):
    url = API_GET_POSITION_INFO

    payload = {
        'position_id': position_id,
    }

    return requests.post(url, payload, timeout=HTTP_TIME_OUT_AH)


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

    return requests.post(url, payload, timeout=HTTP_TIME_OUT_AH)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def duplicate_screening(position_id,liepin_keywords, incharge_id=None):
    url = API_DUPLICATE_SCREENING

    payload = {
        'position_id':position_id,
        'liepin_keywords': liepin_keywords,
        'user_id': incharge_id,
    }

    return requests.post(url, payload, timeout=HTTP_TIME_OUT_AH)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def duplicate(incharge_id=None, vx=None, mobile=None):
    url = API_DUPLICATE

    payload = {
        'weixin': vx,
        'phone': mobile,
        'user_id': incharge_id,
    }

    return requests.post(url, payload, timeout=HTTP_TIME_OUT_AH)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def update_chat_history(resume_id, chat_history):
    url = API_UPDATE_CHAT_HISTORY
    payload = {
        'resume_id': resume_id,
        'chat_history': chat_history,
    }

    return requests.post(url, payload, timeout=HTTP_TIME_OUT_AH)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def update_screening_resume(resume_id, **kwargs):
    url = API_UPDATE_SCREENING_RESUME
    payload = {
        'screening_id': resume_id,
        'source': 'maimai',
    }
    payload.update(kwargs)

    return requests.post(url, payload, timeout=HTTP_TIME_OUT_AH)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def add_resume(position_id, resume, **kwargs):
    url = API_ADD_RESUME
    payload = {
        'position_id': position_id,
        'type': 'position',
        'is_sticky': 1,
        'source': 'maimai',
    }
    payload.update(kwargs)

    files = {
        # 'images': ('resume', resume.encode('utf-8'), 'application/octet-stream')
        'images': ('resume', resume, 'text/plain')
    }

    return requests.post(url, data=payload, files=files, timeout=HTTP_TIME_OUT_AH)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_user_role(user_id):
    url = API_GET_USER_ROLE
    payload = {
        'user_id': user_id,
    }

    return requests.post(url, payload, timeout=HTTP_TIME_OUT_AH)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def update_resume(resume_id, status_tags=None, **kwargs):
    url = API_UPDATE_RESUME
    payload = {
        'resume_id': resume_id,
    }
    if status_tags:
        payload['status_tags'] = status_tags
    payload.update(kwargs)

    return requests.post(url, payload, timeout=HTTP_TIME_OUT_AH)

@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_headhunter_list(headhunter_kind):
    url = API_GET_HUNTER_LIST

    payload = {
        'headhunters': headhunter_kind
    }

    return requests.post(url, payload,timeout=HTTP_TIME_OUT_AH)

@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_position_list(hunter_id):
    url = API_GET_POSITION_LIST

    payload = {
        'headhunter_id': hunter_id
    }

    return requests.post(url, payload,timeout=HTTP_TIME_OUT_AH)



if __name__ == '__main__':
    pass
