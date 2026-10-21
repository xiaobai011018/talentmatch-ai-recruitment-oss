"""
@describe:
@fileName: server_io.py
@time    : 2025/9/17 18:05
@author  : duke
"""
import re
import time
import requests
from urllib.parse import parse_qsl, urlparse
from requests import Response

from backend.config.anyJobConfig import *
from backend.utils.decorator.http_retry import http_retry
from backend.config.httpRetryConfig import *
from backend.logger.logger import get_logger


logger = get_logger(__name__)


class AnyJobResponseError(Exception):
    pass


def _get_anyjob_action(url):
    path = urlparse(url or '').path
    endpoint = path.rsplit('/', 1)[-1]
    action_map = {
        'add_ai_posts.php': 'h5_post',
        'update_ai_status.php': 'h5_ai_update_status',
        'add_screening_resume.php': 'add_screening_resume',
        'get_search_strategy.php': 'get_search_conditions',
        'get_ai_jd.php': 'get_job_data',
        'add_data_count.php': 'h5_ai_add_count',
        'duplicate_screening_resume.php': 'duplicate_screening',
        'duplicate.php': 'duplicate',
        'get_headhunters.php': 'get_headhunters',
        'get_jds.php': 'get_positions',
        'get_user_role.php': 'get_user_role',
        'add-resume.php': 'add_resume',
        'update_resume_summary.php': 'update_resume',
        'update_screening_resume.php': 'update_screening_resume',
        'update_chat_history.php': 'update_chat_history',
        'get_jd_by_id.php': 'get_incharge_id_by_position_id',
    }
    return action_map.get(endpoint, endpoint or 'unknown')


def _get_request_field_names(response):
    request = getattr(response, 'request', None)
    body = getattr(request, 'body', None)
    if not body:
        return ''

    if isinstance(body, bytes):
        body_text = body.decode('utf-8', errors='ignore')
    else:
        body_text = str(body)

    content_type = ''
    headers = getattr(request, 'headers', None)
    if headers:
        content_type = headers.get('content-type', '')

    field_names = []
    if 'multipart/form-data' in content_type:
        field_names = re.findall(r'name="([^"]+)"', body_text[:10000])
    else:
        parsed_fields = parse_qsl(body_text, keep_blank_values=True)
        if parsed_fields:
            field_names = [key for key, _ in parsed_fields]
        elif '=' in body_text:
            field_names = [part.split('=', 1)[0] for part in body_text.split('&') if part]

    return ','.join(dict.fromkeys(field_names))


def _sanitize_body_preview(text):
    preview = (text or '')[:500]
    preview = re.sub(r'(?<!\d)1\d{10}(?!\d)', '1**********', preview)
    preview = re.sub(
        r'((?:phone|mobile|tel|weixin|wechat|vx)[^=:"\']*[=:"\']\s*)[^&,\s<>"\']+',
        r'\1***',
        preview,
        flags=re.IGNORECASE,
    )
    return preview


def _log_ah_response_error(reason, response, body_preview=''):
    if response is None:
        logger.warning(f'AnyJob 响应异常，reason={reason}，response=None')
        return

    url = getattr(response, 'url', '')
    status_code = getattr(response, 'status_code', None)
    headers = getattr(response, 'headers', {}) or {}
    content_type = headers.get('content-type', '')
    request = getattr(response, 'request', None)
    method = getattr(request, 'method', '') if request else ''
    action = _get_anyjob_action(url)
    request_fields = _get_request_field_names(response)
    safe_body_preview = _sanitize_body_preview(body_preview)

    logger.warning(
        f'AnyJob 响应异常，reason={reason}，action={action}，method={method}，'
        f'url={url}，status={status_code}，content_type={content_type}，'
        f'request_fields={request_fields or "none"}，body_preview={safe_body_preview}'
    )


def summarize_anyjob_response(response):
    summary = {
        'http_status': getattr(response, 'status_code', None) if response is not None else None,
        'code': None,
        'message': '',
        'data_type': 'none',
        'results_count': None,
        'screening_id': None,
    }
    if response is None:
        return summary

    try:
        payload = response.json()
    except Exception:
        return summary

    if not isinstance(payload, dict):
        summary['data_type'] = type(payload).__name__
        return summary

    summary['code'] = payload.get('code')
    summary['message'] = _sanitize_body_preview(
        str(payload.get('message') or payload.get('msg') or '')
    )[:200]
    data = payload.get('data')
    summary['data_type'] = type(data).__name__

    results = payload.get('results')
    if isinstance(results, list):
        summary['results_count'] = len(results)
    elif isinstance(data, dict) and isinstance(data.get('results'), list):
        summary['results_count'] = len(data['results'])

    for container in (payload, data):
        if not isinstance(container, dict):
            continue
        for key in ('screening_id', 'screeningId', 'id'):
            if container.get(key) is not None:
                summary['screening_id'] = container.get(key)
                return summary

    result_lists = [results]
    if isinstance(data, dict):
        result_lists.append(data.get('results'))
    elif isinstance(data, list):
        result_lists.append(data)
    for result_list in result_lists:
        if not isinstance(result_list, list) or not result_list or not isinstance(result_list[0], dict):
            continue
        for key in ('screening_id', 'screeningId', 'id'):
            if result_list[0].get(key) is not None:
                summary['screening_id'] = result_list[0].get(key)
                return summary

    return summary


