import json
import random
import re
import time
from html import unescape
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from backend.core.api.anyJobApi import get_ah_result_dict, get_job_data, h5_ai_add_count, h5_post, \
    get_incharge_id_by_position_id
from backend.core.api.zhilian_api import get_candidate_list, get_resume, get_job_list, create_greet, get_session_list, \
    get_session_html, get_session_detail, get_session_resume, get_virtual_number, send_msg, send_sak_phone_msg, \
    send_ask_wx_msg, set_msg_read
from backend.core.config.chatBotApiConfig import ENUM_MODEL_ID
from backend.core.entity.candidate import Candidate
from tqdm import tqdm
from backend.core.entity.searchCondition import SearchCondition
from backend.core.entity.zhilian_search_condition import zhilian_search_conditon
from backend.core.logger.logger import get_logger
import backend.core.api.chatBotApi as chatBot
from backend.core.utils.msg.history_msg import CONTACT_HIDDEN_TEXT, candidate_sent_resume, get_clean_history_msg
from backend.core.utils.path_util import path_util
from backend.core.utils.regex.regex_utils import RegexUtils
from backend.core.utils.resume.clean_resume import select_field_in_resume

logger = get_logger(__name__)

PHONE_PATTERN = re.compile(r'(?<!\d)(1[3-9]\d{9})(?!\d)')
GOLD_COLLAR_LEVELS = {'GOLD', 'DIAMOND'}
UNKNOWN_ACCOUNT_NAME = '未知账号'
ZHILIAN_AUTH_ERROR_MESSAGE = (
    '智联登录已失效或触发安全认证，请先完成认证并重新导出 Cookie，然后重新执行任务'
)

# 会话聊天内容未返回（疑似被服务端限流/未渲染）时的退避重试与熔断参数
SESSION_CONTENT_MAX_RETRY = 2
SESSION_CONTENT_RETRY_GAP_MIN = 10
SESSION_CONTENT_RETRY_GAP_MAX = 20
SESSION_CONTENT_THROTTLE_ABORT = 5


class ZhilianAuthenticationError(RuntimeError):
    pass


