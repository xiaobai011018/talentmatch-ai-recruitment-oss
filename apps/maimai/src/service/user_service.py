"""
@describe:
@fileName: user.py
@time    : 2025/9/24 20:19
@author  : duke
"""
import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from src.io.maimai import UserProxy
from src.models import User, MMJob, SearchCondition
from src.exceptions import *
from src.utils import decode_resp_json
from src.config.maimai import PATTERN_MM_CSRF, PATTERN_MM_CSRF_TOKEN, PATTERN_MM_MOBILE
import re


_RESUME_PAGE_PATH = '/profile/resume_detail'
_RESUME_SHARE_DATA_PATTERN = re.compile(
    r'(?:window\.)?share_data\s*=\s*JSON\.parse\(\s*("(?:\\.|[^"\\])*")\s*\)',
    re.S,
)
_RESUME_SECRET_KEYS = {'trackable_token', '_csrf', '_csrf_token', 'csrftoken'}
_RESUME_SECRET_QUERY_KEYS = _RESUME_SECRET_KEYS | {'share_token', 'token'}
_CANDIDATE_PROFILE_KEYS = {
    'id', 'name', 'avatar', 'career', 'company', 'position', 'dist',
    'judge', 'position_judge', 'rank', 'remark_name', 'status', 'utype',
}


def _resume_card_urls(dialogs):
    urls = []
    for dialog in reversed(dialogs or []):
        if dialog.get('is_me') or dialog.get('type') != 123:
            continue
        card = dialog.get('common_card') or {}
        for key in ('global_click_web_url', 'global_click'):
            url = card.get(key)
            if not isinstance(url, str):
                continue
            parsed = urlsplit(url)
            if (
                parsed.scheme == 'https'
                and parsed.hostname == 'maimai.cn'
                and parsed.path.rstrip('/') == _RESUME_PAGE_PATH
                and url not in urls
            ):
                urls.append(url)
    return urls


def _without_resume_secrets(value):
    if isinstance(value, dict):
        return {
            key: _without_resume_secrets(item)
            for key, item in value.items()
            if str(key).lower() not in _RESUME_SECRET_KEYS
        }
    if isinstance(value, list):
        return [_without_resume_secrets(item) for item in value]
    if isinstance(value, str) and value.startswith(('http://', 'https://')):
        parsed = urlsplit(value)
        query = [
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in _RESUME_SECRET_QUERY_KEYS
        ]
        return urlunsplit((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        ))
    return value


def _parse_resume_page(html):
    if not isinstance(html, str):
        return None
    match = _RESUME_SHARE_DATA_PATTERN.search(html)
    if not match:
        return None
    try:
        share_data = json.loads(json.loads(match.group(1)))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    data = share_data.get('data') if isinstance(share_data, dict) else None
    if not isinstance(data, dict) or not data:
        return None
    return {
        'result': data.get('result', 'ok'),
        'data': _without_resume_secrets(data),
        'resume_source': 'resume_card_page',
    }


def _build_profile_resume(contact_data=None, candidate=None):
    """Build a usable, token-free profile when Maimai withholds full resume data."""
    contact_data = contact_data if isinstance(contact_data, dict) else {}
    candidate = candidate if isinstance(candidate, dict) else {}
    data = contact_data.get('data')
    contact_card = data.get('card') if isinstance(data, dict) else {}
    contact_card = contact_card if isinstance(contact_card, dict) else {}

    profile = {
        key: value
        for key, value in candidate.items()
        if key in _CANDIDATE_PROFILE_KEYS and value not in (None, '', [], {})
    }
    profile.update({
        key: value
        for key, value in contact_card.items()
        if value not in (None, '', [], {})
    })
    profile = _without_resume_secrets(profile)
    if not profile:
        return None

    return {
        'result': 'ok',
        'data': {'card': profile},
        'resume_source': 'contact_profile_fallback',
        'resume_limited': True,
    }