def _post_with_diagnostics(action, url, payload, trace_id=None):
    trace = trace_id or 'none'
    request_fields = ','.join(payload.keys()) if isinstance(payload, dict) else 'unknown'
    logger.info(
        f'[外部调用] trace_id={trace} action={action} stage=request '
        f'url={url} request_fields={request_fields or "none"}'
    )
    started_at = time.perf_counter()
    try:
        response = requests.post(url, payload)
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.warning(
            f'[外部调用] trace_id={trace} action={action} stage=exception '
            f'elapsed_ms={elapsed_ms} exception_type={type(e).__name__} reason={e}'
        )
        raise

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    summary = summarize_anyjob_response(response)
    logger.info(
        f'[外部调用] trace_id={trace} action={action} stage=response '
        f'elapsed_ms={elapsed_ms} http_status={summary["http_status"]} '
        f'code={summary["code"]} message={summary["message"] or "none"} '
        f'data_type={summary["data_type"]} results_count={summary["results_count"]} '
        f'screening_id={summary["screening_id"]}'
    )
    return response


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def h5_post(position_id, title, content, trace_id=None):
    url = API_H5_POST

    payload = {
        'custom_fields': '{}',
        'position_id': position_id,
        'title': title,
        'content': content,
    }

    return _post_with_diagnostics('h5_post', url, payload, trace_id=trace_id)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def h5_ai_update_status(position_id, ai_process_status: ENUM_H5_AI_STATUS, ai_status = None):
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
def add_screening_resume(position_id, incharge_id, status="待联系", coins_cost=2, trace_id=None, **kwargs):
    url = API_ADD_SCREENING_RESUME

    payload = {
        'position_id': position_id,
        'incharge_id': incharge_id,
        'status': status,
        'coins_cost': coins_cost,
    }

    payload.update(kwargs)

    return _post_with_diagnostics('add_screening_resume', url, payload, trace_id=trace_id)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_search_conditions(position_id,id = None):
    url = API_GET_SEARCH_STRATEGYS

    payload = {
        'position_id': position_id,
    }

    if id:
        payload['id'] = id

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_position_info(position_id):
    url = API_GET_POSITION_INFO

    payload = {
        'position_id': position_id,
    }

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def h5_ai_add_count(position_id, trace_id=None, **kwargs):
    """
    :param kwargs: count_resume_reviews, count_conversations, count_replies, count_resume_uploads
    :return:
    """
    url = API_H5_AI_ADD_COUNT

    payload = {
        'position_id': position_id,
    }

    payload.update(kwargs)

    return _post_with_diagnostics('h5_ai_add_count', url, payload, trace_id=trace_id)

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def duplicate(user_id, position_id=None, phone=None, vx=None, smart_keywords=None, link=None):
    url = API_DUPLICATE
    payload = {
        'user_id':user_id
    }

    if position_id:
        payload['position_id'] = position_id
    if phone:
        payload['phone'] = phone
    if vx:
        payload['weixin'] = vx
    if smart_keywords:
        payload['smart_keywords'] = smart_keywords
    if link:
        payload['link'] = link

    return requests.post(url, payload)


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def duplicate_screening(
        user_id,
        liepin_keywords=None,
        data_id=None,
        position_id=None,
        link=None,
        smart_keywords=None,
        trace_id=None,
):
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

    return _post_with_diagnostics('duplicate_screening', url, payload, trace_id=trace_id)

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def get_headhunters(headhuntersKind):
    url = API_GET_HEADHUNTERS

    payload = {
        'headhunters' : headhuntersKind
    }

    return requests.post(url, payload)

@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def get_positions(hunterId):
    url = API_GET_POSITIONS

    payload = {
        'headhunter_id' : hunterId
    }

    return requests.post(url, payload)

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def get_job_data(position_id):
    url = API_GET_JOB_DATA

    payload = {
        'position_id' : position_id
    }

    return requests.post(url, payload)

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def add_resume(position_id, resume, **kwargs):
    url = API_ADD_RESUME
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
        'source': 'liepin',
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

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def update_status_tag(resume_id,status_tags):
    url = API_UPDATE_STATUS_TAG
    payload = {
        'resume_id':resume_id,
        'status_tags': status_tags
    }

    return requests.post(url,payload)

@http_retry(HTTP_RETRY_TIMES,HTTP_RETRY_GAP)
def get_incharge_id_by_position_id(position_id, trace_id=None):
    url = API_GET_INCHARGE_ID_BY_POSITION_ID
    payload = {
        'position_id': position_id
    }
    return _post_with_diagnostics('get_incharge_id_by_position_id', url, payload, trace_id=trace_id)


def get_ah_result_dict(response: Response):
    if response is None:
        _log_ah_response_error('response_none', response)
        raise AnyJobResponseError('AnyJob 响应为空对象')

    status_code = getattr(response, 'status_code', None)
    text = response.text or ''

    if status_code is None or status_code < 200 or status_code >= 300:
        _log_ah_response_error('bad_status', response, text)
        raise AnyJobResponseError(f'AnyJob 响应状态异常 status={status_code}')

    if not text.strip():
        _log_ah_response_error('empty_body', response)
        raise AnyJobResponseError('AnyJob 响应体为空')

    try:
        return response.json()
    except ValueError as e:
        _log_ah_response_error('invalid_json', response, text)
        raise AnyJobResponseError('AnyJob 响应不是合法 JSON') from e


# Manual demo removed from repository import; use synthetic fixtures for local testing.