class Manger:
    def __init__(self):
        self.first_conversation_count = 0
        self.pay_flag = False
        self.current_cookies = None
        self.current_job_number = ''
        self.current_candidate_list = []
        self.current_resume_list = []
        self.current_position = {}
        self.current_session_list = []
        self.session_number_hash = set()
        self.session_html_cache = {}

    def set_cookies(self, cookies_path):
        with open(cookies_path, 'r') as f:
            cookies = json.load(f)
        self.current_cookies = {cookie['name']: cookie['value'] for cookie in cookies}

    @staticmethod
    def _raise_if_zhilian_authentication_failed(response):
        try:
            payload = json.loads(response.text)
        except (TypeError, ValueError, AttributeError):
            return
        if isinstance(payload, dict) and str(payload.get('code')) == '401':
            raise ZhilianAuthenticationError(ZHILIAN_AUTH_ERROR_MESSAGE)

    def set_candidate_list(self, search_condition, page_no, page_size, need_clean=False):
        params = {
            'page_no': page_no,
            'page_size': page_size,
        }
        params.update(**search_condition.to_dict())
        response = get_candidate_list(self.current_cookies, **params)
        candidate_list = json.loads(response.text)['data']['list']
        if need_clean:
            job_requirement = get_ah_result_dict(get_job_data(self.current_position['position_id']))['results'][0][
                'summary']
            job_simple_check = job_requirement.split('初筛要求：')[1].split('深匹要求：')[0]
            resumeK_str = chatBot.send(
                f'【岗位要求：】{job_simple_check} 【简历列表：】{json.dumps(candidate_list, ensure_ascii=False)}',
                ENUM_MODEL_ID.GET_FIRST_CONVERSATION_SIMPLE_CHECK)
            check_resume_list = resumeK_str.split(',')
            for candidate in candidate_list:
                if candidate['resumeK'] in check_resume_list:
                    self.current_candidate_list = [*self.current_candidate_list, *candidate_list]

        else:
            self.current_candidate_list = [*self.current_candidate_list, *candidate_list]

    def set_resume_list(self):
        for candidate in tqdm(self.current_candidate_list):
            time.sleep(random.randrange(2, 4))
            params = {
                "cookies": self.current_cookies,
                "resume_number": candidate['resumeNumber'],
                'resume_K': candidate['resumeK'],
                'resume_T': candidate['resumeT'],
                'purpose_id': candidate['purposes'][0]['purposeId']
            }
            response = get_resume(**params)
            self.current_resume_list.append(json.loads(response.text)['data'])

    def get_page_count(self, search_condition):
        params = {
            'page_no': 1,
            'page_size': 20,
        }
        params.update(**search_condition.to_dict())
        total_count = json.loads(get_candidate_list(self.current_cookies, **params).text)['data']['total']
        page_count = int(total_count / 20) + 1
        return page_count

    def get_candidate_total(self, search_condition):
        params = {
            'page_no': 1,
            'page_size': 20,
        }
        params.update(**search_condition.to_dict())
        return json.loads(get_candidate_list(self.current_cookies, **params).text)['data']['total']

    def check_and_set_job(self, position_id, job_title_hint=None):
        response = get_job_list(self.current_cookies)
        self._raise_if_zhilian_authentication_failed(response)
        for _ in range(3):
            try:
                res_dict = response.json()
                if res_dict['data'][0]['jobNumbers']:
                    pass
                break
            except:
                logger.info(f'获取职位出错，进行重试,第{_+1}次')
                continue

        job_list = json.loads(response.text)['data']

        match_hints = []
        if job_title_hint not in (None, ''):
            match_hints.append(str(job_title_hint).strip())
        if position_id not in (None, ''):
            match_hints.append(str(position_id).strip())
        seen = set()
        match_hints = [hint for hint in match_hints if hint and not (hint in seen or seen.add(hint))]

        for hint in match_hints:
            for job in job_list:
                if hint in job['jobTitle']:
                    self.current_position["position_name"] = job['jobTitle']
                    self.current_job_number = job['jobNumbers'][0]
                    self.current_position["position_id"] = position_id
                    logger.info(f'匹配岗位成功: {job["jobTitle"]} (hint={hint})')
                    return True

        logger.info(f'账号下没有这个岗位, hints={match_hints}')
        return False

    def extract_phone_from_resume_remark(self, raw_resume_dict):
        text_candidates = []

        def collect_strings(value):
            if isinstance(value, str):
                text_candidates.append(value)
            elif isinstance(value, dict):
                for item in value.values():
                    collect_strings(item)
            elif isinstance(value, list):
                for item in value:
                    collect_strings(item)

        resume_session = raw_resume_dict.get('resumeSession') or {}
        collect_strings(resume_session)

        for text in text_candidates:
            match = PHONE_PATTERN.search(text)
            if match:
                return match.group(1)
        return ''

    def normalize_phone(self, value):
        """仅接受完整中国大陆手机号，屏蔽星号等脱敏值不会被误当作可用号码。"""
        digits = re.sub(r'\D', '', str(value or ''))
        if digits.startswith('86') and len(digits) == 13:
            digits = digits[2:]
        return digits if PHONE_PATTERN.fullmatch(digits) else ''

    def extract_available_phone(self, raw_resume_dict):
        raw_user = raw_resume_dict.get('user') or {}
        if not isinstance(raw_user, dict):
            raw_user = {}

        for field_name in ('phone', 'unlockedPhone'):
            phone = self.normalize_phone(raw_user.get(field_name))
            if phone:
                return phone
        return self.extract_phone_from_resume_remark(raw_resume_dict)

    def _get_cached_session_html(self, session):
        session_id = session['sessionId']
        if session_id not in self.session_html_cache:
            response = get_session_html(self.current_cookies, session_id)
            self._raise_if_zhilian_authentication_failed(response)
            self.session_html_cache[session_id] = response.text
        return self.session_html_cache[session_id]

    def _unread_session_contains_resume(self, session):
        """未读会话只在聊天正文确认已发送简历时放行。"""
        try:
            return candidate_sent_resume(self._get_cached_session_html(session))
        except ZhilianAuthenticationError:
            raise
        except Exception:
            logger.exception(
                f"检查未读会话简历消息失败，候选人：{session.get('name', '未知')}，"
                f"会话ID：{session.get('sessionId', '')}"
            )
            return False

    def _can_call_candidate(self, raw_resume_dict):
        return (
            raw_resume_dict.get('interactivePhoneButton') == 'CALL_NOW'
            and raw_resume_dict.get('viewPhoneButton') in {'NORMAL_PHONE', 'UNLOCKED_PHONE'}
        )

    def _get_phone_from_call_button(self, session):
        response = get_virtual_number(
            self.current_cookies,
            session['jobNumber'],
            session['resumeNumber'],
            session['resumeLanguage'],
        )
        self._raise_if_zhilian_authentication_failed(response)
        payload = json.loads(response.text)
        data = payload.get('data') or {}
        if isinstance(data, str):
            return self.normalize_phone(data)
        if isinstance(data, dict):
            for container in (data, data.get('user') or {}):
                if not isinstance(container, dict):
                    continue
                for field_name in ('phone', 'unlockedPhone', 'phoneNumber', 'virtualNumber'):
                    phone = self.normalize_phone(container.get(field_name))
                    if phone:
                        return phone
        return ''

    def get_conversation_rule_tag(self, session, clean_candidate_msg, phone='', wechat='', resume_shared=False):
        if phone or wechat or resume_shared:
            return '有意向沟通'
        if clean_candidate_msg:
            return ''

        response = get_session_detail(
            self.current_cookies,
            session['sessionId'],
            mark_read=False,
            include_resume_detail=False,
        )
        self._raise_if_zhilian_authentication_failed(response)
        payload = json.loads(response.text)
        detail = dict(session)
        detail.update(payload.get('data') or {})

        last_sentence = detail.get('lastSentence') or {}
        if isinstance(last_sentence, str):
            last_sentence = json.loads(last_sentence)
        if not isinstance(last_sentence, dict) or last_sentence.get('senderType') != 'STAFF':
            raise ValueError(f"会话最后一条消息不是招聘官消息，session_id={session['sessionId']}")

        send_time = int(last_sentence.get('sendTime') or 0)
        if not send_time:
            raise ValueError(f"会话缺少最后消息发送时间，session_id={session['sessionId']}")

        msg = detail.get('msg') or {}
        receipt_times = (
            detail.get('lastMessageReadTime'),
            msg.get('msgReceiptTime') if isinstance(msg, dict) else None,
        )
        latest_receipt_time = max(
            (int(value) for value in receipt_times if value not in (None, '')),
            default=0,
        )
        return '已读不回' if latest_receipt_time >= send_time else '未读消息'

    def is_gold_collar_candidate(self, raw_resume_dict):
        resume = raw_resume_dict.get('resume') or {}
        resume_level = str(resume.get('resumeLevel', '')).upper()
        return resume_level in GOLD_COLLAR_LEVELS

    def candidate_has_shared_contact(self, clean_candidate_msg):
        """判断候选人是否已通过卡片或文字提供联系方式（微信/电话）。

        仅依赖可靠信号，避免误判：
        - 卡片：history_msg 已把交换微信/分享电话卡片解析为
          “候选人发起交换微信请求”/“候选人已分享电话”。
        - 文字：history_msg 识别到手机号或带标签的微信号后会写入脱敏占位符。
        - 兼容：仍识别未经过脱敏解析的 11 位手机号。
        """
        for line in clean_candidate_msg or []:
            if '候选人发起交换微信请求' in line or '候选人已分享电话' in line:
                return True
            if CONTACT_HIDDEN_TEXT in line:
                return True
            if PHONE_PATTERN.search(line):
                return True
        return False

    def candidate_spoke_last(self, clean_msg, clean_bot_msg, clean_candidate_msg):
        """判断对话中最后发言的一方是否为候选人。

        用于避免在候选人尚未回复时重复主动发送（例如反复索要联系方式）：
        只有当最后一句来自候选人（确实轮到我们回）时才应回复。
        依据 history_msg 已解析出的候选人/招聘方消息行做精确匹配，倒序找到
        最后一条属于任一方的消息：属于候选人返回 True，属于招聘方返回 False。
        候选人行前缀（候选人说/候选人发起交换微信请求/候选人已分享电话）与
        招聘方行（AI招聘官说）不重叠，不会误判。
        """
        bot_lines = set(clean_bot_msg or [])
        candidate_lines = set(clean_candidate_msg or [])
        for line in reversed(clean_msg or []):
            if line in candidate_lines:
                return True
            if line in bot_lines:
                return False
        return False

    def _collect_active_job_numbers(self):
        """收集智联当前在招（RELEASED）岗位的 jobNumber，用于过滤已下线岗位会话。"""
        active_job_numbers = set()
        page = 1
        while True:
            response = get_job_list(self.current_cookies, page_no=page, page_size=20)
            self._raise_if_zhilian_authentication_failed(response)
            job_list = json.loads(response.text).get('data') or []
            if not job_list:
                break
            for job in job_list:
                job_numbers = job.get('jobNumbers') or []
                if job_numbers:
                    active_job_numbers.add(job_numbers[0])
            page += 1
        return active_job_numbers

    @staticmethod
    def is_session_content_missing(html_text):
        """判断会话页是否只返回了收件箱外壳（含会话列表但无聊天内容）。

        正常会话页含聊天气泡（im-message）；被服务端限流或聊天内容未渲染时，
        返回的页面只剩左侧会话列表（im-session-item）而没有 im-message。
        借此把“被限流/内容未加载”与“真无候选人消息”区分开。
        """
        text = html_text or ''
        return 'im-message' not in text and 'im-session-item' in text

    def _clean_account_name(self, value):
        if not value:
            return ''
        account_name = unescape(str(value)).strip()
        account_name = re.sub(r'\s+', ' ', account_name)
        account_name = account_name.strip(' ：:-')
        if not account_name or account_name == UNKNOWN_ACCOUNT_NAME:
            return ''
        return account_name

    def extract_account_name_from_session_html(self, html):
        soup = BeautifulSoup(html, 'lxml')

        selectors = [
            '.account-entry__name',
            '[class*="account-entry__name"]',
            '[class*="account"][class*="name"]',
            '[class*="staff"][class*="name"]',
            '[class*="user"][class*="name"]',
        ]
        for selector in selectors:
            for node in soup.select(selector):
                account_name = self._clean_account_name(node.get_text(' ', strip=True))
                if account_name:
                    return account_name

        # 智联 IM 页经常把当前账号信息放在内联 JSON / hydration script 中。
        json_key_pattern = re.compile(
            r'"(?:accountName|staffName|rdStaffName|recruiterName|operatorName|userName)"\s*:\s*"([^"]+)"'
        )
        for match in json_key_pattern.finditer(html):
            account_name = self._clean_account_name(match.group(1))
            if account_name:
                return account_name

        text_pattern = re.compile(r'(?:智联账号|当前账号|账号|招聘官)\s*[:：]\s*([^\s<>"，,;；|]+)')
        for match in text_pattern.finditer(soup.get_text(' ', strip=True)):
            account_name = self._clean_account_name(match.group(1))
            if account_name:
                return account_name

        return UNKNOWN_ACCOUNT_NAME

    def upload_screening(self, cookies_path, search_condition, incharge_id, position_id, position_name):
        self.__init__()
        self.set_cookies(cookies_path)

        page_count = self.get_page_count(search_condition)

        logger.info('获取候选人列表')
        for page_no in tqdm(range(page_count)):
            time.sleep(random.randrange(5, 7))
            self.set_candidate_list(search_condition, page_no, 20, need_clean=False)
        logger.info('获取简历列表')
        self.set_resume_list()
        execl_filepath = str(
            Path(path_util.get_save_path()) / 'candidate' / f'{position_name}_{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.xlsx')
        for resume in self.current_resume_list:
            candidate = Candidate.from_raw_resume(resume, position_id, incharge_id)
            candidate.upload_screening_resume_to_anyJob()
            h5_ai_add_count(position_id, count_resume_reviews=1)
            candidate.to_excel_row(execl_filepath)

    def first_conversation(self, cookies_path, search_condition, position_id, limit_count):
        self.__init__()
        self.set_cookies(cookies_path)

        if not self.check_and_set_job(position_id):
            return

        page_count = self.get_page_count(search_condition)

        logger.info('获取合格候选人列表')

        for page_no in tqdm(range(page_count)):
            time.sleep(random.randrange(1, 2))
            self.set_candidate_list(search_condition, page_no, 20, need_clean=True)

        logger.info('合格发起会话人数')

        for candidate in tqdm(self.current_candidate_list):
            if self.first_conversation_count >= limit_count:
                logger.info('初次会话超限制')
                return
            response = create_greet(self.current_cookies, self.current_job_number, candidate['resumeNumber'],
                                    candidate['resumeLanguage'], candidate['resumeVersion'])
            params = {
                "cookies": self.current_cookies,
                "resume_number": candidate['resumeNumber'],
                'resume_K': candidate['resumeK'],
                'resume_T': candidate['resumeT'],
                'purpose_id': candidate['purposes'][0]['purposeId']
            }

            if json.loads(response.text)['code'] == 200:
                self.first_conversation_count += 1
                h5_ai_add_count(self.current_position["position_id"], count_conversations=1)
            else:
                self.pay_flag = True

            response = get_resume(**params)

            raw_resume = json.loads(response.text)['data']

            incharge_id = get_ah_result_dict(get_incharge_id_by_position_id(position_id))['results'][0]['incharge_id']

            candidate = Candidate.from_raw_resume(raw_resume,position_id,incharge_id)

            candidate.upload_screening_resume_to_anyJob()
            h5_ai_add_count(position_id, count_resume_reviews=1)

    def first_conversation_with_excel(self, cookies_path, search_condition, position_id, limit_count,
                                      job_title_hint=None):
        self.__init__()
        self.set_cookies(cookies_path)

        if not self.check_and_set_job(position_id, job_title_hint=job_title_hint):
            return 2

        if self.first_conversation_count >= limit_count:
            logger.info('初次会话超限制')
            return 1

        params = {
            'page_no': 1,
            'page_size': 20,
        }
        params.update(**search_condition.to_dict())
        response = get_candidate_list(self.current_cookies, **params)
        search_data = json.loads(response.text).get('data') or {}
        total = search_data.get('total', 0)
        candidate_list = search_data.get('list') or []
        logger.info(f'高级搜索命中 {total} 人')

        if total == 0 or not candidate_list:
            return 3

        candidate = candidate_list[0]
        response = create_greet(
            self.current_cookies,
            self.current_job_number,
            candidate['resumeNumber'],
            candidate['resumeLanguage'],
            candidate['resumeVersion'],
        )
        resume_params = {
            "cookies": self.current_cookies,
            "resume_number": candidate['resumeNumber'],
            'resume_K': candidate['resumeK'],
            'resume_T': candidate['resumeT'],
            'purpose_id': candidate['purposes'][0]['purposeId'],
        }

        if json.loads(response.text)['code'] != 200:
            logger.info('打招呼失败')
            self.pay_flag = True
            return 3

        self.first_conversation_count += 1
        h5_ai_add_count(self.current_position["position_id"], count_conversations=1)

        response = get_resume(**resume_params)
        raw_resume = json.loads(response.text)['data']
        candidate_obj = Candidate.from_raw_resume(raw_resume, position_id)
        candidate_obj.upload_screening_resume_to_anyJob()
        h5_ai_add_count(position_id, count_resume_reviews=1)
        return 0

    def auto_reply(self, cookies_path, reply_mode='all', position_id='all'):
        self.__init__()
        self.set_cookies(cookies_path)
        active_job_numbers = set()
        if reply_mode == 'all':
            active_job_numbers = self._collect_active_job_numbers()
            if not active_job_numbers:
                logger.info('获取在招职位列表为空，无法执行全部岗位自动回复')
                return

            page = 1
            pabr = tqdm(desc="读取会话", unit="页")
            while True:
                response = get_session_list(
                    self.current_cookies, page, 20, 'all',
                    is_unread=True,
                    initiated_by_me=True,
                )
                if json.loads(response.text)['data']:
                    self.current_session_list = [*self.current_session_list, *json.loads(response.text)['data']]
                    page += 1
                    pabr.update(1)
                else:
                    break
            pabr.close()
        else:
            if not self.check_and_set_job(position_id):
                return
            page = 1
            pabr = tqdm(desc="读取会话", unit="页")
            while True:
                response = get_session_list(
                    self.current_cookies, page, 20, 'all',
                    is_unread=True,
                    job_number=self.current_job_number,
                    initiated_by_me=True,
                )
                if json.loads(response.text)['data']:
                    self.current_session_list = [*self.current_session_list, *json.loads(response.text)['data']]
                    page += 1
                    pabr.update(1)
                else:
                    break
            pabr.close()

        logger.info('处理会话')

        consecutive_throttled = 0
        for session in self.current_session_list:
            if reply_mode == 'all':
                session_job_number = session.get('jobNumber')
                if session_job_number not in active_job_numbers:
                    logger.info(
                        f"候选人{session.get('name', '未知')}会话 jobNumber={session_job_number} "
                        f"不在在招岗位列表，跳过（疑似已下线岗位）"
                    )
                    continue
                try:
                    current_position_id = RegexUtils.get_position_id(session['jobTitle'])
                except Exception:
                    logger.info(f"{session.get('name', '未知')}的岗位 {session.get('jobTitle')} 无法解析岗位ID，跳过")
                    continue
            else:
                current_position_id = position_id

            if not session['unreadCount']:
                logger.info(f"候选人{session.get('name', '未知')}无未读消息被跳过")
                continue

            response = get_session_html(self.current_cookies, session['sessionId'])

            # 区分“被限流/内容未加载”与“真无候选人消息”：仅返回收件箱外壳时做有限次退避重试
            content_retry = 0
            while self.is_session_content_missing(response.text) and content_retry < SESSION_CONTENT_MAX_RETRY:
                content_retry += 1
                logger.info(f"候选人{session.get('name', '未知')}聊天内容疑似被限流/未加载，第{content_retry}次退避重试")
                time.sleep(random.randrange(SESSION_CONTENT_RETRY_GAP_MIN, SESSION_CONTENT_RETRY_GAP_MAX))
                response = get_session_html(self.current_cookies, session['sessionId'])
            if self.is_session_content_missing(response.text):
                consecutive_throttled += 1
                logger.info(f"候选人{session.get('name', '未知')}重试{content_retry}次后聊天内容仍未返回（疑似被限流），本轮跳过（连续{consecutive_throttled}个）")
                if consecutive_throttled >= SESSION_CONTENT_THROTTLE_ABORT:
                    logger.info(f"连续{consecutive_throttled}个会话疑似被限流，提前结束本轮自动回复以避免无效请求")
                    break
                continue
            consecutive_throttled = 0

            if response.text.find('该用户给您发来') >= 0 and response.text.find('如您感兴趣，可留下您的微信继续沟通') >= 0:
                logger.info(f"候选人{session.get('name', '未知')}为系统单向消息（非真人对话）被跳过")
                set_msg_read(self.current_cookies, session['userId'])
                continue
            if response.text.find('登录智联招聘APP可进行沟通') >= 0:
                logger.info(f"候选人{session['name']}将机器活跃判断为已读")
                response = set_msg_read(self.current_cookies, session['userId'])
                continue

            (clean_msg, clean_bot_msg, clean_candidate_msg) = get_clean_history_msg(response.text)

            if not clean_candidate_msg:
                logger.info(f"候选人{session.get('name', '未知')}未解析到候选人消息被跳过（可能为未识别的消息类型）")
                continue

            if not self.candidate_spoke_last(clean_msg, clean_bot_msg, clean_candidate_msg):
                logger.info(f"候选人{session.get('name', '未知')}最后一条消息来自招聘方（候选人尚未回复），跳过避免重复打扰")
                continue

            job_requirement = \
                get_ah_result_dict(get_job_data(current_position_id))['results'][0]['name_summary'].split('【二次会话】')[
                    0]

            contact_instruction = ''
            resume_shared = candidate_sent_resume(response.text)
            if self.candidate_has_shared_contact(clean_candidate_msg):
                logger.info(f"候选人{session['name']}已提供联系方式，本轮回复不再索要联系方式")
                contact_instruction = (
                    '【特别说明：候选人已提供联系方式（微信或电话），请勿再向候选人索要任何联系方式；'
                    '可先简短确认已收到，然后继续就岗位其他方面与候选人沟通。】'
                )
            elif resume_shared:
                logger.info(f"候选人{session['name']}已发送简历，本轮回复不再索要联系方式")
                contact_instruction = (
                    '【特别说明：候选人已发送简历，系统侧可直接查看其电话，请勿再向候选人索要电话；'
                    '可先简短确认已收到简历，然后继续就岗位其他方面与候选人沟通。】'
                )

            reply = chatBot.send(
                f'{contact_instruction}【岗位名称和要求：】{job_requirement}【历史聊天记录：】{"<br>".join(clean_msg)}',
                ENUM_MODEL_ID.AUTO_REPLY_MSG_GEN
            )

            if reply.find('不回复') >= 0:
                logger.info(f"候选人{session['name']}被判断不回复")
                response = set_msg_read(self.current_cookies, session['userId'])
                continue

            time.sleep(random.randrange(10, 20))
            response = send_msg(self.current_cookies, reply, session['sessionId'])
            if json.loads(response.text)['code'] == 200:
                logger.info(f"向候选人{session['name']}发送消息成功")
                if clean_candidate_msg and clean_candidate_msg[-1]:
                    h5_post(current_position_id, '意向人选回复', f"<{session['name']}>发送消息：{clean_candidate_msg[-1]}")

                h5_ai_add_count(current_position_id, count_replies=1)
                try:
                    recommend_id = get_ah_result_dict(get_incharge_id_by_position_id(current_position_id))['results'][0]['incharge_id']
                    resume_payload = {}
                    for _ in range(3):
                        resume_resp = get_session_resume(
                            self.current_cookies,
                            session['jobNumber'],
                            session['resumeNumber'],
                            session['resumeLanguage']
                        )
                        resume_payload = json.loads(resume_resp.text)
                        if resume_payload.get('data'):
                            break
                    raw_resume_dict = resume_payload.get('data') or {}
                    if isinstance(raw_resume_dict, dict) and raw_resume_dict:
                        raw_user = raw_resume_dict.get('user') or {}
                        raw_resume_session = raw_resume_dict.get('resumeSession') or {}
                        phone = raw_user.get('phone', '') if isinstance(raw_user, dict) else ''
                        if not phone:
                            phone = self.extract_phone_from_resume_remark(raw_resume_dict)
                        wechat = raw_resume_session.get('wechat', '') if isinstance(raw_resume_session, dict) else ''
                        candidate = Candidate.from_raw_resume(raw_resume_dict, current_position_id, recommend_id)
                        candidate.sync_high_potential_by_smart_keywords(
                            chat_history='\n'.join(clean_msg),
                            phone=phone,
                            vx=wechat
                        )
                except Exception:
                    logger.exception(
                        f"自动回复后高潜同步失败，候选人={session.get('name', '未知')}，"
                        f"会话ID={session.get('sessionId', '')}"
                    )

                set_msg_read(self.current_cookies, session['userId'])

    def _load_second_conversation_sessions(self, job_number, pabr):
        page = 1
        while True:
            response = get_session_list(
                self.current_cookies, page, 20, 'DEFAULT_INTERESTED', is_unread=False, job_number=job_number
            )
            session_list = json.loads(response.text).get('data') or []
            if not session_list:
                break
            self.select_second_conversation_session_list(session_list)
            pabr.update(1)
            page += 1

    def second_conversation(self, cookies_path, reply_mode='all', position_id='all'):
        self.__init__()
        self.set_cookies(cookies_path)
        pabr = tqdm(desc="读取会话", unit="页")
        if reply_mode == 'all':
            job_list = json.loads(get_job_list(self.current_cookies).text).get('data') or []
            if not job_list:
                logger.info('获取职位列表为空，无法进行二次会话')
                pabr.close()
                return

            for job in job_list:
                job_numbers = job.get('jobNumbers') or []
                if not job_numbers:
                    continue
                self._load_second_conversation_sessions(job_numbers[0], pabr)
        else:
            if not self.check_and_set_job(position_id):
                pabr.close()
                return
            self._load_second_conversation_sessions(self.current_job_number, pabr)

        pabr.close()
        logger.info(f'二次会话筛选完成，待处理 {len(self.current_session_list)} 个会话')
        logger.info('处理对话')
        for session in self.current_session_list:
            session_position_id = position_id
            try:
                if reply_mode == 'all':
                    session_position_id = RegexUtils.get_position_id(session['jobTitle'])

                for _ in range(3):
                    response = get_session_resume(self.current_cookies, session['jobNumber'], session['resumeNumber'],
                                              session['resumeLanguage'])
                    if json.loads(response.text)['data']:
                        break
                    logger.warn(f"重试获取 {session['name']} 简历")

                if not json.loads(response.text)['data']:
                    logger.info(f"{session['name']}无法获取简历被跳过\n{response.text}")
                    continue

                raw_resume_dict = json.loads(response.text)['data']

                candidate = Candidate.from_raw_resume(raw_resume_dict, session_position_id)
                clean_resume = select_field_in_resume(json.loads(candidate.rawResume))

                resp = get_job_data(session_position_id)
                data = get_ah_result_dict(resp)['results'][0]
                summary = data['summary']
                name_summary = data['name_summary']
                job_requirement = f"深匹要求：{summary.split('深匹要求：')[1]} {name_summary.split('【公司信息】')[0]}"

                (clean_msg, _, _) = get_clean_history_msg(response.text)
                his_msg = '\n'.join(clean_msg)

                second_contact_msg = chatBot.send(
                    f'【岗位信息：】{job_requirement} 【候选人信息：】{clean_resume}【历史聊天记录:】{his_msg}',
                    ENUM_MODEL_ID.SECOND_CONTACT_MSG_GEN
                )
                reply = chatBot.send(second_contact_msg, ENUM_MODEL_ID.SECOND_CONTACT_MSG_GEN)

                send_msg(self.current_cookies, reply, session['sessionId'])

                send_ask_wx_msg(self.current_cookies, session['sessionId'])
                send_sak_phone_msg(self.current_cookies, session['sessionId'])

                set_msg_read(self.current_cookies, session['userId'])
            except Exception:
                logger.exception(
                    f"二次会话处理失败，候选人={session.get('name', '未知')}，"
                    f"会话ID={session.get('sessionId', '')}，position_id={session_position_id}"
                )
                continue

    def select_second_conversation_session_list(self, session_list):
        for session in session_list:
            if session.get('latestMsgTime',{}):
                dt = datetime.fromtimestamp(session['latestMsgTime'] / 1000)

                if dt < datetime.now() - timedelta(days=7):
                    logger.info(f"{session['name']}最后聊天时间早于7天前,结束二次会话")
                    return
            try:
                RegexUtils.get_position_id(session['jobTitle'])
            except Exception as e:
                logger.info(f"{session['name']}的岗位{session['jobTitle']}格式中无数字被跳过")
                continue
            if not session['unreadCount'] == 0:
                logger.info(f"{session['name']}有未读消息被跳过")
                continue
            response = get_session_html(self.current_cookies, session['sessionId'])

            (clean_msg, clean_bot_msg, clean_candidate_msg) = get_clean_history_msg(response.text)

            if clean_bot_msg and clean_bot_msg.__len__() >= 3:
                logger.info(f"{session['name']}已经发送三条消息被跳过")
                continue

            if clean_candidate_msg:
                logger.info(f"{session['name']}已经回复被跳过")
                continue

            for _ in range(3):
                response = get_session_resume(self.current_cookies, session['jobNumber'], session['resumeNumber'],
                                          session['resumeLanguage'])
                if json.loads(response.text)['data']:
                    break
                logger.warn(f"重试获取 {session['name']} 简历")

            if not json.loads(response.text)['data']:
                logger.info(f"{session['name']}无法获取简历被跳过\n{response.text}")
                continue

            raw_resume_dict = json.loads(response.text)['data']

            if raw_resume_dict['user']['phone']:
                logger.info(f"{session['name']}有电话被跳过")
                continue

            if raw_resume_dict['resumeSession']['wechat']:
                logger.info(f"{session['name']}有微信被跳过")
                continue

            self.current_session_list.append(session)

    def save_resume(self, cookies_path, reply_mode,start_time, end_time,position_id = None):
        self.__init__()
        self.set_cookies(cookies_path)
        if reply_mode == 'all':
            active_job_numbers = self._collect_active_job_numbers()
            if not active_job_numbers:
                logger.info('获取在招职位列表为空，无法执行全部岗位保存简历')
                return

            page = 1
            pabr = tqdm(desc="读取保存简历会话", unit="页")
            while True:
                response = get_session_list(self.current_cookies, page, 20, 'all', is_unread=False)
                self._raise_if_zhilian_authentication_failed(response)
                session_list = json.loads(response.text).get('data') or []

                if not session_list:
                    break

                self.set_save_resume_session_list(end_time, session_list, start_time, active_job_numbers)
                page += 1
                pabr.update(1)
            pabr.close()
        else:
            if not self.check_and_set_job(position_id):
                return
            page = 1
            pabr = tqdm(desc="读取保存简历会话", unit="页")

            while True:
                response = get_session_list(
                    self.current_cookies, page, 20, 'all', is_unread=False,
                    job_number=self.current_job_number,
                )
                self._raise_if_zhilian_authentication_failed(response)
                session_list = json.loads(response.text).get('data') or []

                if not session_list:
                    break

                self.set_save_resume_session_list(end_time, session_list, start_time)

                page += 1
                pabr.update(1)

            pabr.close()

        logger.info('处理会话')

        for session in self.current_session_list:
            phone = ''
            wechat = ''
            try:
                if reply_mode == 'all':
                    position_id = RegexUtils.get_position_id(session['jobTitle'])
                else:
                    position_id = position_id

                recommend_id = get_ah_result_dict(get_incharge_id_by_position_id(position_id))['results'][0]['incharge_id']

                resume_response_text = ''
                resume_payload = {}
                for _ in range(3):
                    response = get_session_resume(self.current_cookies, session['jobNumber'], session['resumeNumber'],
                                              session['resumeLanguage'])
                    resume_response_text = response.text
                    resume_payload = json.loads(resume_response_text)
                    self._raise_if_zhilian_authentication_failed(response)
                    if resume_payload.get('data'):
                        break
                    logger.warn(f"重试获取 {session['name']} 简历")

                if not resume_payload.get('data'):
                    logger.info(f"{session['name']}无法获取简历被跳过\n{resume_response_text}")
                    continue

                raw_resume_dict = resume_payload.get('data') or {}
                if not isinstance(raw_resume_dict, dict):
                    logger.warning(f"{session['name']}简历数据结构异常，data不是字典，被跳过\n{resume_response_text}")
                    continue

                raw_resume_session = raw_resume_dict.get('resumeSession') or {}
                if not isinstance(raw_resume_session, dict):
                    raw_resume_session = {}

                phone = self.extract_available_phone(raw_resume_dict)

                wechat = raw_resume_session.get('wechat', '')

                session_html = self._get_cached_session_html(session)

                (clean_msg, _, clean_candidate_msg) = get_clean_history_msg(session_html)
                resume_shared = candidate_sent_resume(session_html)

                if not clean_msg:
                    logger.info(f"候选人{session.get('name', '未知')}无聊天记录被跳过")
                    continue

                msg = '\n'.join(clean_msg)

                candidate = Candidate.from_raw_resume(raw_resume_dict, position_id, recommend_id)

                if (
                    not phone
                    and resume_shared
                    and self._can_call_candidate(raw_resume_dict)
                ):
                    try:
                        phone = self._get_phone_from_call_button(session)
                        if phone:
                            logger.info(f"候选人{session['name']}已发送简历，通过打电话入口获取到联系方式")
                    except ZhilianAuthenticationError:
                        raise
                    except Exception:
                        logger.exception(
                            f"候选人{session['name']}已发送简历，但通过打电话入口获取联系方式失败"
                        )

                rule_tag = self.get_conversation_rule_tag(
                    session,
                    clean_candidate_msg,
                    phone=phone,
                    wechat=wechat,
                    resume_shared=resume_shared,
                )

                if not phone and not wechat:
                    candidate.sync_high_potential_by_smart_keywords(
                        chat_history=msg,
                        rule_tag=rule_tag,
                    )
                    logger.info(
                        f"候选人{session['name']}无联系方式，仅完成高潜 tag 同步，"
                        f"rule_tag={rule_tag or '模型判断'}"
                    )
                    set_msg_read(self.current_cookies, session['userId'])
                    continue

                if not phone and self.is_gold_collar_candidate(raw_resume_dict):
                    candidate.sync_high_potential_by_smart_keywords(
                        chat_history=msg,
                        rule_tag=rule_tag,
                    )
                    logger.info(f"{session['name']}是金领人才且备注中无手机号，跳过后续正式入库")
                    set_msg_read(self.current_cookies, session['userId'])
                    continue

                account_name = self.extract_account_name_from_session_html(session_html)
                if account_name == UNKNOWN_ACCOUNT_NAME:
                    logger.warning(
                        f"未能从 IM HTML 读取智联账号姓名，候选人={session.get('name', '未知')}，"
                        f"会话ID={session.get('sessionId', '')}"
                    )

                candidate.upload_resume_to_anyJob(
                    phone,
                    wechat,
                    msg,
                    recommend_id,
                    account_name,
                    rule_tag=rule_tag,
                )

                set_msg_read(self.current_cookies, session['userId'])
            except ZhilianAuthenticationError:
                logger.error(ZHILIAN_AUTH_ERROR_MESSAGE)
                raise
            except Exception:
                logger.exception(
                    f"保存简历时处理会话失败，候选人：{session.get('name', '未知')}，"
                    f"会话ID：{session.get('sessionId', '')}，"
                    f"phone_empty={not bool(phone)}，wechat_empty={not bool(wechat)}"
                )
                continue

    def set_save_resume_session_list(self, end_time, session_list, start_time, active_job_numbers=None):
        for session in session_list:
            dt = datetime.fromtimestamp(session['communicateTime'] / 1000)
            if dt > end_time:
                logger.info(f"候选人{session['name']}会话时间晚于结束时间，结束筛选会话")
                break
            if active_job_numbers is not None:
                session_job_number = session.get('jobNumber')
                if session_job_number not in active_job_numbers:
                    logger.info(
                        f"候选人{session.get('name', '未知')}会话 jobNumber={session_job_number} "
                        f"不在在招岗位列表，跳过（疑似已下线岗位）"
                    )
                    continue
            try:
                RegexUtils.get_position_id(session['jobTitle'])
            except Exception as e:
                logger.info(f"{session['name']}的岗位{session['jobTitle']}格式中无数字被跳过")
                continue
            if session['sessionId'] in self.session_number_hash:
                continue
            if dt < start_time:
                logger.info(f"候选人{session['name']}会话时间早于开始时间被跳过")
                continue
            if session['unreadCount'] and session['unreadCount'] > 0:
                if not self._unread_session_contains_resume(session):
                    logger.info(f"候选人{session['name']}有未读消息且未检测到候选人发送简历，被跳过")
                    continue
                logger.info(f"候选人{session['name']}有未读消息，但已确认候选人发送简历，定向放行")
            self.session_number_hash.add(session['sessionId'])
            self.current_session_list.append(session)


# Manual demo removed from repository import; use synthetic fixtures for local testing.
