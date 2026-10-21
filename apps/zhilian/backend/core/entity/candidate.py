"""
----------------------------------------------------
 File Name:        Candidate
 Author:           hoges
 Created Date:     2025/9/22
 Last Modified:    2025/9/22
 Python Version:   
----------------------------------------------------
"""
import json
import re
import unicodedata
from pathlib import Path

import backend.core.api.chatBotApi as chatBot

from datetime import datetime
from typing import Union
from backend.core.api.anyJobApi import get_job_data, duplicate_screening, add_screening_resume, \
    h5_post, get_user_role, get_ah_result_dict, add_resume, duplicate, update_screening_resume, update_chat_history, \
    update_status_tag, update_resume, get_incharge_id_by_position_id, get_resume_data
from backend.core.config.anyJobConfig import (
    ENUM_CANDIDATE_CLASSIFY,
    STATUS_TAG_CODE_STRONG_INTENT,
    STATUS_TAG_STRONG_INTENT_NUMERIC_CODES,
    STATUS_TAG_VERY_MATCH_COIN_60_CODES,
    STATUS_TAG_VERY_MATCH_COIN_80_ACTIVE_CODES,
)
from backend.core.config.chatBotApiConfig import ENUM_MODEL_ID
from backend.core.config.execl_config import EXECL_HEADER, EXECL_ATTRIBUTES
from backend.core.logger.logger import get_logger
from backend.core.utils.excel_generator.excel_generator import excel_generator
from backend.core.utils.msg.history_msg import get_duplicate_full_chat_history, redact_contact_text
from backend.core.utils.regex.regex_utils import RegexUtils
from backend.core.utils.resume.clean_resume import select_field_in_resume
from backend.core.utils.resume.highest_education import get_highest_education_fields
from backend.core.utils.resume.diagnostics import (
    log_resume_diagnostic,
    stable_data_sha256,
    summarize_education_experiences,
    summarize_http_response,
)

logger = get_logger(__name__)


def _safe_dict(value):
    return value if isinstance(value, dict) else {}


def _position_id_matches(record_position_id, current_position_id) -> bool:
    current = str(current_position_id).strip()
    raw = str(record_position_id).strip()
    if not current or not raw:
        return False
    if raw == current:
        return True
    # 接口有时会返回逗号拼接或其他分隔形式的岗位 ID，这里只认明确 token 命中
    return current in [token for token in re.split(r"[^\d]+", raw) if token]


def _find_current_position_record(records, position_id):
    for record in records or []:
        if _position_id_matches(record.get("position_id"), position_id):
            return record
    return None


def _extract_chat_history(value):
    if isinstance(value, dict):
        for key in ("chat_history", "chatHistory", "chat_history_text", "chatHistoryText"):
            chat_history = value.get(key)
            if isinstance(chat_history, str) and chat_history.strip():
                return chat_history
        for item in value.values():
            chat_history = _extract_chat_history(item)
            if chat_history:
                return chat_history
    elif isinstance(value, list):
        for item in value:
            chat_history = _extract_chat_history(item)
            if chat_history:
                return chat_history
    return ""


def _status_tags_is_strong_intent(status_tags) -> bool:
    if status_tags is None:
        return False
    raw = str(status_tags).strip()
    if "强意向" in raw:
        return True
    if not STATUS_TAG_STRONG_INTENT_NUMERIC_CODES:
        return False
    try:
        return int(raw) in STATUS_TAG_STRONG_INTENT_NUMERIC_CODES
    except ValueError:
        return False


def _coins_cost_very_match_from_status_tags(status_tags) -> int:
    """
    非常匹配 + 候选人已回复：先识别强意向 256（积极，80），再识别 104/105/107（80）、109/110（60），
    其余沿用原「>=109 → 60，否则 80」兜底（256 已单独排除，避免被 >=109 误判为 60）。
    """
    try:
        v = int(str(status_tags).strip())
    except (ValueError, TypeError):
        logger.warning("status_tags 非数字，按「无明确标签」计 60: %r", status_tags)
        return 60

    if v == STATUS_TAG_CODE_STRONG_INTENT:
        return 80
    if v in STATUS_TAG_VERY_MATCH_COIN_80_ACTIVE_CODES:
        return 80
    if v in STATUS_TAG_VERY_MATCH_COIN_60_CODES:
        return 60
    return 60 if v >= 109 else 80


