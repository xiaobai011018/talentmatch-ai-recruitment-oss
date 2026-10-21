"""
@describe:
@fileName: manager.py
@time    : 2025/9/24 20:41
@author  : duke
"""
import json
import logging
import os
import pickle
import re
import time
import traceback
from datetime import datetime, timedelta
import pandas as pd

from src.io.anyhelper import h5_post, add_screening_resume, get_incharge_id_by_pid, get_user_role
# from tqdm import tqdm
from src.service import UserService
from src.models import AHPosition, SearchCondition
import src.io.anyhelper as ah_io
import src.io.bot as bot_io
from src.utils import decode_resp_json, random_sleep, Logger, stream_download
from src.utils.highest_education import extract_screening_education, log_screening_education
from src import _CONFIG
from src.exceptions import *
from src.config.maimai import MM_OFFICIAL_IDs, MM_SKIP_MSG_NAMES, MM_CANDIDATE_REPLY_TYPES, \
    MM_SECOND_CONTACT_LIMIT, PATTERN_MM_VX, FIRST_CONTACT_CANDIDATE_RESUME_KEYS, AUTO_REPLY_SLEEP_TIME
from src.config.bot import ENUM_MODEL_ID
from src.config.path import LOG_PATH, SAVE_FILE_DIR, SAVE_PATH
import src.service.maimai_chrome as mm_c
import threading
from src.config.path import *

# 人才库上传 coins_cost：GET_TAG_BY_CHAT_HISTORY 返回的状态标签 ID
TAG_STRONG_INTENT = 256  # 强意向（需在 >=109 分支之前匹配）
TAG_URGENT_JOB_SEEKING = frozenset((104, 105, 107))  # 在职急寻、在职看机会、离职
TAG_LOW_URGENCY_MIN = 109  # 需再联系 109、不跳槽 110 及更大 ID（不含已单独处理的 256）

_CANDIDATE_REPLY_IN_CHAT = re.compile(r'候选人:\s*\S')
_PHONE_PATTERN = re.compile(r'(?<!\d)1\d{10}(?!\d)')
_VISIBLE_PHONE_PATTERN = re.compile(
    r'(?<!\d)(?:\+?86[\s-]*)?1[3-9](?:[\s-]*\d){9}(?!\d)'
)
_VISIBLE_WECHAT_PATTERN = re.compile(
    r'((?:微信号\s*[:：]?\s*|(?:微信|[Vv][Xx]|[Ww]e[Cc]hat)(?:\s*[:：]\s*|\s+)))'
    r'([A-Za-z0-9][A-Za-z0-9._-]{2,})'
)
_WECHAT_ID_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$')
_CONTACT_HIDDEN_TEXT = '[联系方式已隐藏，解锁后查看]'
_CONTACT_EXCHANGE_TEXT = '[已交换联系方式（解锁后查看）]'
_CONTACT_REQUEST_TEXT = '[请求交换联系方式]'
_CONTACT_REQUEST_MARKERS = (
    '我希望与您交换', '我希望与你交换', '对方申请与你交换', '请求交换', '申请交换',
)
_DELETED_MESSAGE_TEXTS = frozenset(('[消息删除]', '消息删除'))
_CANDIDATE_INITIATION_KEYWORDS = (
    '有兴趣聊聊这个职位',
    '对方向您发送简历',
    '最近更新了简历',
)
_AGE_KEYS = ('age', 'ageLabel')
_BIRTH_YEAR_KEYS = ('birthYear', 'birthdayYear', 'bornYear')
_BIRTH_MONTH_KEYS = ('birthMonth', 'birthdayMonth', 'bornMonth')
_BIRTH_LABEL_KEYS = ('birthday', 'birthDate', 'birthYearMonthLabel', 'birthdayLabel')
_RESUME_RESPONSE_ERROR_KEYS = (
    'result', 'code', 'error_code', 'status', 'message', 'msg', 'reason', 'error', 'detail',
)
_DIAGNOSTIC_SECRET_PATTERN = re.compile(
    r'(?i)((?:trackable_token|csrf(?:_token)?|csrftoken|cookie)s?\s*[:=]\s*)[^,\s;&]+'
)


def _parse_status_tag_id(status_tags):
    try:
        return int(str(status_tags).strip())
    except (ValueError, TypeError):
        return 0


def _has_candidate_reply_in_chat(chat_history):
    if not chat_history or not str(chat_history).strip():
        return False
    return bool(_CANDIDATE_REPLY_IN_CHAT.search(chat_history))


def _chat_tag_without_candidate_reply(chat_history='', dialogs=None):
    if _has_candidate_reply_in_chat(chat_history):
        return None
    for dialog in dialogs or []:
        text = str(dialog.get('text') or '')
        if '已阅读您的消息' in text:
            return '已读不回'
    return '未读消息'


def _is_deleted_message(dialog):
    return str(dialog.get('text') or '').strip() in _DELETED_MESSAGE_TEXTS


def _dialog_text_for_filter(dialog):
    if _is_deleted_message(dialog):
        return ''
    text = (dialog.get('text') or '').strip()
    if text:
        return text
    if dialog.get('type') == 123:
        center = (dialog.get('common_card') or {}).get('center') or {}
        return (center.get('content') or center.get('title') or '').strip()
    return ''


def _redact_contact_text(text):
    if text is None:
        return ''
    text = str(text)
    text = _VISIBLE_PHONE_PATTERN.sub(_CONTACT_HIDDEN_TEXT, text)
    return _VISIBLE_WECHAT_PATTERN.sub(
        lambda match: f'{match.group(1)}{_CONTACT_HIDDEN_TEXT}', text)


def _safe_diagnostic_text(value, limit=300):
    if isinstance(value, (dict, list, tuple, set)):
        return f'<{type(value).__name__}>'
    text = _redact_contact_text(str(value))
    text = _DIAGNOSTIC_SECRET_PATTERN.sub(r'\1[REDACTED]', text)
    text = text.replace('\r', ' ').replace('\n', ' ')
    return text[:limit]


def _resume_response_diagnostic(payload, resp=None):
    diagnostic = {
        'http_status': getattr(resp, 'status_code', None),
        'content_type': (getattr(resp, 'headers', {}) or {}).get('content-type', ''),
        'body_length': len(getattr(resp, 'text', '') or ''),
        'payload_type': type(payload).__name__,
    }
    if not isinstance(payload, dict):
        return diagnostic

    diagnostic['top_level_keys'] = sorted(map(str, payload.keys()))
    diagnostic['has_data'] = 'data' in payload
    diagnostic['data_type'] = type(payload.get('data')).__name__ if 'data' in payload else None
    diagnostic['data_present'] = bool(payload.get('data'))

    error_fields = {}
    for key in _RESUME_RESPONSE_ERROR_KEYS:
        value = payload.get(key)
        if value is not None:
            error_fields[key] = _safe_diagnostic_text(value)
    diagnostic['error_fields'] = error_fields
    return diagnostic


def _extract_wechat_from_dialog(dialog):
    if _is_deleted_message(dialog) or dialog.get('is_me'):
        return None
    center = (dialog.get('common_card') or {}).get('center') or {}
    texts = (
        str(dialog.get('text') or ''),
        str(center.get('title') or ''),
        str(center.get('content') or ''),
    )
    for text in texts:
        match = PATTERN_MM_VX.search(text)
        if match:
            return match.group(1)

    content = texts[2].strip()
    labels = '\n'.join(texts[:2])
    if '微信号' in labels and _WECHAT_ID_PATTERN.fullmatch(content):
        return content
    return None


def _extract_phone_from_dialog(dialog):
    if _is_deleted_message(dialog) or dialog.get('is_me'):
        return None
    center = (dialog.get('common_card') or {}).get('center') or {}
    texts = (
        str(dialog.get('text') or ''),
        str(center.get('title') or ''),
        str(center.get('content') or ''),
    )
    for text in texts:
        match = _VISIBLE_PHONE_PATTERN.search(text)
        if not match:
            continue
        prefix = text[max(0, match.start() - 12):match.start()].lower()
        surrounding_text = text[:match.start()] + text[match.end():]
        is_standalone = not surrounding_text.strip(' ，,。.!！?？:：;；')
        has_phone_context = any(
            marker in prefix for marker in ('手机', '电话', '联系', '号码', 'tel', 'phone'))
        if dialog.get('type') != 123 and not is_standalone and not has_phone_context:
            continue
        digits = re.sub(r'\D', '', match.group(0))
        if digits.startswith('86'):
            digits = digits[2:]
        if _PHONE_PATTERN.fullmatch(digits):
            return digits
    return None


def _dialog_text_for_visible_history(dialog):
    text = _dialog_text_for_filter(dialog)
    if dialog.get('type') == 123:
        center = (dialog.get('common_card') or {}).get('center') or {}
        texts = (
            str(dialog.get('text') or ''),
            str(center.get('title') or ''),
            str(center.get('content') or ''),
        )
        combined = '\n'.join(texts)
        if any(_VISIBLE_PHONE_PATTERN.search(item) for item in texts) or _extract_wechat_from_dialog(dialog):
            return _CONTACT_EXCHANGE_TEXT
        if any(marker in combined for marker in _CONTACT_REQUEST_MARKERS):
            return _CONTACT_REQUEST_TEXT
    return _redact_contact_text(text)


def _is_candidate_initiation_dialog(dialog):
    if dialog.get('is_me'):
        return False
    msg_type = dialog.get('type')
    if msg_type not in (116, 118, 123):
        return False
    text = _dialog_text_for_filter(dialog)
    return any(keyword in text for keyword in _CANDIDATE_INITIATION_KEYWORDS)


def _compute_resume_coin_cost(raw_comment, chat_history, status_tags):
    """
    根据初审结论（comment）、是否有候选人发言、状态标签计算上传人才库金币消耗。
    raw_comment 须为 MATCH_CHECK_SECOND 原始输出（未经 replace/split 处理）。
    """
    not_pass = ('不匹配' in raw_comment) or ('不确定' in raw_comment)
    has_reply = _has_candidate_reply_in_chat(chat_history)

    if not_pass:
        return 30 if has_reply else 20
    if not has_reply:
        return 40

    tag_id = _parse_status_tag_id(status_tags)
    if tag_id == TAG_STRONG_INTENT:
        return 80
    if '非常匹配' in raw_comment:
        if tag_id in TAG_URGENT_JOB_SEEKING:
            return 80
        if tag_id >= TAG_LOW_URGENCY_MIN:
            return 60
        return 60
    return 50


def _on_logger_active(msg):
    # msg = f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] ' + msg
    print(msg)
    with open(LOG_PATH, 'a', encoding='utf-8', errors='replace') as f:
        f.write(msg)