class UserService:
    def __init__(self, cookies):
        self.proxy = UserProxy(cookies)
        self.user = User(self._pull_all_jod(), **self._pull_user_info())
        self.chat_init()

    def export_cookies(self):
        return self.proxy.export_cookies()

    def refresh(self):
        self.user = User(self._pull_all_jod(), **self._pull_user_info())

    def _get_job_by_pid(self, pid: str):
        try:
            job = self.user.job_dict[pid]
        except KeyError:
            raise DisMatchedJobException(pid, self.user.name)
        return job

    def get_jid_by_pid(self, pid: str):
        return self._get_job_by_pid(pid).jid

    def get_ejid_by_pid(self, pid: str):
        return self._get_job_by_pid(pid).ejid

    def get_jname_by_pid(self, pid: str):
        return self._get_job_by_pid(pid).position

    def _pull_all_jod(self):
        resp = self.proxy.get_job_list()
        data = decode_resp_json(resp)
        jobs = data['jobs']
        result = {}
        for job in jobs:
            pid_group = re.search(r"\d+", job['position'])
            if not pid_group:
                continue
            pid = pid_group.group()
            result[pid] = MMJob(**job)
        return result

    def _pull_user_info(self):
        resp = self.proxy.get_user_info()
        data = decode_resp_json(resp)
        return data['data']['ucard']

    def search_candidate(self, search_condition: SearchCondition, page, size):
        payload = search_condition.get_mm_payload(page, size)
        resp = self.proxy.search_candidate(payload)
        data = decode_resp_json(resp)
        return data['data']

    # def send_job(self, uid, jid, greet_text):
    #     resp = self.proxy.send(uid, greet_text, jid=jid, greet_name='您好，')
    #     data = decode_resp_json(resp)
    #     return data['result'] == 'ok'

    def batch_send_job(self, uids, pid, greet_text):
        jid = self.get_jid_by_pid(pid)
        resp = self.proxy.batch_send(uids, greet_text, jid=jid, greet_name_type='姓+先生/女士')
        data = decode_resp_json(resp)
        return data

    def chat_init(self):
        resp = self.proxy.chat()
        text = resp.text
        match = re.search(PATTERN_MM_CSRF, text)
        try:
            _csrf = match.group(1)
        except Exception as e:
            raise NoCSRFException(str(e))

        match = re.search(PATTERN_MM_CSRF_TOKEN, text)
        try:
            _csrf_token = match.group(1)
        except Exception as e:
            raise NoCSRFException(str(e))

        _csrf = _csrf.encode('utf-8').decode('unicode_escape')
        _csrf_token = _csrf_token.encode('utf-8').decode('unicode_escape')

        self.proxy._csrf = _csrf
        self.proxy.headers['X-Csrf-Token'] = _csrf_token
        self.proxy.cookies_dict['csrftoken'] = _csrf_token
        pass

    def get_msgs(self, count=100, only_unread=False, page=0):
        resp = self.proxy.get_msg_by_ldtime(count, only_unread=only_unread, page=page)
        data = decode_resp_json(resp)
        msgs = data['messages']
        return msgs

    def get_all_msgs(self, only_unread=False, page_size=100, max_pages=50):
        all_msgs = []
        seen_ids = set()
        for page in range(max_pages):
            msgs = self.get_msgs(count=page_size, only_unread=only_unread, page=page)
            if not msgs:
                break
            for msg in msgs:
                mid = msg.get('id')
                if mid in seen_ids:
                    continue
                seen_ids.add(mid)
                all_msgs.append(msg)
            if len(msgs) < page_size:
                break
        return all_msgs

    def _get_trackable_token(self, uid):
        resp = self.proxy.get_contact(uid)
        return json.loads(resp.text)['data']['card']['trackable_token']

    def get_resume(self, uid, dialogs=None, candidate=None, with_response=False):
        for url in _resume_card_urls(dialogs):
            try:
                page_resp = self.proxy.get_resume_page(url)
            except (
                requests.RequestException,
                HTTPRetryException,
                AccessForbiddenException,
                CookiesExpiredException,
            ):
                continue
            page_data = _parse_resume_page(page_resp.text)
            if page_data:
                if with_response:
                    return page_data, page_resp
                return page_data

        contact_data = None
        contact_resp = None
        contact_error = None
        try:
            contact_resp = self.proxy.get_contact(uid)
            contact_data = decode_resp_json(contact_resp)
        except (
            requests.RequestException,
            HTTPRetryException,
            AccessForbiddenException,
            CookiesExpiredException,
            InvalidRespJsonException,
        ) as error:
            contact_error = error

        contact_card = (
            contact_data.get('data', {}).get('card', {})
            if isinstance(contact_data, dict)
            else {}
        )
        trackable_token = (
            contact_card.get('trackable_token')
            if isinstance(contact_card, dict)
            else None
        )
        resp = None
        data = None
        legacy_error = None
        if trackable_token:
            try:
                resp = self.proxy.get_resume(uid, trackable_token)
                data = decode_resp_json(resp)
            except (
                requests.RequestException,
                HTTPRetryException,
                AccessForbiddenException,
                CookiesExpiredException,
                InvalidRespJsonException,
            ) as error:
                legacy_error = error

        if isinstance(data, dict) and data.get('data'):
            if with_response:
                return data, resp
            return data

        profile_resume = _build_profile_resume(contact_data, candidate)
        if profile_resume:
            if with_response:
                return profile_resume, contact_resp or resp
            return profile_resume

        if legacy_error:
            raise legacy_error
        if contact_error:
            raise contact_error
        if data is None:
            data = {
                'result': 'error',
                'error': 'Maimai resume and public profile are unavailable.',
            }
        if with_response:
            return data, resp
        return data

    def req_mobile_vx(self, uid, mid, pid):
        ejid = self.get_ejid_by_pid(pid)
        resp1 = self.proxy.mobile_req(uid, mid, ejid)
        resp2 = self.proxy.vx_req(uid, mid, ejid)
        return decode_resp_json(resp1), decode_resp_json(resp2)

    def get_dialog(self, mid, count=100):
        r = []
        resp = self.proxy.get_dialog(mid)
        dialogs = decode_resp_json(resp)['dialogues']
        r += dialogs
        while len(dialogs) == 20 and len(r) < count:
            resp = self.proxy.get_dialog(mid, before_did=dialogs[0]['id'])
            dialogs = decode_resp_json(resp)['dialogues']
            r += dialogs
        r.sort(key=lambda x:x['crtimestamp'])
        return r

    def add_dialog(self, mid, msg):
        resp = self.proxy.add_dialog(mid, msg)
        return decode_resp_json(resp)['dialogue']['last_did']

    def get_mobile(self, mid):
        resp = self.proxy.enter_msg(mid)
        text = resp.text
        match = re.search(PATTERN_MM_MOBILE, text)
        if match:
            return match.group(1)
        return None

    def read_msg(self, mid, last_did):
        resp = self.proxy.clear_badge(mid, last_did)
        return resp.ok