def compute_upload_resume_coins_cost(fact_check_comment_label: str, chat_history: str, status_tags) -> int:
    """
    保存简历上传人才库时的金币消耗（coins_cost）。
    与 upload_resume_to_anyJob 中业务规则保持一致，便于脚本做真值表校验。
    """
    has_reply = "候选人" in (chat_history or "")
    label = fact_check_comment_label or ""
    passed = label in ("匹配", "非常匹配")
    not_passed = label in ("不匹配", "不确定")

    if has_reply and not_passed:
        return 30
    if not_passed:
        return 20
    if passed and not has_reply:
        return 40
    if passed and has_reply:
        if _status_tags_is_strong_intent(status_tags):
            return 80
        if label == "匹配":
            return 50
        if label == "非常匹配":
            return _coins_cost_very_match_from_status_tags(status_tags)
    return 20


class Candidate:
    def __init__(
            self,
            name,
            currentCompany,
            currentPosition,
            schoolName,
            major,
            rawResume: str,
            salary,
            position_id,
            incharge_id,
            now_region,
            age=None,
            gold_collar=None,
            link: str = "",
            recentActiveTime: datetime = None,
    ):
        """
        execl列头
        name:简历获取
        current company : 简历最后一段经历获取
        current position : 简历最后一段经历获取
        link : 无
        liepin key words : 公司加岗位加学校加专业
        resume : bot清洗, __TALENTMATCH_MODEL_19__ ,简单简历关键字清洗(对应simple_resume)
        salary : 从resume里面拿取
        comment :  firstCheckComment (这里不存推荐语,推荐语上传的时候添加)
        comment_simplified : firstCheckCommentLabel
        gold collar : 简历里面有一个值是resumeLevel
        raw resume : 简历里有resume.language
        note : 放空
        time_stamp : 当前时间戳
        事实判断是否 : 二次判断的label
        事实判断 : 二次判断的原始值
        是否重复 : 查重结果(Yes,No)
        上传情况 : 上传后填入,是否上传看二次判断label
        最近活跃时间 : 简历里有lastActiveTime
        """

        self.resume_id = None
        self.is_duplicate_with_current_position = False
        self.name = name

        self.currentCompany = currentCompany
        self.currentPosition = currentPosition
        self.link = link
        self.schoolName = schoolName
        self.major = major
        self.liepin_keywords = f'{currentCompany} {currentPosition} {schoolName} {major}'
        self.smart_keywords = Candidate._build_smart_keywords(
            name=name,
            current_company=currentCompany,
            current_position=currentPosition,
            school_name=schoolName,
            major=major,
        )
        self.smart_keywords_candidates = Candidate._build_smart_keyword_candidates(
            name=name,
            current_company=currentCompany,
            current_position=currentPosition,
            school_name=schoolName,
            major=major,
        )

        self.rawResume = rawResume

        self.simple_resume = ''

        self.salary = salary
        self.age = age

        self.position_id = position_id
        self.incharge_id = incharge_id

        self.job_requirement = ''
        self.job_deep_requirement = ''

        self.firstCheckComment = ""
        self.firstCheckCommentLabel = ""

        self.gold_collar = gold_collar
        self.time_stamp = datetime.now()
        self.note = ''

        self.fact_check_comment = ''
        self.fact_check_comment_label = ''

        self.now_region = now_region

        self.is_clients = False

        self.is_duplicate = False
        self.is_duplicate_pass = False
        self.duplicate_position_id_list = []
        self.duplicate_position_name_list = []

        self.recentActiveTime = recentActiveTime
        self.source_user_id = None
        self.source_resume_id = None
        self.resume_payload_sha256 = ""

    @staticmethod
    def _collapse_spaces(value: str) -> str:
        if not value:
            return ''
        normalized = unicodedata.normalize('NFKC', str(value))
        # smart_keywords 查重依赖精确匹配；统一括号写法，避免【】/（）/括号内空格导致 miss
        normalized = normalized.replace('【', '(').replace('】', ')')
        normalized = normalized.replace('\u3000', ' ')
        normalized = re.sub(r'\(\s+', '(', normalized)
        normalized = re.sub(r'\s+\)', ')', normalized)
        normalized = re.sub(r'\s+\(', '(', normalized)
        normalized = re.sub(r'\)\s+', ')', normalized)
        return ' '.join(normalized.split())

    @staticmethod
    def _get_name_first_char(name: str) -> str:
        normalized_name = Candidate._collapse_spaces(name)
        if not normalized_name:
            return ''
        return normalized_name[0]

    @staticmethod
    def _build_smart_keywords_with_separator(name, current_company, current_position, school_name, major, separator):
        name_first_char = Candidate._get_name_first_char(name)
        parts = [
            name_first_char,
            Candidate._collapse_spaces(current_company),
            Candidate._collapse_spaces(current_position),
            Candidate._collapse_spaces(school_name),
            Candidate._collapse_spaces(major),
        ]
        return separator.join(part for part in parts if part)

    @staticmethod
    def _build_smart_keywords(name, current_company, current_position, school_name, major):
        return Candidate._build_smart_keywords_with_separator(
            name=name,
            current_company=current_company,
            current_position=current_position,
            school_name=school_name,
            major=major,
            separator='_',
        )

    @staticmethod
    def _build_smart_keyword_candidates(name, current_company, current_position, school_name, major):
        keywords = []
        base_position = Candidate._collapse_spaces(current_position)
        position_variants = [base_position]
        if base_position.startswith('研发'):
            position_variants.append(base_position.removeprefix('研发').strip())

        for position in position_variants:
            for separator in ('_', ' '):
                keyword = Candidate._build_smart_keywords_with_separator(
                    name=name,
                    current_company=current_company,
                    current_position=position,
                    school_name=school_name,
                    major=major,
                    separator=separator,
                )
                if keyword and keyword not in keywords:
                    keywords.append(keyword)
        return keywords

    def _reset_duplicate_state(self):
        self.is_duplicate = False
        self.is_duplicate_pass = False
        self.is_duplicate_with_current_position = False
        self.duplicate_position_id_list = []
        self.duplicate_position_name_list = []
        self.resume_id = None

    def _resume_diagnostic_fields(self):
        return {
            "data_sha256": getattr(self, "resume_payload_sha256", ""),
            "user_id": getattr(self, "source_user_id", None),
            "source_resume_id": getattr(self, "source_resume_id", None),
            "candidate_name": getattr(self, "name", ""),
            "position_id": getattr(self, "position_id", None),
            "incharge_id": getattr(self, "incharge_id", None),
            "selected_school": getattr(self, "schoolName", ""),
            "selected_major": getattr(self, "major", ""),
            "smart_keywords": getattr(self, "smart_keywords", ""),
        }

    def set_simple_resume(self):
        self.simple_resume = chatBot.send(self.rawResume, ENUM_MODEL_ID.GET_SIMPLE_RESUME)

    def set_job_requirement(self):
        self.job_requirement = get_ah_result_dict(get_job_data(self.position_id))['results'][0][
            'summary']
        self.job_deep_requirement = self.job_requirement.split('深匹要求：')[1]

    def set_first_check(self):
        self.set_job_requirement()

        self.firstCheckComment = chatBot.send(f'【个人信息：】{self.rawResume}【岗位要求：】{self.job_deep_requirement}',
                                              ENUM_MODEL_ID.GET_FIRST_CHECK)
        if self.firstCheckComment.find("非常匹配") >= 0:
            self.firstCheckCommentLabel = "非常匹配"
            return
        if self.firstCheckComment.find("不匹配") >= 0:
            self.firstCheckCommentLabel = "不匹配"
            return
        if self.firstCheckComment.find("匹配") >= 0:
            self.firstCheckCommentLabel = "匹配"
            return

    def set_fact_check(self):

        self.set_first_check()

        self.fact_check_comment = chatBot.send(
            f'【requirements：岗位要求】{self.job_deep_requirement}【name ：候选人名字】{self.name}【comment: 判断结果和原因】{self.firstCheckComment}【raw resume：候选人简历】{self.rawResume}',
            ENUM_MODEL_ID.GET_FACT_CHECK)
        if '不匹配' in self.fact_check_comment:
            self.fact_check_comment_label = '不匹配'
        elif '不确定' in self.fact_check_comment:
            self.fact_check_comment_label = '不确定'
        elif '非常匹配' in self.fact_check_comment:
            self.fact_check_comment_label = '非常匹配'
        else:
            self.fact_check_comment_label = '匹配'

    def check_screening_is_duplicate_with_smart_keywords(self):
        self._reset_duplicate_state()

        if not self.incharge_id:
            logger.warning(f'smart_keywords 高潜查重跳过，候选人={self.name}，原因=缺少 incharge_id')
            return
        if not self.position_id:
            logger.warning(f'smart_keywords 高潜查重跳过，候选人={self.name}，原因=缺少 position_id')
            return
        if not self.smart_keywords:
            logger.warning(f'smart_keywords 高潜查重跳过，候选人={self.name}，原因=smart_keywords 为空')
            return

        keywords_candidates = self.smart_keywords_candidates or [self.smart_keywords]
        for keyword in keywords_candidates:
            response = duplicate_screening(
                user_id=self.incharge_id,
                position_id=self.position_id,
                smart_keywords=keyword,
            )
            duplicate_response = get_ah_result_dict(response)
            duplicate_flag = str(duplicate_response.get('duplicate', '')).lower()
            records = duplicate_response.get('records', [])
            log_resume_diagnostic(
                logger,
                "anyjob_screening_duplicate_result",
                **self._resume_diagnostic_fields(),
                queried_smart_keywords=keyword,
                duplicate_flag=duplicate_flag,
                matched_records=[
                    {
                        "id": record.get("id"),
                        "position_id": record.get("position_id"),
                        "smart_keywords": record.get("smart_keywords"),
                    }
                    for record in records
                    if isinstance(record, dict)
                ],
                response_status=getattr(response, "status_code", None),
            )
            if duplicate_flag not in ('yes', '1', 'true'):
                continue

            current_record = _find_current_position_record(records, self.position_id)
            if current_record:
                self.is_duplicate = True
                self.is_duplicate_pass = True
                self.is_duplicate_with_current_position = True
                self.resume_id = current_record.get('id')
                self.duplicate_position_id_list = [current_record.get('position_id')]
                self.duplicate_position_name_list = [current_record.get('Position', '未知岗位')]
                logger.info(
                    f'与当前岗位 smart_keywords 重复，跳过新增高潜，候选人={self.name}，'
                    f'position_id={self.position_id}，smart_keywords={keyword}'
                )
                return

            duplicate_position_ids = [record.get('position_id') for record in records]
            logger.info(
                f'smart_keywords 查重命中但不是当前岗位，候选人={self.name}，当前岗位={self.position_id}，'
                f'重复岗位={duplicate_position_ids}，smart_keywords={keyword}'
            )

        self.is_duplicate_pass = False

    # 兼容旧调用，内部统一走 smart_keywords 查重。
    def check_screening_is_duplicate_with_keywords(self):
        self.check_screening_is_duplicate_with_smart_keywords()

    def check_is_duplicate_with_phone_wx(self, phone=None, vx=None):
        if not phone and not vx:
            logger.info(f'手机/微信均为空，跳过手机号微信查重，候选人={self.name}，当前岗位={self.position_id}')
            self.is_duplicate = False
            self.resume_id = None
            self.is_duplicate_with_current_position = False
            return

        response = duplicate(
            user_id=self.incharge_id,
            position_id=self.position_id,
            phone=phone,
            vx=vx,
        )
        try:
            duplicate_response = get_ah_result_dict(response)
        except Exception:
            raw_text = getattr(response, 'text', '')
            logger.exception(
                f'手机号/微信查重返回非 JSON，候选人={self.name}，当前岗位={self.position_id}，'
                f'phone_empty={not bool(phone)}，wechat_empty={not bool(vx)}，'
                f'status_code={getattr(response, "status_code", "unknown")}，'
                f'response_preview={raw_text[:500]!r}'
            )
            raise
        if '1' == duplicate_response['duplicate']:
            records = duplicate_response.get('data', [])
            current_record = _find_current_position_record(records, self.position_id)
            if current_record:
                self.is_duplicate = True
                self.resume_id = current_record['id']
                self.is_duplicate_with_current_position = True
            else:
                duplicate_position_ids = [record.get('position_id') for record in records]
                logger.info(
                    f'手机/微信查重仅命中其他岗位，按当前岗位新人处理，候选人={self.name}，当前岗位={self.position_id}，重复岗位={duplicate_position_ids}'
                )
                self.is_duplicate = False
                self.resume_id = None
                self.is_duplicate_with_current_position = False

    def check_is_duplicate_with_smart_code(self, smart_code):
        logger.warning(f'check_is_duplicate_with_smart_code 已废弃，候选人={self.name}，请改用 smart_keywords 统一查重')
        duplicate_response = get_ah_result_dict(
            duplicate(
                user_id=self.incharge_id,
                position_id=self.position_id,
                smart_keywords=smart_code,
            )
        )
        if str(duplicate_response.get('duplicate', '')).lower() in ('1', 'yes', 'true'):
            records = duplicate_response.get('data', [])
            current_record = _find_current_position_record(records, self.position_id)
            if current_record:
                self.is_duplicate = True
                self.resume_id = current_record['id']
                self.is_duplicate_with_current_position = True
            else:
                duplicate_position_ids = [record.get('position_id') for record in records]
                logger.info(
                    f'smart_code 查重仅命中其他岗位，按当前岗位新人处理，候选人={self.name}，当前岗位={self.position_id}，重复岗位={duplicate_position_ids}'
                )
                self.is_duplicate = False
                self.resume_id = None
                self.is_duplicate_with_current_position = False

    def check_is_clients(self):
        if 'client' == get_ah_result_dict(get_user_role(self.incharge_id))['type']:
            self.is_clients = True
        else:
            self.is_clients = False

    def set_incharge_id_by_recommend_id(self, recommend_id):
        if 'client' == get_ah_result_dict(get_user_role(recommend_id))['type']:
            self.is_clients = True
        else:
            self.is_clients = False

        if self.is_clients:
            self.incharge_id = recommend_id
        else:
            self.incharge_id = 834

    def get_md_text(self, phone=None, vx=None):
        raw_resume_dict = json.loads(self.rawResume)
        clean_resume_dict = select_field_in_resume(raw_resume_dict)

        md_text = chatBot.send(json.dumps(clean_resume_dict, ensure_ascii=False), ENUM_MODEL_ID.RESUME_TRANSLATOR)

        md_split = md_text.split('---')

        if phone:
            md_split[0] = f'{md_split[0]}\n### 手机号: {phone}'
        if vx:
            md_split[0] = f'{md_split[0]}\n### 微信号: {vx}'

        md_text = '\n---\n'.join(md_split)

        return md_text

    def check_status(self, check_test):
        if '不匹配' == check_test:
            status = '待筛选'
        else:
            status = '初审待定'

        return status

    def upload_screening_resume_to_anyJob(self):
        self.check_is_clients()

        self.check_screening_is_duplicate_with_smart_keywords()

        # 查重
        if self.is_duplicate_pass:
            return

        self.set_fact_check()

        # 事实判断
        if self.fact_check_comment_label == '不匹配':
            return

        rawResume_dict = json.loads(self.rawResume)

        clean_rawResume_dict = select_field_in_resume(rawResume_dict)

        clean_resume = chatBot.send(json.dumps(clean_rawResume_dict), ENUM_MODEL_ID.GET_CLEAN_RESUME)

        # 判断是否是客户,做备注拼接逻辑
        recommendation = RegexUtils.extract_recommendation(clean_resume)
        if self.is_clients:
            comment = f"{self.fact_check_comment_label}，{recommendation[0]}"
        else:
            # 如果不是客户岗位
            # 重复了
            if self.is_duplicate:
                comment = f"重复：{'，'.join(self.duplicate_position_name_list)}" + '，' + f'{self.fact_check_comment}'
            else:
                comment = f"{self.fact_check_comment_label}，{'，'.join(self.fact_check_comment.split('，')[3:])}"

        self.set_simple_resume()

        salary = self.salary or ''
        if not salary:
            salary_matches = RegexUtils.extract_salary(clean_resume)
            if salary_matches:
                salary = salary_matches[0]

        location = RegexUtils.extract_location(clean_resume)

        tags = RegexUtils.extract_tags(clean_resume)

        last_active_timestamp = clean_rawResume_dict['user']['lastActiveTime']
        dt = datetime.fromtimestamp(last_active_timestamp / 1000)
        active_time_str = dt.strftime("%Y-%m-%d")

        # 每判断一个合适上传人才，h5发帖一次
        h5_post(self.position_id, '发现匹配人才', f'姓名：{"智联 " + self.name} 匹配原因：{comment}')

        params = {
            'name': self.name,
            'liepin_keywords': self.liepin_keywords,
            'smart_keywords': self.smart_keywords,
            'current_company': self.currentCompany,
            'current_position': self.currentPosition,
            'resume_content': clean_resume,
            'ai_summary': self.simple_resume,
            'comment': comment,
            'source': ENUM_CANDIDATE_CLASSIFY.ZHI_LIAN.value,
        }
        # 上传教育字段独立选取，保留 self.schoolName/self.major 及查重键的原有含义。
        params.update(get_highest_education_fields(
            _safe_dict(rawResume_dict.get('resume')).get('educationExperiences')
        ))

        if active_time_str:
            params['activity_time'] = active_time_str
        if salary:
            params['salary'] = salary
        if self.age not in (None, ''):
            params['age'] = self.age
        if location:
            params['location'] = location[0]

        if tags:
            params['tags'] = tags[0]

        log_resume_diagnostic(
            logger,
            "anyjob_screening_upload_request",
            **self._resume_diagnostic_fields(),
            normalized_company=self.currentCompany,
            normalized_position=self.currentPosition,
            salary=salary,
            age=self.age,
            location=params.get("location", ""),
            activity_time=active_time_str,
        )
        response = add_screening_resume(
            position_id=self.position_id,
            incharge_id=self.incharge_id,
            status='待联系',
            coins_cost=2,
            **params
        )
        log_resume_diagnostic(
            logger,
            "anyjob_screening_upload_response",
            **self._resume_diagnostic_fields(),
            **summarize_http_response(response),
        )

    def upload_chat_history_and_tags(self, chat_history):
        return self.sync_high_potential_by_smart_keywords(chat_history=chat_history)

    def sync_high_potential_by_smart_keywords(self, chat_history, phone=None, vx=None, rule_tag=None, activity_time=None):
        self.check_screening_is_duplicate_with_smart_keywords()
        if not self.is_duplicate_with_current_position:
            return False

        chat_history = redact_contact_text(chat_history)
        if rule_tag:
            chat_tag = rule_tag
        else:
            chat_tag = chatBot.send(f"【历史聊天记录：】{chat_history}", ENUM_MODEL_ID.GET_CHAT_TAGS)
        update_kwargs = {
            'chat_history': chat_history,
            'chat_tags': chat_tag,
        }
        if phone:
            update_kwargs['phone'] = phone
        if vx:
            update_kwargs['wechat'] = vx
        if activity_time:
            if isinstance(activity_time, datetime):
                update_kwargs['activity_time'] = activity_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                update_kwargs['activity_time'] = str(activity_time)

        update_screening_resume(self.resume_id, **update_kwargs)
        logger.info(
            f"高潜 smart_keywords 同步完成，候选人={self.name}，position_id={self.position_id}，"
            f"screening_id={self.resume_id}"
        )
        return True

    def _compute_upload_coins_cost(self, chat_history, status_tags) -> int:
        return compute_upload_resume_coins_cost(self.fact_check_comment_label, chat_history, status_tags)

    def _get_existing_resume_chat_history(self):
        if not self.resume_id:
            return ""
        try:
            response = get_resume_data(self.resume_id)
            return _extract_chat_history(get_ah_result_dict(response))
        except Exception:
            logger.exception(f"读取已有聊天记录失败，候选人={self.name}，resume_id={self.resume_id}")
            return ""

    def _merge_existing_chat_history(self, chat_history):
        existing_chat_history = self._get_existing_resume_chat_history()
        return get_duplicate_full_chat_history(existing_chat_history, chat_history)

    def upload_resume_to_anyJob(self, phone, vx, chat_history, recommend_id, account_name, rule_tag=None):
        self.set_incharge_id_by_recommend_id(recommend_id)
        account_name = str(account_name or '未知账号').strip() or '未知账号'
        chat_history = redact_contact_text(chat_history)

        self.is_duplicate_with_current_position = False
        # 意向查重（优先 smart_keywords，电话/微信兜底）
        duplicate_synced = self.sync_high_potential_by_smart_keywords(
            chat_history=chat_history,
            phone=phone,
            vx=vx,
            rule_tag=rule_tag,
        )
        if duplicate_synced:
            # 高潜记录与正式人才使用不同的 ID 空间。同步高潜后清空高潜查重状态，
            # 继续执行正式人才查重/入库，避免把 screening_id 当作 resume_id。
            self._reset_duplicate_state()

        self.check_is_duplicate_with_phone_wx(phone, vx)

        if self.is_duplicate_with_current_position:
            merged_chat_history = self._merge_existing_chat_history(chat_history)
            update_chat_history(self.resume_id, merged_chat_history)
            status_tags = chatBot.send(f'【聊天记录：】{merged_chat_history}', ENUM_MODEL_ID.GET_TAG_BY_CHAT_HISTORY)
            update_status_tag(self.resume_id, status_tags)
            return

        self.is_duplicate_with_current_position = False

        self.set_fact_check()

        # 事实判断
        if self.fact_check_comment_label == '不匹配':
            check_label = '一般匹配'
        else:
            check_label = self.fact_check_comment_label

        md_resume = self.get_md_text(phone, vx)

        status_tags = chatBot.send(f'【聊天记录：】{chat_history}', ENUM_MODEL_ID.GET_TAG_BY_CHAT_HISTORY)

        status = self.check_status(self.fact_check_comment_label)

        if self.is_clients:
            comment = f'{check_label}' + '，' + f"{'，'.join(self.fact_check_comment.split('，')[3:])}"
        else:
            comment = f'{self.fact_check_comment}'

        coins_cost = self._compute_upload_coins_cost(chat_history, status_tags)

        h5_post(self.position_id, '意向人选上传',
                f'来自{self.currentCompany}的{self.name}已上传系统中')

        log_resume_diagnostic(
            logger,
            "anyjob_resume_upload_request",
            **self._resume_diagnostic_fields(),
            recommend_id=recommend_id,
            coins_cost=coins_cost,
            status=status,
        )
        res = add_resume(
            position_id=self.position_id,
            resume=md_resume,
            user_id=self.incharge_id,
            smart_keywords=self.smart_keywords,
            status=status,
            comment=comment,
            recommend_by=recommend_id,
            status_tags=status_tags,
            chat_history=f'{chat_history} \n智联账号:{account_name}',
            coins_cost=coins_cost,
            source=ENUM_CANDIDATE_CLASSIFY.ZHI_LIAN.value,
            resume_tags=255
        )
        log_resume_diagnostic(
            logger,
            "anyjob_resume_upload_response",
            **self._resume_diagnostic_fields(),
            **summarize_http_response(res),
        )
        res = update_resume(
            resume_id=res.json()['data'][0],
            other_expected_locations=self.now_region
        )

    def to_excel_row(self, filepath: Union[str, Path]):
        filepath = Path(filepath)

        if filepath.exists():
            # ✅ 文件存在：加载并追加数据行
            generator = excel_generator(filepath)
            generator.add_data_object_row(self, EXECL_ATTRIBUTES)
            generator.save()
            logger.info(f"已在 {filepath} 追加一行数据。")
        else:
            # ✅ 文件不存在：新建文件并写入表头
            generator = excel_generator(filepath)
            generator.set_headers(EXECL_HEADER)  # 仅第一次写表头
            generator.add_data_object_row(self, EXECL_ATTRIBUTES)
            generator.save()
            logger.info(f"新建 Excel 文件并写入首行数据：{filepath}")

    @classmethod
    def from_raw_resume(cls, raw_resume_dict, position_id, incharge_id=None):
        data = _safe_dict(raw_resume_dict)
        user = _safe_dict(data.get('user'))
        resume = _safe_dict(data.get('resume'))

        # 安全获取列表中第一个元素，否则返回空字典
        work_exps = resume.get('workExperiences') or []
        edu_exps = resume.get('educationExperiences') or []
        purposes = resume.get('purposes') or []

        work = _safe_dict(work_exps[0]) if len(work_exps) > 0 else {}
        edu = _safe_dict(edu_exps[0]) if len(edu_exps) > 0 else {}
        purpose = _safe_dict(purposes[0]) if len(purposes) > 0 else {}

        # 安全提取字段（不存在则置空字符串）
        name = user.get('name', '')
        currentCompany = work.get('orgName', '')
        currentPosition = work.get('jobTitle', '')
        schoolName = edu.get('schoolName', '')
        major = edu.get('major', '')
        age = user.get('age')
        if age in (None, ''):
            age_label = str(user.get('ageLabel', '')).strip()
            age_match = re.search(r'\d+', age_label)
            age = int(age_match.group(0)) if age_match else ''
        salary = purpose.get('salaryLabel', '')
        if salary:
            try:
                salary = chatBot.send(salary, ENUM_MODEL_ID.GET_CLEAN_SALARY.value)
            except Exception:
                logger.exception(f'薪资清洗模型失败，跳过薪资字段，候选人={name}，原始薪资={salary}')
                salary = ''
        now_region = user.get('cityName','')

        # 最近活跃时间（可能不存在）
        last_active_time = user.get('lastActiveTime')
        recentActiveTime = None
        if last_active_time:
            try:
                recentActiveTime = datetime.fromtimestamp(last_active_time / 1000)
            except Exception:
                recentActiveTime = None

        if incharge_id:
            incharge_id = incharge_id
        else:
            incharge_id = get_ah_result_dict(get_incharge_id_by_position_id(position_id))['results'][0]['incharge_id']

        candidate = cls(
            name=name,
            currentCompany=currentCompany,
            currentPosition=currentPosition,
            schoolName=schoolName,
            major=major,
            rawResume=json.dumps(data, ensure_ascii=False),
            salary=salary,
            age=age,
            position_id=position_id,
            incharge_id=incharge_id,
            recentActiveTime=recentActiveTime,
            now_region=now_region
        )
        candidate.source_user_id = user.get("id")
        candidate.source_resume_id = resume.get("id")
        candidate.resume_payload_sha256 = stable_data_sha256(data)
        log_resume_diagnostic(
            logger,
            "candidate_resume_parsed",
            **candidate._resume_diagnostic_fields(),
            education_experiences=summarize_education_experiences(edu_exps),
            selected_education_index=0 if edu_exps else None,
            raw_identity_fields={
                "name": name,
                "company": currentCompany,
                "position": currentPosition,
                "school": schoolName,
                "major": major,
            },
            normalized_identity_fields={
                "name": Candidate._collapse_spaces(name),
                "company": Candidate._collapse_spaces(currentCompany),
                "position": Candidate._collapse_spaces(currentPosition),
                "school": Candidate._collapse_spaces(schoolName),
                "major": Candidate._collapse_spaces(major),
            },
            smart_keywords_candidates=candidate.smart_keywords_candidates,
        )
        return candidate



# Manual demo removed from repository import; use synthetic fixtures for local testing.