def _normalize_contact(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() == 'none':
        return None
    return s


def _find_first_nested_value(payload, keys):
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if value not in (None, ''):
                return value
        for value in payload.values():
            found = _find_first_nested_value(value, keys)
            if found not in (None, ''):
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_first_nested_value(item, keys)
            if found not in (None, ''):
                return found
    return None


def _calculate_age_from_birth(year, month=None):
    try:
        year_int = int(year)
    except (TypeError, ValueError):
        return None

    now = datetime.now()
    if year_int < 1900 or year_int > now.year:
        return None

    age = now.year - year_int
    try:
        month_int = int(month) if month not in (None, '') else None
    except (TypeError, ValueError):
        month_int = None

    if month_int and 1 <= month_int <= 12 and now.month < month_int:
        age -= 1
    return age if 0 < age < 100 else None


def _calculate_age_from_timestamp(timestamp):
    try:
        timestamp = float(timestamp)
        if timestamp > 100000000000:
            timestamp = timestamp / 1000
        if timestamp <= 100000000:
            return None
        return _calculate_age_from_birth(datetime.fromtimestamp(timestamp).year)
    except (OverflowError, OSError, ValueError):
        return None


def _normalize_age(value):
    if value in (None, ''):
        return None
    if isinstance(value, (int, float)):
        if value > 100000000:
            return _calculate_age_from_timestamp(value)
        age = int(value)
        if 1900 <= age <= datetime.now().year:
            return _calculate_age_from_birth(age)
        return age if 0 < age < 100 else None

    text = str(value).strip()
    if not text:
        return None

    if re.fullmatch(r'\d{10,13}', text):
        return _calculate_age_from_timestamp(text)

    birth_match = re.search(r'(\d{4})\D{0,3}(\d{1,2})?', text)
    if birth_match:
        return _calculate_age_from_birth(birth_match.group(1), birth_match.group(2))

    short_birth_match = re.search(r'(?<!\d)(\d{2})[年/-](\d{1,2})?', text)
    if short_birth_match:
        year = int(short_birth_match.group(1))
        current_two_digit_year = datetime.now().year % 100
        full_year = 2000 + year if year <= current_two_digit_year else 1900 + year
        return _calculate_age_from_birth(full_year, short_birth_match.group(2))

    match = re.search(r'(\d{1,2})', text)
    if not match:
        return None

    age = int(match.group(1))
    return age if 0 < age < 100 else None


def _extract_age_from_resume_data(resume_data):
    age = _normalize_age(_find_first_nested_value(resume_data, _AGE_KEYS))
    if age:
        return age

    birth_year = _find_first_nested_value(resume_data, _BIRTH_YEAR_KEYS)
    birth_month = _find_first_nested_value(resume_data, _BIRTH_MONTH_KEYS)
    age = _calculate_age_from_birth(birth_year, birth_month)
    if age:
        return age

    birth_label = _find_first_nested_value(resume_data, _BIRTH_LABEL_KEYS)
    return _normalize_age(birth_label)


class Manager:
    def __init__(self):
        self._lock = threading.Lock()
        self.user_services: dict[int, UserService] = dict[int, UserService]()  # key: user_id
        self.status_msg = ''
        self.pid_candidate_contacted_sets = {}  # key: pid
        self._auto_reply_evt = threading.Event()
        self._auto_reply_owner_tid = None
        self.candidates = {}
        # 已成功上传意向库的 (岗位pid, 脉脉uid)，删除档案后仍禁止重复上传
        self.intent_uploaded_keys = set()
        # 会话 mid -> 岗位 pid，多轮回复时职位卡片标题可能无岗位号
        self.conversation_pid_cache = {}
        self.logger = Logger(on_active=_on_logger_active)

    def __getstate__(self):
        state = self.__dict__.copy()
        if '_lock' in state:
            del state['_lock']
        if '_auto_reply_evt' in state:
            del state['_auto_reply_evt']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._lock = threading.Lock()
        self._auto_reply_evt = threading.Event()
        self._auto_reply_owner_tid = None

        if not hasattr(self, 'intent_uploaded_keys'):
            self.intent_uploaded_keys = set()
        if not hasattr(self, 'conversation_pid_cache'):
            self.conversation_pid_cache = {}

    def _intent_upload_key(self, pid, uid):
        return f'{pid}:{int(uid)}'

    def _is_intent_upload_blocked(self, pid, uid, mobile, vx, incharge_id):
        key = self._intent_upload_key(pid, uid)
        if key in self.intent_uploaded_keys:
            return True, '本地已记录上传过意向库，不再重复上传'

        mobile = _normalize_contact(mobile)
        vx = _normalize_contact(vx)
        if mobile or vx:
            try:
                resp = ah_io.duplicate(incharge_id=incharge_id, mobile=mobile, vx=vx)
                data = decode_resp_json(resp)
                if int(data.get('duplicate', 0)):
                    return True, '意向人才查重重复'
            except Exception:
                self.logger.write_line('意向查重接口异常，为安全起见跳过上传', active=True)
                return True, '意向查重接口异常'

        return False, ''

    def _remove_candidate_from_queue(self, uid, name='', reason=''):
        uid = int(uid)
        if uid not in self.candidates:
            return
        del self.candidates[uid]
        label = f'<{name}>' if name else f'uid={uid}'
        msg = f'{label}已从待上传队列移除'
        if reason:
            msg += f'（{reason}）'
        self.logger.write_line(msg, active=True)

    def _purge_stale_candidates(self):
        if not self.candidates:
            return 0
        removed = 0
        for uid in list(self.candidates.keys()):
            candidate = self.candidates[uid]
            pid = candidate['position'].pid
            name = candidate.get('resume', {}).get('name', '')
            blocked, reason = self._is_intent_upload_blocked(
                pid, uid,
                candidate.get('mobile'),
                candidate.get('vx'),
                candidate['position'].incharge_id,
            )
            if blocked:
                del self.candidates[uid]
                removed += 1
                self.logger.write_line(f'清理积压待上传队列：<{name}>{reason}', active=True)
        return removed

    def _mark_intent_uploaded(self, pid, uid):
        self.intent_uploaded_keys.add(self._intent_upload_key(pid, uid))
        with open(SAVE_PATH, 'wb') as f:
            pickle.dump(self, f)

    def _persist_manager(self):
        with open(SAVE_PATH, 'wb') as f:
            pickle.dump(self, f)

    def is_locked(self):
        return self._lock.locked()

    def get_users(self):
        return [service.user for service in self.user_services.values()]

    def _decode_resp_json(self, resp, context='接口'):
        try:
            return decode_resp_json(resp)
        except InvalidRespJsonException:
            status_code = getattr(resp, 'status_code', 'unknown')
            text = getattr(resp, 'text', '')
            snippet = (text or '').replace('\n', ' ')[:300]
            self.logger.write_line(
                f'{context}返回非JSON，status={status_code}，body={snippet!r}', active=True)
            raise

    def update_user(self, cookies):
        service = UserService(cookies)
        with self._lock:
            self.user_services[service.user.id] = service
        return service.user.id

    def parse_is_chat(self,val):
        if pd.isna(val):
            return 0
        try:
            return int(val)
        except:
            return 0

    def get_ah_position(self, pid) -> AHPosition:
        try:
            pid = int(pid)
        except:
            self.logger.write_line(f'<{pid}> is not a legal pid', active=True)
            return None

        try:
            resp = ah_io.get_position_info(pid)
            data = decode_resp_json(resp)
            kwargs = data['results'][0]

            resp = ah_io.get_incharge_id_by_pid(pid)
            data = decode_resp_json(resp)
            data = data['results'][0]
            incharge_id = data['incharge_id']

            return AHPosition(pid, incharge_id, **kwargs)
        except Exception as e:
            self.logger.write_line(f'获取岗位<{pid}>信息失败: {e}', active=True)
            if _CONFIG['dev']:
                traceback.print_exc()
            return None

    def get_search_conditions(self, ah_pid) -> dict[int: SearchCondition]:
        res = ah_io.get_search_condition(ah_pid)
        data = decode_resp_json(res)['results']
        search_conditions = dict[int: SearchCondition]()
        for item in data:
            try:
                search_conditions[item['id']] = SearchCondition(json.loads(item['strategy']))
            except:
                pass
        return search_conditions

    def first_contact(self, pid, search_condition_ids: list[int], greet_text, limit_per_user=50, limit_search=1000,
                      user_ids=None):
        with self._lock:

            pid = str(pid)

            if pid not in self.pid_candidate_contacted_sets.keys():
                self.pid_candidate_contacted_sets[pid] = set()

            ah_io.h5_ai_update_status(pid, ah_io.ENUM_H5_AI_STATUS.CHATTING)

            service_list = list(self.user_services.values())
            if user_ids:
                service_list = [service for service in service_list if service.user.id in user_ids]

            tmp_service: UserService = service_list[0]
            uids = []

            search_conditions = self.get_search_conditions(pid)
            position = self.get_ah_position(pid)
            if not position:
                return -1, 0, []

            for search_condition_id in search_condition_ids:
                self.logger.write_line(
                    f'开始一次激活岗位<{tmp_service.get_jname_by_pid(pid)}>策略<{search_condition_id}>', active=True)

                search_condition: SearchCondition = search_conditions[search_condition_id]
                page_index = 0
                _PAGE_SIZE = 30
                total = tmp_service.search_candidate(search_condition, page_index, _PAGE_SIZE)['total']
                self.logger.write_line(f'该策略共{total}人', active=True)

                if not int(total):
                    continue

                while page_index * _PAGE_SIZE < limit_search:
                    if len(uids) > limit_per_user * len(service_list):
                        break

                    random_sleep()
                    data = tmp_service.search_candidate(search_condition, page_index, _PAGE_SIZE)
                    uids_tmp = data['all_uids']
                    if not len(uids_tmp):
                        break
                    uids_tmp = set(uids_tmp) - self.pid_candidate_contacted_sets[pid]
                    uids_tmp = list(uids_tmp)
                    if not len(uids_tmp):
                        page_index += 1
                        continue

                    self.logger.write_line(f'找到{len(uids_tmp)}位新候选人', active=True)

                    candidates = data['list']

                    candidates = [
                        {key: candidate[key] for key in FIRST_CONTACT_CANDIDATE_RESUME_KEYS if key in candidate}
                        for candidate in candidates if candidate['id'] in uids_tmp]

                    candidates = json.dumps(candidates, ensure_ascii=False)
                    resp = bot_io.send(position.requirement + candidates,
                                       bot_io.ENUM_MODEL_ID.RESUME_BATCH_PRE_CHECK.value)
                    data = decode_resp_json(resp)
                    uids_tmp = data['choices'][0]['message']['content']
                    uids_tmp = uids_tmp.split(',')
                    # uids_tmp = list(map(int, uids_tmp))
                    # uids += uids_tmp

                    for uid in uids_tmp:
                        try:
                            uid = int(uid)
                        except:
                            continue
                        uids.append(uid)

                    page_index += 1

                    self.logger.write_line(f'初筛后剩余{len(uids_tmp)}位候选人', active=True)

            i = 0
            j = 0
            tmp_uids = uids[:limit_per_user]
            succ_count = 0
            exceptions = []
            while len(tmp_uids):
                random_sleep()

                try:
                    tmp_service = service_list[i]
                except IndexError:
                    break
                i += 1

                try:
                    resp_data = tmp_service.batch_send_job(tmp_uids, pid, greet_text)
                    succ_count += resp_data['succ_count']
                    resp = get_incharge_id_by_pid(pid)
                    data = decode_resp_json(resp)
                    data = data['results'][0]
                    incharge_id = data['incharge_id']

                    for obj in resp_data['data']:
                        random_sleep()

                        try:
                            uid = next(iter(obj.keys()))
                            self.pid_candidate_contacted_sets[pid].add(int(uid))
                            mid = obj[uid]['mid']
                            self._remember_conversation_pid(tmp_service.user.id, mid, pid)
                            tmp_service.req_mobile_vx(uid, mid, pid)

                            resume = tmp_service.get_resume(uid)['data']
                            resp = get_user_role(incharge_id)
                            data = decode_resp_json(resp)
                            is_client = False
                            if data['type'] == "client":
                                is_client = True

                            resp = ah_io.duplicate_screening(position.pid,uid,incharge_id)
                            data = decode_resp_json(resp)
                            is_duplicate = False
                            is_duplicate_with_current_position = False
                            if data["duplicate"] == "yes":
                                if is_client:
                                    self.logger.write_line(f'候选人<{resume["name"]}>重复且推荐人为客户，被跳过上传高潜', active=True)
                                    continue
                                is_duplicate = True
                            duplicate_position_name_list = []
                            for record in data.get("records",""):
                                duplicate_position_name_list.append(record['Position'])
                                if pid == record['position_id']:
                                    is_duplicate_with_current_position = True
                            resp = ah_io.get_position_info(pid)
                            data = decode_resp_json(resp)
                            job_requirement = data['results'][0]["summary"]
                            job_deep_requirement = job_requirement.split('深匹要求：')[1]
                            resp = bot_io.send(
                                f'【个人信息：】{json.dumps(resume)}【岗位要求：】{job_deep_requirement}',
                                ENUM_MODEL_ID.MATCH_CHECK_FIRST.value)
                            first_check_comment = decode_resp_json(resp)['choices'][0]['message']['content']
                            resp = bot_io.send(
                                f'【requirements：岗位要求】{job_deep_requirement}【name ：候选人名字】{resume["name"]}【comment: 判断结果和原因】{first_check_comment}【raw resume：候选人简历】{json.dumps(resume)}',
                                ENUM_MODEL_ID.MATCH_CHECK_SECOND.value)
                            fact_check_comment = decode_resp_json(resp)['choices'][0]['message']['content']
                            if '不匹配' in fact_check_comment:
                                self.logger.write_line(
                                    f'候选人<{resume["name"]}>二轮判断不匹配，跳过上传高潜', active=True)
                                continue
                            elif '非常匹配' in fact_check_comment:
                                fact_check_comment_label = '非常匹配'
                            else:
                                fact_check_comment_label = '匹配'
                            resp = bot_io.send(json.dumps(resume), ENUM_MODEL_ID.CLEAN_SCREENING_RESUME.value)
                            data = decode_resp_json(resp)
                            clean_resume = _redact_contact_text(data['choices'][0]['message']['content'])
                            recommendation = re.search(r"\*\*推荐语\*\*[:：]?\s*([\s\S]*?)(?:\n---|\n##|$)",clean_resume).group(1).strip()
                            if is_client:
                                comment = f"{fact_check_comment_label}，{recommendation}"
                            else:
                                # 如果不是客户岗位
                                # 重复了
                                if is_duplicate:
                                    if duplicate_position_name_list:
                                        comment = f"重复：{'，'.join(duplicate_position_name_list)}" + '，' + f'{fact_check_comment}'
                                    else:
                                        comment = f"重复：但是无具体岗位" + '，' + f'{fact_check_comment}'
                                else:
                                    comment = f"{fact_check_comment_label}，{'，'.join(fact_check_comment.split('，')[3:])}"

                            comment = _redact_contact_text(comment)

                            resp = bot_io.send(json.dumps(resume),ENUM_MODEL_ID.AI_SUMMARY_RESUME.value)
                            data = decode_resp_json(resp)
                            ai_summary = _redact_contact_text(data['choices'][0]['message']['content'])

                            SALARY_PATTERN = re.compile(r"\*\*期待薪资\*\*[:：]?\s*(.+)")
                            LOCATION_PATTERN = re.compile(r"\*\*居住地\*\*[:：]?\s*(.+)")
                            TAGS_PATTERN = re.compile(r"\*\*优势标签\*\*[:：]?\s*(.+)")

                            summary_salary = re.search(SALARY_PATTERN,ai_summary)
                            location = re.search(LOCATION_PATTERN,ai_summary)
                            tags = re.search(TAGS_PATTERN,ai_summary)
                            age = _extract_age_from_resume_data(resume)
                            salary = None
                            try:
                                salary = self._clean_expect_salary(resume)
                            except Exception as e:
                                self.logger.write_line(
                                    f'<{resume["name"]}>高潜薪资清洗失败，尝试使用AI摘要薪资: {e}',
                                    active=True,
                                )
                                if _CONFIG['dev']:
                                    traceback.print_exc()

                            kwarg = {
                                "name":resume['name'] if resume['name'] or len(resume['name']) >= 4  else resume["name"][0] + "*",
                                "liepin_keywords":uid,
                                "current_company":resume['current_company']['company'],
                                "current_position":resume['current_company']['position'],
                                "resume_content":clean_resume,
                                "ai_summary":ai_summary,
                                "comment":comment,
                                'source':"maimai"
                            }

                            if salary:
                                kwarg['salary'] = salary
                            elif summary_salary:
                                kwarg['salary'] = summary_salary.group(1).strip()
                            if age:
                                kwarg['age'] = age
                            if location:
                                kwarg['location'] = location.group(1).strip()
                            if tags:
                                kwarg['tags'] = tags.group(1).strip()

                            education, selection = extract_screening_education(resume, kwarg['resume_content'])
                            kwarg.update(education)
                            log_screening_education(self.logger, 'upload_request', pid, uid, education, selection)
                            upload_resp = add_screening_resume(pid,incharge_id,**kwarg)
                            log_screening_education(self.logger, 'upload_response', pid, uid,
                                                    education, selection, upload_resp)
                            h5_post(pid, '发现匹配人才', f'姓名：{"脉脉 " + resume["name"]} 匹配原因：{comment}')
                            ah_io.h5_ai_add_count(pid, count_resume_reviews=1)
                        except Exception as e:
                            exceptions.append(e)
                            if _CONFIG['dev']:
                                traceback.print_exc()
                            continue
                except DisMatchedJobException:
                    self.logger.write_line(f'<{tmp_service.user.name}>在脉脉上无<{pid}>岗位', active=True)
                    continue
                except Exception as e:
                    exceptions.append(e)
                    if _CONFIG['dev']:
                        traceback.print_exc()
                    continue

                j += 1
                tmp_uids = uids[j * limit_per_user:(j + 1) * limit_per_user]

            resp = ah_io.h5_ai_add_count(pid, count_conversations=succ_count)

            self.logger.write_line(f'一次激活完成, <{pid}>岗位h5post发起会话数+{succ_count}', active=True)

        return succ_count, len(uids), exceptions

    def first_contact_with_excel(self, excel_path, greet_text,limit_per_user=50, user_ids=None):
        with self._lock:
            df = pd.read_excel(excel_path)
            rows,cols = df.shape
            link_index = df.columns.get_loc('link')
            position_name_index = df.columns.get_loc("position")
            is_chat_index = df.columns.get_loc("is_chat")
            p_u_map = {}
            for row in range(rows):
                is_chat_raw = df.iat[row, is_chat_index]
                is_chat = self.parse_is_chat(is_chat_raw)
                if is_chat == 1:
                    self.logger.write_line(f"表格发起第{row}行, 已发起，跳过")
                    continue

                if is_chat == 2:
                    self.logger.write_line(f"表格发起第{row}行, 发起异常，跳过")
                    continue

                position_name = df.iat[row,position_name_index]
                if isinstance(position_name, bytes):
                    position_name = position_name.decode("utf-8", errors="ignore")
                else:
                    position_name = str(position_name)
                m = re.search(r'\d+',position_name)
                if not m:
                    self.logger.write_line(f"表格发起第{row}行,岗位名称无数字，被跳过")
                    df.iat[row, is_chat_index] = 2
                    continue
                pid = m.group()
                if pid not in self.pid_candidate_contacted_sets.keys():
                    self.pid_candidate_contacted_sets[pid] = set()
                ah_io.h5_ai_update_status(pid, ah_io.ENUM_H5_AI_STATUS.CHATTING)
                link = df.iat[row,link_index]
                if isinstance(link, bytes):
                    link = link.decode("utf-8", errors="ignore")
                else:
                    link = str(link)
                m = re.search(r"dstu=(\d+)",link)
                if not m :
                    self.logger.write_line(f"表格发起第{row}行,链接中无用户数字，被跳过")
                    df.iat[row, is_chat_index] = 2
                    continue
                maimai_uid = m.group(1)

                if not pid in p_u_map.keys():
                    p_u_map[pid] = []
                p_u_map[pid].append((maimai_uid,row))

            service_list = list(self.user_services.values())
            if user_ids:
                service_list = [service for service in service_list if service.user.id in user_ids]

            pids = p_u_map.keys()
            for pid in pids:
                i = 0
                j = 0
                u_r_map = {}
                for u, r in p_u_map[pid]:
                    u_r_map[u] = r
                uids = list(u_r_map.keys())
                tmp_uids = uids[:limit_per_user]
                succ_count = 0
                exceptions = []
                while len(tmp_uids):
                    random_sleep()

                    try:
                        tmp_service = service_list[i]
                    except IndexError:
                        break
                    i += 1

                    try:
                        resp_data = tmp_service.batch_send_job(tmp_uids, pid, greet_text)
                        succ_count += resp_data['succ_count']

                        for obj in resp_data['data']:
                            random_sleep()

                            try:
                                uid = next(iter(obj.keys()))
                                df.iat[u_r_map[uid], is_chat_index] = 1
                                self.pid_candidate_contacted_sets[pid].add(int(uid))
                                mid = obj[uid]['mid']
                                self._remember_conversation_pid(tmp_service.user.id, mid, pid)
                                tmp_service.req_mobile_vx(uid, mid, pid)
                            except Exception as e:
                                exceptions.append(e)
                                if _CONFIG['dev']:
                                    traceback.print_exc()
                                continue
                    except DisMatchedJobException:
                        self.logger.write_line(f'<{tmp_service.user.name}>在脉脉上无<{pid}>岗位', active=True)
                        continue
                    except Exception as e:
                        exceptions.append(e)
                        if _CONFIG['dev']:
                            traceback.print_exc()
                        continue

                    j += 1
                    tmp_uids = uids[j * limit_per_user:(j + 1) * limit_per_user]

                resp = ah_io.h5_ai_add_count(pid, count_conversations=succ_count)

        self.logger.write_line(f'一次激活完成, <{pids}>岗位h5post发起会话数+{succ_count}', active=True)

        df.to_excel(excel_path, index=False)

        return succ_count, rows, exceptions

    @staticmethod
    def _find_vx_from_dialogs(dialogs: iter):
        for dialog in dialogs:
            vx = _extract_wechat_from_dialog(dialog)
            if vx:
                return vx
        return None

    @staticmethod
    def _find_mobile_from_dialogs(dialogs: iter):
        for dialog in dialogs:
            mobile = _extract_phone_from_dialog(dialog)
            if mobile:
                return mobile
        return None

    @staticmethod
    def _find_jname_from_dialogs(dialogs: iter):
        for dialog in dialogs:
            center = (dialog.get('common_card') or {}).get('center') or {}
            title = center.get('title')
            if dialog.get('type') == 124 and title:
                return title
        return None

    @staticmethod
    def _parse_pid_from_job_card(dialog, job_dict):
        """从单条职位卡片标题提取当前在招岗位 pid。"""
        center = (dialog.get('common_card') or {}).get('center') or {}
        title = center.get('title') or ''
        if not title:
            return None
        for pid in reversed(re.findall(r'\d+', title)):
            if pid in job_dict:
                return pid
        return None

    @classmethod
    def _collect_pids_from_job_cards(cls, dialogs, job_dict):
        pids = []
        seen = set()
        for dialog in dialogs:
            pid = cls._parse_pid_from_job_card(dialog, job_dict)
            if pid and pid not in seen:
                seen.add(pid)
                pids.append(pid)
        return pids

    @staticmethod
    def _candidate_texts_from_dialog(dialog):
        center = (dialog.get('common_card') or {}).get('center') or {}
        return [
            dialog.get('text') or '',
            center.get('title') or '',
            center.get('content') or '',
        ]

    @staticmethod
    def _extract_pid_candidates_from_text(text, strict_context=False):
        if not text:
            return []
        text = str(text)
        pids = []
        if strict_context:
            patterns = [
                r'正在招[^，。！？\n]{0,40}?(\d{3,8})\s*人才',
                r'职位卡片[^，。！？\n]{0,40}?(\d{3,8})',
                r'岗位[^，。！？\n]{0,40}?(\d{3,8})',
            ]
            for pattern in patterns:
                pids.extend(re.findall(pattern, text))
        else:
            pids.extend(re.findall(r'(?<!\d)(\d{3,8})(?!\d)', text))

        result = []
        seen = set()
        for pid in pids:
            pid = str(pid)
            if pid not in seen:
                seen.add(pid)
                result.append(pid)
        return result

    @staticmethod
    def _match_pid_in_job_dict(blob, job_dict):
        if not blob:
            return None
        for pid, job in job_dict.items():
            position = getattr(job, 'position', '') or ''
            if position and position in blob:
                return str(pid)
            if re.search(rf'(?<!\d){re.escape(str(pid))}(?!\d)', blob):
                return str(pid)
        return None

    @staticmethod
    def _normalize_job_text(text):
        text = str(text or '')
        text = re.sub(r'\s+', '', text)
        return text

    @classmethod
    def _job_title_matches_active_job(cls, title, pid, job):
        title = cls._normalize_job_text(title)
        if not title:
            return False

        pid = str(pid)
        if re.search(rf'(?<!\d){re.escape(pid)}(?!\d)', title):
            return True

        position = cls._normalize_job_text(getattr(job, 'position', '') or '')
        if not position:
            return False

        position_without_pid = re.sub(rf'{re.escape(pid)}$', '', position)
        candidates = [position, position_without_pid]
        for candidate in candidates:
            if candidate and (candidate in title or title in candidate):
                return True
        return False

    @staticmethod
    def _job_card_title_from_dialog(dialog):
        if dialog.get('type') != 124:
            return ''
        center = (dialog.get('common_card') or {}).get('center') or {}
        title = center.get('title') or ''
        if not title:
            return ''
        if '简历' in title:
            return ''
        return title

    @staticmethod
    def _has_job_card(dialogs):
        for dialog in dialogs:
            if Manager._job_card_title_from_dialog(dialog):
                return True
        return False

    @staticmethod
    def _find_current_job_pid_from_dialogs(dialogs, job_dict):
        for dialog in dialogs:
            title = Manager._job_card_title_from_dialog(dialog)
            if not title:
                continue
            for pid, job in job_dict.items():
                if Manager._job_title_matches_active_job(title, pid, job):
                    return str(pid)
        return None

    @classmethod
    def _collect_history_pid_candidates(cls, dialogs):
        pids = []
        seen = set()

        def add(pid):
            pid = str(pid)
            if pid not in seen:
                seen.add(pid)
                pids.append(pid)

        for dialog in dialogs:
            if dialog.get('type') == 124:
                title = cls._job_card_title_from_dialog(dialog)
                for pid in cls._extract_pid_candidates_from_text(title):
                    add(pid)

        for dialog in dialogs:
            if not dialog.get('is_me'):
                continue
            for text in cls._candidate_texts_from_dialog(dialog):
                for pid in cls._extract_pid_candidates_from_text(text, strict_context=True):
                    add(pid)

        return pids

    def _is_uid_contacted_for_pid(self, pid, uid):
        contacted_uids = self.pid_candidate_contacted_sets.get(str(pid), set())
        return int(uid) in contacted_uids or str(uid) in contacted_uids

    def _contacted_pids_for_uid(self, uid, active_pids=None):
        uid = int(uid)
        if active_pids is not None:
            active_pids = set(map(str, active_pids))

        pids = []
        for pid, contacted_uids in self.pid_candidate_contacted_sets.items():
            pid = str(pid)
            if active_pids is not None and pid not in active_pids:
                continue
            if uid in contacted_uids or str(uid) in contacted_uids:
                pids.append(pid)
        return pids

    @staticmethod
    def _has_recruiter_outreach(dialogs):
        return any(d.get('is_me') and not _is_deleted_message(d) for d in dialogs)

    def _is_helper_initiated_conversation(self, uid, pid, dialogs):
        """仅处理一次激活/表格发起触达过的会话。"""
        if not self._has_recruiter_outreach(dialogs):
            return False
        if self._is_uid_contacted_for_pid(pid, uid):
            return True

        for dialog in dialogs:
            if not dialog.get('is_me'):
                continue
            if _is_deleted_message(dialog):
                continue
            if dialog.get('type') == 124 and dialog.get('common_card'):
                return True
            texts = self._candidate_texts_from_dialog(dialog)
            joined = '\n'.join(texts)
            if '正在招' in joined and ('简历' in joined or '人才' in joined):
                return True
            if '交换联系方式' in joined or '交换微信' in joined:
                return True
        return False

    @staticmethod
    def _dialog_reply_text(dialog):
        return _dialog_text_for_filter(dialog)

    @classmethod
    def _is_system_notice_dialog(cls, dialog):
        if dialog.get('type') == 99:
            return True
        if dialog.get('type') == 94:
            return True
        return False

    @classmethod
    def _is_candidate_reply_dialog(cls, dialog):
        if dialog.get('is_me'):
            return False
        if cls._is_system_notice_dialog(dialog):
            return False
        if _is_candidate_initiation_dialog(dialog):
            return False
        msg_type = dialog.get('type')
        if msg_type in MM_CANDIDATE_REPLY_TYPES:
            return bool(cls._dialog_reply_text(dialog)) or msg_type in (116, 123)
        return False

    @classmethod
    def _get_last_reply_turn(cls, dialogs):
        """
        判断当前是否该自动回复。
        返回 (last_relevant_dialog, speaker)，speaker 为 'candidate' 或 'me'。
        """
        for dialog in reversed(dialogs):
            if cls._is_system_notice_dialog(dialog):
                continue
            if dialog.get('is_me'):
                if dialog.get('type') == 0 or cls._dialog_reply_text(dialog):
                    return dialog, 'me'
                continue
            if cls._is_candidate_reply_dialog(dialog):
                return dialog, 'candidate'
        return None, None

    @staticmethod
    def _dialog_to_chat_line(dialog):
        if Manager._is_system_notice_dialog(dialog):
            return None
        if _is_deleted_message(dialog):
            return None
        text = _dialog_text_for_visible_history(dialog)
        msg_type = dialog.get('type')
        if msg_type == 0:
            if not text:
                return None
        elif msg_type in MM_CANDIDATE_REPLY_TYPES:
            if not text:
                text = '[卡片消息]'
        else:
            return None
        role = 'AI招聘官' if dialog.get('is_me') else '候选人'
        ts = datetime.fromtimestamp(dialog['uptimestamp']).strftime('%m月%d日 %H:%M')
        return f'[{ts}]\n{role}: {text}\n'

    @staticmethod
    def _conversation_cache_key(mm_user_id, mid):
        return f'{mm_user_id}:{mid}'

    def _remember_conversation_pid(self, mm_user_id, mid, pid):
        self.conversation_pid_cache[self._conversation_cache_key(mm_user_id, mid)] = str(pid)

    def _resolve_pid_for_msg(self, user_service, msg, dialogs):
        """
        解析会话岗位 pid：优先认缓存和职位卡片；如果脉脉未返回岗位卡片，
        则用本地一次激活触达记录兜底，仅在 uid 唯一对应一个在招 pid 时使用。
        """
        uid = int(msg['u2']['id'])
        job_dict = user_service.user.job_dict
        key = self._conversation_cache_key(user_service.user.id, msg['id'])

        current_job_pid = self._find_current_job_pid_from_dialogs(dialogs, job_dict)
        if current_job_pid:
            self._remember_conversation_pid(user_service.user.id, msg['id'], current_job_pid)
            return current_job_pid

        has_job_card = self._has_job_card(dialogs)
        history_pids = self._collect_history_pid_candidates(dialogs)
        active_history_pids = [pid for pid in history_pids if pid in job_dict]
        if len(active_history_pids) == 1:
            pid = active_history_pids[0]
            self.logger.write_line(
                f'会话<{msg["u2"]["name"]}>按历史职位卡片/招呼语解析岗位<{pid}>', active=True)
            self._remember_conversation_pid(user_service.user.id, msg['id'], pid)
            return pid

        if has_job_card:
            self.logger.write_line(
                f'会话<{msg["u2"]["name"]}>职位卡片未匹配当前在招岗位，跳过缓存/触达兜底', active=True)
            return None

        cached = self.conversation_pid_cache.get(key)
        if cached and cached in job_dict and self._is_uid_contacted_for_pid(cached, uid):
            return str(cached)

        card_pids = self._collect_pids_from_job_cards(dialogs, job_dict)
        contacted_pids = [p for p in card_pids if self._is_uid_contacted_for_pid(p, uid)]

        if contacted_pids:
            contacted_set = set(contacted_pids)
            pid = next(p for p in reversed(card_pids) if p in contacted_set)
            self._remember_conversation_pid(user_service.user.id, msg['id'], pid)
            return pid

        active_contacted_pids = self._contacted_pids_for_uid(uid, active_pids=job_dict.keys())
        if len(active_contacted_pids) == 1:
            pid = active_contacted_pids[0]
            self.logger.write_line(
                f'会话<{msg["u2"]["name"]}>未取到岗位卡片，按触达记录匹配岗位<{pid}>', active=True)
            self._remember_conversation_pid(user_service.user.id, msg['id'], pid)
            return pid

        return None

    def _dump_pid_resolution_debug(self, user_service, msg, dialogs):
        try:
            debug_dir = os.path.join(SAVE_FILE_DIR, 'pid_resolution_debug')
            os.makedirs(debug_dir, exist_ok=True)

            uid = msg.get('u2', {}).get('id')
            name = msg.get('u2', {}).get('name', '')
            mid = msg.get('id')
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_name = re.sub(r'[^\w.-]+', '_', str(name))[:40] or 'unknown'
            filename = f'{ts}_{user_service.user.id}_{mid}_{uid}_{safe_name}.json'
            path = os.path.join(debug_dir, filename)

            job_dict = {
                str(pid): {
                    'pid': str(pid),
                    'position': getattr(job, 'position', None),
                    'jid': getattr(job, 'jid', None),
                    'ejid': getattr(job, 'ejid', None),
                }
                for pid, job in user_service.user.job_dict.items()
            }
            dialog_summaries = []
            for dialog in dialogs:
                center = (dialog.get('common_card') or {}).get('center') or {}
                dialog_summaries.append({
                    'id': dialog.get('id'),
                    'type': dialog.get('type'),
                    'is_me': dialog.get('is_me'),
                    'text': dialog.get('text'),
                    'center_title': center.get('title'),
                    'center_content': center.get('content'),
                    'has_common_card': bool(dialog.get('common_card')),
                })

            payload = {
                'reason': 'auto_reply_pid_resolution_failed',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'mm_account': {
                    'id': user_service.user.id,
                    'name': user_service.user.name,
                },
                'message': msg,
                'active_jobs': job_dict,
                'contacted_pids_for_uid': self._contacted_pids_for_uid(
                    uid, active_pids=user_service.user.job_dict.keys()) if uid is not None else [],
                'conversation_pid_cache_key': self._conversation_cache_key(user_service.user.id, mid),
                'conversation_pid_cache_value': self.conversation_pid_cache.get(
                    self._conversation_cache_key(user_service.user.id, mid)),
                'dialog_summaries': dialog_summaries,
                'dialogs': dialogs,
            }

            with open(path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
            self.logger.write_line(f'岗位解析诊断已导出：{path}', active=True)
        except Exception as e:
            self.logger.write_line(f'岗位解析诊断导出失败: {e}', active=True)
            if _CONFIG['dev']:
                traceback.print_exc()

    def _skip_auto_reply_msg(self, user_service, msg, dialogs, reason, mark_read=True):
        name = msg['u2']['name']
        self.logger.write_line(f'跳过<{name}>, {reason}', active=True)
        if mark_read:
            self._read_msg_safe(user_service, msg['id'], dialogs, name)

    def second_contact(self, user_ids=None, reply_mode='all', position_id=None):
        with self._lock:
            self.logger.write_line(f'开始二次激活 mode={reply_mode}', active=True)

            succ_count_dict = {}
            tmp_pid_position_dict = dict()

            user_services = self.user_services.values()
            if user_ids:
                user_services = [service for service in user_services if service.user.id in user_ids]

            for user_service in user_services:
                succ_count_dict[user_service.user.name] = 0
                msgs = user_service.get_msgs()
                msgs_unread = user_service.get_msgs(only_unread=True)
                msg_ids_unread = [item['id'] for item in msgs_unread]
                msgs = filter(lambda x: x['id'] not in msg_ids_unread, msgs)
                one_week_ago = datetime.now() - timedelta(weeks=1)
                one_week_ago_ts = one_week_ago.timestamp()
                msgs = filter(lambda x: x['latest_dialog_timestamp'] > one_week_ago_ts, msgs)
                msgs = filter(lambda x: x['u2'].get('id', 0) not in MM_OFFICIAL_IDs, msgs)
                msgs = list(msgs)

                # for msg in tqdm(msgs, desc=user_service.user.name):
                for msg in msgs:
                    try:
                        random_sleep()

                        if user_service.get_mobile(msg['id']):
                            continue

                        dialogs = user_service.get_dialog(msg['id'])

                        if self._find_mobile_from_dialogs(dialogs) or self._find_vx_from_dialogs(dialogs):
                            continue

                        is_valid = True
                        contact_count = 0
                        me_msg_count = 0
                        is_candidate_job_expired = False
                        for dialog in dialogs:
                            #这里判断的是回复消息的类型是否是候选人或者是面试官
                            if dialog['type']:
                                continue
                            if dialog['type'] == 124:
                                job_title = dialog.get('common_card').get('center').get('title')
                                pid_group = re.search(r"\d+", job_title)
                                if not pid_group:
                                    is_candidate_job_expired = True
                                    continue
                                pid = pid_group.group()
                                if pid not in user_service.user.job_dict.keys():
                                    is_candidate_job_expired = True
                                    continue

                            if dialog['is_me']:
                                me_msg_count += 1
                                contact_count += 1
                                if contact_count > MM_SECOND_CONTACT_LIMIT:
                                    is_valid = False
                                    break
                            else:
                                is_valid = False
                                break

                        if is_candidate_job_expired:
                            self.logger.write_line(f'跳过<{msg['u2']['name']}>, 因为职位过期了', active=True)
                            continue

                        if is_valid and me_msg_count == 0:
                            is_valid = False

                        if not is_valid:
                            self.logger.write_line(f'跳过<{msg['u2']['name']}>, 因为已激活两次或已回复', active=True)
                            continue

                        jname = self._find_jname_from_dialogs(dialogs)
                        if not jname:
                            continue
                        pid_group = re.search(r"\d+",jname)
                        if not pid_group :
                            self.logger.write_line(f"跳过<{msg['u2']['name']}>, 因为无岗位 id",active=True)
                            continue
                        pid = pid_group.group()
                        if reply_mode == 'single' and str(pid) != str(position_id):
                            self.logger.write_line(
                                f'跳过<{msg["u2"]["name"]}>，会话岗位<{pid}>与选定岗位<{position_id}>不一致',
                                active=True)
                            continue
                        position: AHPosition
                        if pid in tmp_pid_position_dict:
                            position = tmp_pid_position_dict[pid]
                        else:
                            position = self.get_ah_position(pid)
                        if not position:
                            continue

                        try:
                            resume_info, resume_resp = user_service.get_resume(
                                msg['u2']['id'],
                                dialogs=dialogs,
                                candidate=msg['u2'],
                                with_response=True,
                            )
                        except Exception as e:
                            diagnostic = _resume_response_diagnostic(
                                None, getattr(e, 'resp', None))
                            diagnostic['error_type'] = type(e).__name__
                            diagnostic['error'] = _safe_diagnostic_text(e)
                            self.logger.write_line(
                                f'二次激活简历接口调用失败 '
                                f'account=<{user_service.user.name}> '
                                f'candidate=<{msg["u2"]["name"]}> '
                                f'uid_tail={str(msg["u2"]["id"])[-4:]} '
                                f'mid={msg["id"]} pid={pid} '
                                f'diagnostic={json.dumps(diagnostic, ensure_ascii=False)}',
                                active=True,
                            )
                            if _CONFIG['dev']:
                                traceback.print_exc()
                            continue

                        resume = resume_info.get('data') if isinstance(resume_info, dict) else None
                        if not resume:
                            diagnostic = _resume_response_diagnostic(resume_info, resume_resp)
                            self.logger.write_line(
                                f'二次激活简历接口缺少有效data，已跳过 '
                                f'account=<{user_service.user.name}> '
                                f'candidate=<{msg["u2"]["name"]}> '
                                f'uid_tail={str(msg["u2"]["id"])[-4:]} '
                                f'mid={msg["id"]} pid={pid} '
                                f'diagnostic={json.dumps(diagnostic, ensure_ascii=False)}',
                                active=True,
                            )
                            continue

                        resp = ah_io.duplicate_screening(position.pid,msg['u2']['id'], position.incharge_id)

                        data = decode_resp_json(resp)
                        if data['duplicate'] == 'yes':
                            chat_tag = _chat_tag_without_candidate_reply(dialogs=dialogs)
                            for record in data['records']:
                                resp = ah_io.update_screening_resume(record['id'], chat_tags=chat_tag)

                        resp = ah_io.h5_ai_update_status(pid,ah_io.ENUM_H5_AI_STATUS.ACTIVATING)

                        chat_history = ''
                        for dialog in dialogs:
                            if not dialog['type']:
                                chat_history += f'[{datetime.fromtimestamp(dialog['uptimestamp']).strftime('%m月%d日 %H:%M')}]\n{'AI招聘官' if dialog['is_me'] else '候选人'}: {dialog['text']}\n'

                        payload = position.second_requirement + '以下是候选人信息:' + json.dumps(resume_info, ensure_ascii=False) + '以下是历史聊天记录:' + chat_history
                        resp = bot_io.send(payload, ENUM_MODEL_ID.SECOND_CONTACT_MSG_GEN.value)
                        data = decode_resp_json(resp)
                        new_text = data['choices'][0]['message']['content']

                        user_service.add_dialog(msg['id'], new_text)
                        succ_count_dict[user_service.user.name] += 1
                        self.logger.write_line(f'<{user_service.user.name}> 成功二次激活 <{msg['u2']['name']}>',
                                               active=True)
                    except Exception as e:
                        self.logger.write_line(f"<{msg['u2']['name']}>有问题，被抛出")
                        traceback.print_exc()
                        continue

            self.logger.write_line(f'二次激活完成', active=True)
            for k, v in succ_count_dict.items():
                self.logger.write_line(f'{k}: {v}', active=True)

        return succ_count_dict

    def _auto_reply(self, user_ids=None):
        # with self._lock:
        # exceptions = []

        user_services = list(self.user_services.values())
        if user_ids:
            user_services = [service for service in user_services if service.user.id in user_ids]

        if not user_services:
            self.logger.write_line('自动回复：无匹配脉脉账号，请确认左侧已勾选且已登录', active=True)
            return

        tmp_pid_position_dict = dict()
        total_unread = 0

        for user_service in user_services:
            user_service: UserService
            try:
                user_service.refresh()
            except CookiesExpiredException:
                self.logger.write_line(
                    f'跳过账号<{user_service.user.name}>, Cookie已失效，请重新登录', active=True)
                continue

            msgs = user_service.get_msgs(only_unread=True)
            msgs = filter(lambda x: x['u2'].get('id', 0) not in MM_OFFICIAL_IDs, msgs)
            msgs = list(msgs)
            total_unread += len(msgs)
            self.logger.write_line(
                f'账号<{user_service.user.name}> 未读会话 {len(msgs)} 条', active=True)

            # for msg in tqdm(msgs, desc=user_service.user.name):
            for msg in msgs:
                random_sleep()
                name = msg['u2'].get('name', '')
                if name in MM_SKIP_MSG_NAMES:
                    dialogs = user_service.get_dialog(msg['id'])
                    self._skip_auto_reply_msg(user_service, msg, dialogs, '系统/营销消息')
                    continue

                dialogs = user_service.get_dialog(msg['id'])
                if not dialogs:
                    self._skip_auto_reply_msg(user_service, msg, dialogs, '无聊天记录')
                    continue

                _, speaker = self._get_last_reply_turn(dialogs)
                if not speaker:
                    self._skip_auto_reply_msg(
                        user_service, msg, dialogs, '无候选人回复（仅系统通知或未读卡片）')
                    continue
                if speaker == 'me':
                    self._skip_auto_reply_msg(user_service, msg, dialogs, '最后一条为我方消息')
                    continue

                last_did = dialogs[-1]['last_did']
                pid = self._resolve_pid_for_msg(user_service, msg, dialogs)
                if not pid:
                    self._dump_pid_resolution_debug(user_service, msg, dialogs)
                    self._skip_auto_reply_msg(user_service, msg, dialogs, '无法解析岗位', mark_read=False)
                    continue
                if pid not in user_service.user.job_dict.keys():
                    self._skip_auto_reply_msg(
                        user_service, msg, dialogs, f'职位<{pid}>已下线或不在当前在招列表')
                    continue

                if not self._is_helper_initiated_conversation(msg['u2']['id'], pid, dialogs):
                    self._skip_auto_reply_msg(user_service, msg, dialogs, '非 helper 发起会话')
                    continue

                position: AHPosition
                if pid in tmp_pid_position_dict:
                    position = tmp_pid_position_dict[pid]
                else:
                    position = self.get_ah_position(pid)
                    if position:
                        tmp_pid_position_dict[pid] = position
                if not position:
                    self._skip_auto_reply_msg(user_service, msg, dialogs, f'获取岗位<{pid}>信息失败', mark_read=False)
                    continue

                self._remember_conversation_pid(user_service.user.id, msg['id'], pid)

                resp = ah_io.h5_ai_update_status(pid, ah_io.ENUM_H5_AI_STATUS.REPLYING)

                try:
                    resume_result = user_service.get_resume(
                        msg['u2']['id'], dialogs=dialogs, candidate=msg['u2'])
                except Exception:
                    self._skip_auto_reply_msg(
                        user_service, msg, dialogs, '获取简历失败', mark_read=False)
                    if _CONFIG['dev']:
                        traceback.print_exc()
                    continue
                resume = resume_result.get('data') if isinstance(resume_result, dict) else None
                if not isinstance(resume, dict) or not resume:
                    self._skip_auto_reply_msg(
                        user_service, msg, dialogs, '无法获取有效简历', mark_read=False)
                    continue
                resume_limited = bool(resume_result.get('resume_limited'))
                resume_name = resume.get('name') or msg['u2']['name']
                resume_company = resume.get('company', '')

                resume_file_url = resume.get('resume', {}).get('file_url', None)
                # resume_file = None
                if resume_file_url:
                    resume_file_bytes_io = stream_download(resume_file_url)
                    with open(os.path.join(SAVE_FILE_DIR, f'{resume_name}_{resume_company}.pdf'), 'wb') as f:
                        f.write(resume_file_bytes_io.read())
                #     resume_file = resume_file_bytes_io.read()

                chat_history = ''
                for dialog in dialogs:
                    line = self._dialog_to_chat_line(dialog)
                    if line:
                        chat_history += line

                vx = _normalize_contact(self._find_vx_from_dialogs(dialogs))
                mobile = _normalize_contact(user_service.get_mobile(msg['id']))
                if not mobile:
                    mobile = self._find_mobile_from_dialogs(dialogs)

                payload = position.jd + '聊天上下文:\n' + chat_history
                payload += '\n对方已交换联系方式，请勿再索要联系方式\n' if vx or mobile else ''
                try:
                    resp = bot_io.send(payload, ENUM_MODEL_ID.AUTO_REPLY_MSG_GEN.value)
                    data = self._decode_resp_json(resp, f'自动回复AI<{name}>')
                    new_text = data['choices'][0]['message']['content']
                except InvalidRespJsonException:
                    self._skip_auto_reply_msg(user_service, msg, dialogs, 'AI自动回复接口返回异常')
                    continue
                except Exception as e:
                    self.logger.write_line(f'跳过<{name}>, AI自动回复生成失败: {e}', active=True)
                    if _CONFIG['dev']:
                        traceback.print_exc()
                    continue

                chat_history += f'\n脉脉账户: {user_service.user.name}'

                user_service.read_msg(msg['id'], last_did)
                last_did = user_service.add_dialog(msg['id'], new_text)
                # user_service.read_msg(msg['id'], last_did)

                # 脉脉unread字段失效
                # for dialog in dialogs:
                #     if not dialog['type']:
                #         if dialog['unread'] and not dialog['is_me']:
                #             resp = ah_io.h5_post(position.pid, '意向人选回复',
                #                                  f'{resume['name']} 发送消息: ' + dialog['text'])
                i = 1
                is_candidate_job_expired = False
                while i <= len(dialogs):
                    dialog = dialogs[-i]
                    if dialog['type']:
                        i += 1
                        continue
                    if dialog['is_me']:
                        break
                    else:
                        resp = ah_io.h5_post(position.pid, '意向人选回复',
                                             f'{resume_name} 发送消息: ' +
                                             _redact_contact_text(dialog['text']))
                    i += 1

                resp = ah_io.h5_ai_add_count(position.pid, count_replies=1)
                self.logger.write_line(f'检测到候选人 <{msg['u2']['name']}> 新消息, 已回复: {new_text}', active=True)
                self.logger.write_line(f'对<{position.name}>岗位发送h5post消息回复数+1', active=True)

                resp = ah_io.duplicate_screening(position.pid, msg['u2']['id'] ,incharge_id=position.incharge_id)
                data = decode_resp_json(resp)
                if data['duplicate'] == 'yes':
                    self.logger.write_line(f'<{msg['u2']['name']}>高潜人才查重重复，更新聊天记录', active=True)
                    records = data['records']
                    candidate_tags = _chat_tag_without_candidate_reply(chat_history, dialogs)
                    if candidate_tags is None:
                        try:
                            resp = bot_io.send(chat_history, ENUM_MODEL_ID.CANDIDATE_TAGS_GEN.value)
                            data = self._decode_resp_json(resp, f'候选人标签AI<{name}>')
                            candidate_tags = [obj['message']['content'] for obj in data['choices']]
                            candidate_tags = ','.join(candidate_tags)
                        except Exception as e:
                            candidate_tags = ''
                            self.logger.write_line(f'<{name}>候选人标签生成失败，仅同步聊天记录: {e}', active=True)
                            if _CONFIG['dev']:
                                traceback.print_exc()

                    for record in records:
                        update_kwargs = {
                            'chat_history': chat_history,
                            'chat_tags': candidate_tags,
                        }
                        if mobile:
                            update_kwargs['phone'] = mobile
                        if vx:
                            update_kwargs['wechat'] = vx
                        resp = ah_io.update_screening_resume(record['id'], **update_kwargs)

                if mobile or vx:
                    self.logger.write_line(f'<{msg['u2']['name']}>检测到联系方式', active=True)
                    uid = msg['u2']['id']
                    blocked, block_reason = self._is_intent_upload_blocked(
                        position.pid, uid, mobile, vx, position.incharge_id,
                    )
                    if blocked and block_reason != '意向人才查重重复':
                        self.logger.write_line(
                            f'<{msg['u2']['name']}>{block_reason}，跳过加入待上传队列', active=True)
                        self._remove_candidate_from_queue(uid, msg['u2']['name'], block_reason)
                    elif blocked:
                        self.logger.write_line(
                            f'<{msg['u2']['name']}>意向人才查重重复，更新聊天记录', active=True)
                        resp = ah_io.duplicate(incharge_id=position.incharge_id, mobile=mobile, vx=vx)
                        data = decode_resp_json(resp)
                        for record in data['data']:
                            resp = ah_io.update_chat_history(record['id'], chat_history)

                            try:
                                resp = bot_io.send(chat_history, ENUM_MODEL_ID.GET_TAG_BY_CHAT_HISTORY)
                                data = self._decode_resp_json(resp, f'聊天状态标签AI<{name}>')
                                status_tags = data['choices'][0]['message']['content']
                                resp = ah_io.update_resume(record['id'], status_tags=status_tags)
                            except Exception as e:
                                self.logger.write_line(f'<{name}>聊天状态标签生成失败，仅更新聊天记录: {e}', active=True)
                                if _CONFIG['dev']:
                                    traceback.print_exc()
                        self._remove_candidate_from_queue(uid, msg['u2']['name'], '意向人才查重重复')
                    else:
                        if resume_limited:
                            self.logger.write_line(
                                f'<{msg['u2']['name']}>仅获取到有限公开资料，跳过加入待上传队列',
                                active=True)
                            continue
                        incharge_mm_acc = user_service.user.name
                        incharge_mm_acc = (incharge_mm_acc[:len(incharge_mm_acc) // 2] +
                                           '*' * (len(incharge_mm_acc) // 2))
                        job_preferences = resume.get('job_preferences')
                        salary = (job_preferences.get('salary')
                                  if isinstance(job_preferences, dict) else None)
                        if salary:
                            try:
                                resp = bot_io.send(salary, ENUM_MODEL_ID.GET_CLEAN_SALARY.value)
                                data = self._decode_resp_json(resp, f'薪资清洗AI<{name}>')
                                salary = data['choices'][0]['message']['content']
                            except Exception as e:
                                self.logger.write_line(f'<{name}>薪资清洗失败，继续加入上传队列: {e}', active=True)
                                if _CONFIG['dev']:
                                    traceback.print_exc()
                                salary = None

                        self.candidates[uid] = {
                            'uid': uid,
                            'resume': resume,
                            'mobile': mobile,
                            'vx': vx,
                            'chat_history': chat_history,
                            'position': position,
                            'incharge_mm_acc': incharge_mm_acc,
                            'salary': salary,
                        }

                        self._persist_manager()
                        self.logger.write_line(
                            f'<{msg['u2']['name']}>已加入待上传队列，manager.pkl已自动保存',
                            active=True)

        if total_unread == 0:
            self.logger.write_line('本轮无未读会话，5 分钟后再次检查', active=True)

        # return candidates, exceptions

    def _upload_resume(self, candidate):
        uid = candidate.get('uid')
        pid = candidate['position'].pid
        name = candidate.get('resume', {}).get('name', '')
        mobile = _normalize_contact(candidate.get('mobile'))
        vx = _normalize_contact(candidate.get('vx'))
        chat_history = _redact_contact_text(candidate.get('chat_history', ''))

        if uid is not None:
            blocked, reason = self._is_intent_upload_blocked(
                pid, uid, mobile, vx, candidate['position'].incharge_id,
            )
            if blocked:
                self.logger.write_line(f'跳过上传：<{name}>{reason}', active=True)
                return 'skipped'

        resp = bot_io.send(json.dumps(candidate['resume'], ensure_ascii=False), ENUM_MODEL_ID.RESUME_TRANSLATOR.value)
        data = self._decode_resp_json(resp, f'简历翻译AI<{name}>')
        resume = _redact_contact_text(data['choices'][0]['message']['content'])
        resp = bot_io.send(f'【个人信息:{resume}】\n【岗位需求:{candidate['position'].requirement}】',
                           ENUM_MODEL_ID.MATCH_CHECK_FIRST.value)
        data = self._decode_resp_json(resp, f'一轮匹配AI<{name}>')
        result = data['choices'][0]['message']['content']
        resp = bot_io.send(f'【个人信息:{resume}】\n【岗位需求:{candidate['position'].requirement}】【判断:{result}】',
                           ENUM_MODEL_ID.MATCH_CHECK_SECOND.value)
        data = self._decode_resp_json(resp, f'二轮匹配AI<{name}>')
        comment = data['choices'][0]['message']['content']

        resp = ah_io.h5_ai_update_status(candidate['position'].pid,
                                         ah_io.ENUM_H5_AI_STATUS.RESUME_UPDATING_SCREENING)

        status = '待筛选' if (('不匹配' in comment) or ('不确定' in comment)) else '初审待定'

        resp = bot_io.send(chat_history, ENUM_MODEL_ID.GET_TAG_BY_CHAT_HISTORY.value)
        data = self._decode_resp_json(resp, f'聊天状态标签AI<{name}>')
        status_tags = data['choices'][0]['message']['content']

        coin_cost = _compute_resume_coin_cost(comment, chat_history, status_tags)

        recommend_by = candidate['position'].incharge_id
        resp = ah_io.get_user_role(recommend_by)
        data = decode_resp_json(resp)
        user_id = recommend_by if data['type'] == 'client' else 834

        comment = '，'.join(comment.split('，')[2:])
        comment = comment.replace('确实', '').replace('判断结果应为', '').replace('不匹配', '一般匹配')
        comment = _redact_contact_text(comment)
        # comment += f'\n脉脉账户: {candidate.get('incharge_mm_acc', '')}'

        resume = self._inject_contact_into_resume_text(resume, mobile, vx)

        resp = ah_io.add_resume(candidate['position'].pid, resume, status_tags=status_tags, comment=comment,
                                chat_history=chat_history, coins_cost=coin_cost,
                                recommend_by=recommend_by, user_id=user_id, status=status, resume_tags=254,
                                expect_salary=candidate['salary'])

        if not getattr(resp, 'text', ''):
            raise RuntimeError('AnyHelper新增简历接口返回为空')
        if uid is not None:
            self._mark_intent_uploaded(pid, uid)
        company = candidate['resume'].get('company', '')
        resume_name = candidate['resume'].get('name', name)
        ah_io.h5_post(candidate['position'].pid, '意向人选上传',
                      f'来自{company}的{resume_name}已上传系统中')
        self.logger.write_line(f'来自{company}的{resume_name}已上传系统中', active=True)
        return 'uploaded'

    @staticmethod
    def _format_chat_history(dialogs):
        chat_history = ''
        for dialog in dialogs:
            msg_type = dialog.get('type')
            if msg_type not in (0, 123):
                continue
            if msg_type == 123 and _dialog_text_for_visible_history(dialog) not in (
                    _CONTACT_EXCHANGE_TEXT, _CONTACT_REQUEST_TEXT):
                continue
            line = Manager._dialog_to_chat_line(dialog)
            if line:
                chat_history += line
        return chat_history

    @staticmethod
    def _extract_phone_from_resume_data(resume_data):
        if not resume_data:
            return None

        def collect_strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for item in value.values():
                    yield from collect_strings(item)
            elif isinstance(value, list):
                for item in value:
                    yield from collect_strings(item)

        for text in collect_strings(resume_data):
            match = _PHONE_PATTERN.search(text)
            if match:
                return match.group(0)
        return None

    @staticmethod
    def _masked_mm_account_name(user_service):
        name = user_service.user.name
        half = len(name) // 2
        return name[:half] + '*' * half

    def _clean_expect_salary(self, resume):
        salary = resume.get('job_preferences', {}).get('salary')
        if not salary:
            return None
        resp = bot_io.send(salary, ENUM_MODEL_ID.GET_CLEAN_SALARY.value)
        data = decode_resp_json(resp)
        return data['choices'][0]['message']['content']

    def _get_resume_with_retry(self, user_service, uid, dialogs=None, candidate=None, retries=3):
        for _ in range(retries):
            random_sleep()
            try:
                result = user_service.get_resume(
                    uid, dialogs=dialogs, candidate=candidate)
                if result.get('data'):
                    return result
            except Exception:
                if _CONFIG['dev']:
                    traceback.print_exc()
            self.logger.write_line(f'重试获取 uid={uid} 简历', active=True)
        return None

    def _screening_record_for_current_position(self, records, pid):
        for record in records or []:
            if str(record.get('position_id')) == str(pid):
                return record
        return None

    def _sync_screening_chat_if_current_position(self, position, uid, name, chat_history, dialogs=None):
        chat_history = _redact_contact_text(chat_history)
        try:
            resp = ah_io.duplicate_screening(position.pid, uid, incharge_id=position.incharge_id)
            data = decode_resp_json(resp)
            if data.get('duplicate') != 'yes':
                return False

            record = self._screening_record_for_current_position(data.get('records'), position.pid)
            if not record:
                return False

            candidate_tags = _chat_tag_without_candidate_reply(chat_history, dialogs)
            if candidate_tags is None:
                resp = bot_io.send(chat_history, ENUM_MODEL_ID.CANDIDATE_TAGS_GEN.value)
                data = decode_resp_json(resp)
                candidate_tags = ','.join(obj['message']['content'] for obj in data['choices'])
            ah_io.update_screening_resume(record['id'], chat_history=chat_history, chat_tags=candidate_tags)
            self.logger.write_line(
                f'候选人<{name}>无联系方式，已同步高潜聊天记录（screening_id={record["id"]}）', active=True)
            return True
        except Exception as e:
            self.logger.write_line(f'候选人<{name}>高潜同步失败: {e}', active=True)
            if _CONFIG['dev']:
                traceback.print_exc()
            return False

    @staticmethod
    def _read_msg_safe(user_service, mid, dialogs, name):
        if not dialogs:
            return
        last_did = dialogs[-1].get('last_did')
        if not last_did:
            return
        try:
            user_service.read_msg(mid, last_did)
        except Exception as e:
            logging.getLogger(__name__).warning('read_msg failed for <%s>: %s', name, e)

    def _update_intent_duplicate(self, position, mobile, vx, chat_history, name):
        chat_history = _redact_contact_text(chat_history)
        resp = ah_io.duplicate(incharge_id=position.incharge_id, mobile=mobile, vx=vx)
        data = decode_resp_json(resp)
        for record in data.get('data', []):
            ah_io.update_chat_history(record['id'], chat_history)
            resp = bot_io.send(chat_history, ENUM_MODEL_ID.GET_TAG_BY_CHAT_HISTORY.value)
            tag_data = decode_resp_json(resp)
            status_tags = tag_data['choices'][0]['message']['content']
            ah_io.update_resume(record['id'], status_tags=status_tags)
        self.logger.write_line(f'候选人<{name}>意向人才查重重复，已更新聊天记录', active=True)

    def _check_intent_duplicate_current_position(self, pid, incharge_id, mobile, vx):
        mobile = _normalize_contact(mobile)
        vx = _normalize_contact(vx)
        if not mobile and not vx:
            return False
        try:
            resp = ah_io.duplicate(incharge_id=incharge_id, mobile=mobile, vx=vx)
            data = decode_resp_json(resp)
        except Exception:
            return False
        if not int(data.get('duplicate', 0)):
            return False
        for record in data.get('data', []):
            if str(record.get('position_id', '')) == str(pid):
                return True
        return False

    def _find_intent_duplicate_current_position_record(self, pid, incharge_id, mobile, vx):
        mobile = _normalize_contact(mobile)
        vx = _normalize_contact(vx)
        if not mobile and not vx:
            return None
        try:
            resp = ah_io.duplicate(incharge_id=incharge_id, mobile=mobile, vx=vx)
            data = decode_resp_json(resp)
        except Exception:
            return None
        if not int(data.get('duplicate', 0)):
            return None
        for record in data.get('data', []):
            if str(record.get('position_id', '')) == str(pid):
                return record
        return None

    @staticmethod
    def _classify_saved_resume_status(comment):
        if ('不匹配' in comment) or ('不确定' in comment):
            return '待筛选'
        if ('非常匹配' in comment) or ('匹配' in comment):
            return '初审待定'
        return '待筛选'

    @staticmethod
    def _inject_contact_into_resume_text(resume_text, mobile=None, vx=None):
        mobile = _normalize_contact(mobile)
        vx = _normalize_contact(vx)
        if not mobile and not vx:
            return resume_text

        contact = '\n## 联系方式\n'
        if vx:
            contact += f'### 微信号: {vx}\n'
        if mobile:
            contact += f'### 手机号: {mobile}\n'

        parts = resume_text.split('---')
        if len(parts) > 1:
            parts.insert(1, contact)
            return '---'.join(parts)
        return contact + '\n' + resume_text

    def _resolve_pid_for_save_msg(self, user_service, msg, dialogs, active_pids, fixed_pid=None):
        uid = int(msg['u2']['id'])
        job_dict = user_service.user.job_dict
        key = self._conversation_cache_key(user_service.user.id, msg['id'])
        active_pids = set(map(str, active_pids))
        fixed_pid = str(fixed_pid) if fixed_pid else None

        cached = self.conversation_pid_cache.get(key)
        if cached and cached in active_pids and (not fixed_pid or cached == fixed_pid):
            return cached

        card_pids = self._collect_pids_from_job_cards(dialogs, job_dict)
        if fixed_pid:
            if fixed_pid in card_pids:
                self._remember_conversation_pid(user_service.user.id, msg['id'], fixed_pid)
                return fixed_pid
            if self._is_uid_contacted_for_pid(fixed_pid, uid):
                self._remember_conversation_pid(user_service.user.id, msg['id'], fixed_pid)
                return fixed_pid
            return None

        candidates = [pid for pid in card_pids if pid in active_pids]
        if candidates:
            pid = candidates[-1]
            self._remember_conversation_pid(user_service.user.id, msg['id'], pid)
            return pid

        contacted_pids = self._contacted_pids_for_uid(uid, active_pids=active_pids)
        if len(contacted_pids) == 1:
            pid = contacted_pids[0]
            self.logger.write_line(
                f'保存简历<{msg["u2"]["name"]}>未取到岗位卡片，按触达记录匹配岗位<{pid}>', active=True)
            self._remember_conversation_pid(user_service.user.id, msg['id'], pid)
            return pid

        return None

    def _save_resume_to_intent_library(self, user_service, msg, position, resume, mobile, vx, chat_history):
        uid = msg['u2']['id']
        name = msg['u2']['name']
        mobile = _normalize_contact(mobile)
        vx = _normalize_contact(vx)
        chat_history = _redact_contact_text(chat_history)

        resp = bot_io.send(json.dumps(resume, ensure_ascii=False), ENUM_MODEL_ID.RESUME_TRANSLATOR.value)
        data = self._decode_resp_json(resp, f'保存简历翻译AI<{name}>')
        resume_text = _redact_contact_text(data['choices'][0]['message']['content'])

        resp = bot_io.send(f'【个人信息:{resume_text}】\n【岗位需求:{position.requirement}】',
                           ENUM_MODEL_ID.MATCH_CHECK_FIRST.value)
        data = self._decode_resp_json(resp, f'保存简历一轮匹配AI<{name}>')
        first_result = data['choices'][0]['message']['content']

        resp = bot_io.send(f'【个人信息:{resume_text}】\n【岗位需求:{position.requirement}】【判断:{first_result}】',
                           ENUM_MODEL_ID.MATCH_CHECK_SECOND.value)
        data = self._decode_resp_json(resp, f'保存简历二轮匹配AI<{name}>')
        raw_comment = data['choices'][0]['message']['content']
        status = self._classify_saved_resume_status(raw_comment)

        comment = '，'.join(raw_comment.split('，')[2:])
        comment = comment.replace('确实', '').replace('判断结果应为', '')
        if not comment.strip():
            comment = raw_comment
        comment = comment.replace('不匹配', '一般匹配')
        comment = _redact_contact_text(comment)

        resp = bot_io.send(chat_history, ENUM_MODEL_ID.GET_TAG_BY_CHAT_HISTORY.value)
        data = self._decode_resp_json(resp, f'保存简历聊天状态标签AI<{name}>')
        status_tags = data['choices'][0]['message']['content']

        existing_record = self._find_intent_duplicate_current_position_record(
            position.pid, position.incharge_id, mobile, vx)
        if existing_record:
            ah_io.update_chat_history(existing_record['id'], chat_history)
            ah_io.update_resume(
                existing_record['id'], status_tags=status_tags, status=status, comment=comment)
            self.logger.write_line(
                f'候选人<{name}>意向库当前岗位已存在，已更新聊天记录、状态标签和状态：{status}', active=True)
            return 'updated_intent'

        if self._intent_upload_key(position.pid, uid) in self.intent_uploaded_keys:
            self.logger.write_line(f'候选人<{name}>本地已记录保存过，跳过新增', active=True)
            return 'already_saved'

        coin_cost = _compute_resume_coin_cost(raw_comment, chat_history, status_tags)
        recommend_by = position.incharge_id
        resp = ah_io.get_user_role(recommend_by)
        data = decode_resp_json(resp)
        user_id = recommend_by if data['type'] == 'client' else 834

        salary = None
        try:
            salary = self._clean_expect_salary(resume)
        except Exception:
            if _CONFIG['dev']:
                traceback.print_exc()

        resume_text = self._inject_contact_into_resume_text(resume_text, mobile, vx)

        resp = ah_io.add_resume(
            position.pid,
            resume_text,
            status_tags=status_tags,
            comment=comment,
            chat_history=f'{chat_history}\n脉脉账户: {user_service.user.name}',
            coins_cost=coin_cost,
            recommend_by=recommend_by,
            user_id=user_id,
            status=status,
            resume_tags=254,
            expect_salary=salary,
        )

        if resp.text:
            self._mark_intent_uploaded(position.pid, uid)
            ah_io.h5_post(position.pid, '保存简历',
                          f'来自{resume.get("company", "")}的{resume.get("name", name)}已保存，状态：{status}')
            self.logger.write_line(
                f'候选人<{name}>已保存到意向库，AI状态：{status}', active=True)
            return 'uploaded_intent'

        return 'skipped'

    def _upload_intent_from_save(self, user_service, msg, position, resume, mobile, vx, chat_history):
        uid = msg['u2']['id']
        name = msg['u2']['name']
        mobile = _normalize_contact(mobile)
        vx = _normalize_contact(vx)

        if self._sync_screening_chat_if_current_position(position, uid, name, chat_history):
            return 'synced_screening'

        if self._intent_upload_key(position.pid, uid) in self.intent_uploaded_keys:
            self.logger.write_line(f'<{name}>本地已记录上传过意向库，跳过', active=True)
            return 'skipped'

        if self._check_intent_duplicate_current_position(position.pid, position.incharge_id, mobile, vx):
            self._update_intent_duplicate(position, mobile, vx, chat_history, name)
            return 'updated_intent'

        salary = None
        try:
            salary = self._clean_expect_salary(resume)
        except Exception:
            if _CONFIG['dev']:
                traceback.print_exc()

        candidate = {
            'uid': uid,
            'resume': resume,
            'mobile': mobile,
            'vx': vx,
            'chat_history': f'{chat_history}\n脉脉账户: {user_service.user.name}',
            'position': position,
            'incharge_mm_acc': self._masked_mm_account_name(user_service),
            'salary': salary,
        }
        result = self._upload_resume(candidate)
        return 'uploaded_intent' if result == 'uploaded' else 'skipped'

    def _process_save_resume_msg(self, user_service, msg, reply_mode, active_pids, fixed_pid=None):
        name = msg['u2']['name']
        uid = msg['u2']['id']
        mid = msg['id']

        dialogs = user_service.get_dialog(mid)
        if not dialogs:
            self.logger.write_line(f'跳过<{name}>，无聊天记录', active=True)
            return 'skipped'

        pid = self._resolve_pid_for_save_msg(
            user_service, msg, dialogs, active_pids, fixed_pid=fixed_pid)
        if not pid:
            self.logger.write_line(
                f'跳过<{name}>，无法解析到目标岗位', active=True)
            return 'skipped'

        if reply_mode == 'single' and str(pid) != str(fixed_pid):
            self.logger.write_line(
                f'跳过<{name}>，会话岗位<{pid}>与选定岗位<{fixed_pid}>不一致', active=True)
            return 'skipped'

        if str(pid) not in active_pids:
            self.logger.write_line(f'跳过<{name}>，岗位<{pid}>不在在招列表', active=True)
            return 'skipped'

        if str(pid) not in user_service.user.job_dict:
            self.logger.write_line(f'跳过<{name}>，职位已过期', active=True)
            return 'skipped'

        position = self.get_ah_position(pid)
        if not position:
            return 'skipped'

        resume_result = self._get_resume_with_retry(
            user_service, uid, dialogs=dialogs, candidate=msg['u2'])
        if not resume_result:
            self.logger.write_line(f'跳过<{name}>，无法获取简历', active=True)
            return 'skipped'
        if resume_result.get('resume_limited'):
            self.logger.write_line(
                f'跳过<{name}>，仅获取到有限公开资料，未保存到意向库', active=True)
            return 'skipped'
        resume = resume_result['data']

        chat_history = self._format_chat_history(dialogs)
        if not chat_history.strip():
            self.logger.write_line(f'跳过<{name}>，无有效聊天记录', active=True)
            return 'skipped'

        try:
            mobile = _normalize_contact(user_service.get_mobile(mid))
        except Exception as e:
            self.logger.write_line(f'候选人<{name}>获取手机号失败: {e}', active=True)
            mobile = None
        if not mobile:
            mobile = self._find_mobile_from_dialogs(dialogs)
        if not mobile and _has_candidate_reply_in_chat(chat_history):
            mobile = _normalize_contact(self._extract_phone_from_resume_data(resume))
        vx = _normalize_contact(self._find_vx_from_dialogs(dialogs))
        if not mobile and not vx:
            self.logger.write_line(f'跳过<{name}>，无手机号或微信，不能保存到意向库', active=True)
            return 'skipped'

        result = self._save_resume_to_intent_library(
            user_service, msg, position, resume, mobile, vx, chat_history)
        self._read_msg_safe(user_service, mid, dialogs, name)
        return result or 'skipped'

    def save_resume(self, reply_mode, start_time, end_time, position_id=None, user_ids=None):
        with self._lock:
            if isinstance(start_time, str):
                start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            if isinstance(end_time, str):
                end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            end_time = end_time.replace(hour=23, minute=59, second=59)

            self.logger.write_line(
                f'开始保存简历 mode={reply_mode} range={start_time} ~ {end_time}', active=True)

            user_services = list(self.user_services.values())
            if user_ids:
                user_services = [s for s in user_services if s.user.id in user_ids]

            if reply_mode == 'single':
                if not position_id:
                    self.logger.write_line('单独岗位保存缺少 position_id', active=True)
                    return {'scanned': 0, 'succ_count': 0, 'skip_count': 0}

            stats = {'scanned': 0, 'succ_count': 0, 'skip_count': 0}
            succ_results = frozenset(('synced_screening', 'uploaded_intent', 'updated_intent', 'already_saved'))

            for user_service in user_services:
                active_pids = set(user_service.user.job_dict.keys())
                if reply_mode == 'single':
                    if str(position_id) not in active_pids:
                        self.logger.write_line(
                            f'账号<{user_service.user.name}>无岗位<{position_id}>，跳过', active=True)
                        continue
                    active_pids = {str(position_id)}

                msgs = user_service.get_all_msgs(only_unread=False)
                msgs_unread = user_service.get_msgs(only_unread=True)
                unread_ids = {item['id'] for item in msgs_unread}
                start_ts = start_time.timestamp()
                end_ts = end_time.timestamp()
                seen_mids = set()
                msg_candidates = []

                sorted_msgs = sorted(
                    msgs,
                    key=lambda x: x.get('latest_dialog_timestamp', 0),
                    reverse=True,
                )

                for msg in sorted_msgs:
                    if msg['u2'].get('id', 0) in MM_OFFICIAL_IDs:
                        continue
                    dt_ts = msg.get('latest_dialog_timestamp', 0)
                    if dt_ts > end_ts:
                        self.logger.write_line(
                            f"候选人{msg['u2']['name']}会话时间晚于结束时间，继续筛选历史会话", active=True)
                        continue
                    if dt_ts < start_ts:
                        break
                    if msg['id'] in unread_ids:
                        self.logger.write_line(
                            f"候选人{msg['u2']['name']}有未读消息被跳过", active=True)
                        continue
                    if msg['id'] in seen_mids:
                        continue
                    seen_mids.add(msg['id'])
                    msg_candidates.append(msg)

                self.logger.write_line(
                    f'账号<{user_service.user.name}>待处理会话 {len(msg_candidates)} 条', active=True)

                for msg in msg_candidates:
                    stats['scanned'] += 1
                    try:
                        random_sleep()
                        result = self._process_save_resume_msg(
                            user_service, msg, reply_mode, active_pids, fixed_pid=position_id)
                        if result in succ_results:
                            stats['succ_count'] += 1
                        else:
                            stats['skip_count'] += 1
                    except Exception as e:
                        stats['skip_count'] += 1
                        self.logger.write_line(
                            f'保存简历处理<{msg["u2"]["name"]}>失败: {e}', active=True)
                        if _CONFIG['dev']:
                            traceback.print_exc()

            self.logger.write_line(
                f'保存简历完成，扫描 {stats["scanned"]} 条，成功 {stats["succ_count"]} 条，跳过 {stats["skip_count"]} 条',
                active=True)
            return stats

    def _interruptible_sleep(self, seconds, owner_tid=None):
        """分段 sleep，便于 stop_auto_reply 及时生效且不长期占用 _lock。"""
        for _ in range(seconds):
            if not self._auto_reply_evt.is_set():
                return
            if owner_tid is not None and not self._is_auto_reply_owner(owner_tid):
                return
            time.sleep(1)

    def _is_auto_reply_owner(self, owner_tid):
        return self._auto_reply_owner_tid == owner_tid

    def process_auto_reply(self, user_ids=None):
        owner_tid = threading.get_ident()
        self._auto_reply_owner_tid = owner_tid
        self.logger.write_line('开始自动回复', active=True)

        self._auto_reply_evt.set()
        while self._auto_reply_evt.is_set() and self._is_auto_reply_owner(owner_tid):
            with self._lock:
                if not self._is_auto_reply_owner(owner_tid):
                    break
                try:
                    self._auto_reply(user_ids)
                except Exception as e:
                    self.logger.write_line(f'自动回复本轮异常，已保留后台线程继续下一轮: {e}', active=True)
                    if _CONFIG['dev']:
                        traceback.print_exc()
            if not self._auto_reply_evt.is_set() or not self._is_auto_reply_owner(owner_tid):
                break
            self.logger.write_line(f'自动回复本轮结束，暂停{AUTO_REPLY_SLEEP_TIME}s', active=True)
            self._interruptible_sleep(AUTO_REPLY_SLEEP_TIME, owner_tid=owner_tid)

        if self._is_auto_reply_owner(owner_tid):
            self._auto_reply_owner_tid = None
        self.logger.write_line('自动回复结束', active=True)

    def stop_auto_reply(self):
        self._auto_reply_evt.clear()

    def is_auto_reply(self):
        return self._auto_reply_evt.is_set()

    def process_upload_resume(self):
        with self._lock:
            self.logger.write_line('开始上传简历', active=True)
            queued = len(self.candidates)
            purged = self._purge_stale_candidates()
            stats = {
                'queued': queued,
                'processed': 0,
                'succeeded': 0,
                'skipped': purged,
                'failed': 0,
                'remaining': 0,
            }
            failed_candidates = {}
            # bar = tqdm(desc='uploading', total=len(self.candidates))
            while self.candidates:
                key, candidate = self.candidates.popitem()
                if candidate.get('uid') is None:
                    candidate['uid'] = key
                stats['processed'] += 1
                try:
                    result = self._upload_resume(candidate)
                    if result == 'uploaded':
                        stats['succeeded'] += 1
                    else:
                        stats['skipped'] += 1
                    # bar.update(1)
                except Exception as e:
                    failed_candidates[key] = candidate
                    stats['failed'] += 1
                    name = candidate.get('resume', {}).get('name', key)
                    self.logger.write_line(
                        f'上传简历失败：<{name}> {e}，已保留在待上传队列，继续处理其他候选人',
                        active=True,
                    )
                    if _CONFIG['dev']:
                        traceback.print_exc()
                    continue
            self.candidates.update(failed_candidates)
            stats['remaining'] = len(self.candidates)
            if queued:
                self._persist_manager()
            if failed_candidates:
                self.logger.write_line(
                    f'本轮上传有 {len(failed_candidates)} 位候选人失败，已保留到下次重试',
                    active=True,
                )
            self.logger.write_line(
                f'上传简历结束，队列 {stats["queued"]} 位，成功 {stats["succeeded"]} 位，'
                f'跳过 {stats["skipped"]} 位，失败 {stats["failed"]} 位，'
                f'剩余 {stats["remaining"]} 位',
                active=True)
            return stats

    def export_cookies(self):
        with self._lock:
            r = {}
            for user_service in self.user_services.values():
                user_service: UserService
                r[user_service.user.name] = user_service.export_cookies()
            return r

    def login_by_chrome(self):
        with self._lock:
            cookies = mm_c.login()
        self.update_user(cookies)

    def auto_process_all(self, **kwargs):
        options = kwargs.get('options', '')
        options = options.split(',')
        user_ids = list(map(int, kwargs['user_ids'].split(',')))

        if 'first_contact' in options:
            search_condition_ids = list(map(int, kwargs['search_condition_ids'].split(',')))
            self.first_contact(kwargs['pid'], search_condition_ids, kwargs['greet_text'],
                               limit_per_user=int(kwargs['limit_per_user']), user_ids=user_ids)
        if 'first_contact_with_excel' in options:
            excel_name = kwargs.get('excel_name')
            excel_path = os.path.join(RSC_DIR, excel_name)
            self.first_contact_with_excel(excel_path,kwargs.get('greet_text'),limit_per_user=int(kwargs.get('limit_per_user')),user_ids=user_ids)

        if 'second_contact' in options:
            self.second_contact(user_ids=user_ids)
        if 'auto_reply' in options:
            tt = int(kwargs['auto_reply_stop_timestamp'][:10])
            threading.Thread(target=self.process_auto_reply, kwargs={'user_ids': user_ids}).start()

            while int(time.time()) < tt:
                time.sleep(10)
            self.stop_auto_reply()
        if 'upload_resume' in options:
            self.process_upload_resume()
        if 'save_resume' in options:
            start_time = kwargs.get('save_resume_start_time', '').strip()
            end_time = kwargs.get('save_resume_end_time', '').strip()
            if not start_time or not end_time:
                raise ValueError('全流程保存简历需要填写开始日期和结束日期')
            save_resume_time = kwargs.get('save_resume_time')
            if save_resume_time:
                tt = int(str(save_resume_time)[:10])
                while int(time.time()) < tt:
                    time.sleep(10)
                self.stop_auto_reply()
            save_pid = kwargs.get('pid')
            save_mode = kwargs.get('save_resume_mode', 'all')
            if save_mode == 'single' and kwargs.get('save_resume_position_id'):
                save_pid = kwargs.get('save_resume_position_id')
            self.save_resume(
                reply_mode=save_mode,
                start_time=start_time,
                end_time=end_time,
                position_id=save_pid,
                user_ids=user_ids,
            )

        self.logger.write_line('全流程已结束', active=True)
