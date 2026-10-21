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
import time
import unicodedata
from pathlib import Path
from typing import Union
import traceback

import requests
import backend.api.chatBotApi as chatBot
from backend.config.execl_config import EXECL_HEADER, EXECL_ATTRIBUTES
from datetime import datetime
from backend.api.anyJobApi import get_job_data, duplicate_screening, add_screening_resume, \
    h5_post, get_user_role, get_ah_result_dict, add_resume, duplicate, update_screening_resume, update_chat_history, \
    update_status_tag, update_resume, AnyJobResponseError, summarize_anyjob_response
from backend.config.anyJobConfig import ENUM_CANDIDATE_CLASSIFY
from backend.config.chatBotApiConfig import ENUM_MODEL_ID
from backend.entity.feichu_spider import FSSpider
from backend.logger.logger import get_logger
from backend.utils.excel_generator.excel_generator import excel_generator
from backend.utils.filePathUtils.FilePathUtils import get_save_path, ensure_dir_exists
from backend.utils.regex.regex_utils import RegexUtils
from backend.utils.highest_education import extract_highest_education
from backend.utils.resume_upload_ledger import record_upload as record_resume_upload, get_record as get_resume_upload_record
logger = get_logger(__name__)

# GET_TAG_BY_CHAT_HISTORY 返回的主标签整型：强意向需先于 >=109 的「非常匹配」分支处理
STATUS_TAG_STRONG_INTENT = 256
TAG_THRESHOLD_FOR_60 = 109
ALLOWED_CHAT_TAGS = {
    '地点不考虑',
    '薪资不符合',
    '岗位不匹配',
    '不感兴趣',
    '未读消息',
    '已读不回',
    '有意向沟通',
    '被联系过了',
    '不看机会',
}
TAG_PRIORITY = [
    '不感兴趣',
    '岗位不匹配',
    '薪资不符合',
    '地点不考虑',
    '不看机会',
    '有意向沟通',
    '未读消息',
    '已读不回',
    '被联系过了',
]
DEFAULT_SINGLE_CHAT_TAG = '被联系过了'


class Candidate:
    # smart_keywords 候选总数上限：分隔符 × 职位变体 × 括号形态变体 三维笛卡尔积后做去重，
    # 这里再加一道保险，避免极端字段组合下 candidate 爆炸引发过多 duplicate_screening 调用。
    MAX_SMART_KEYWORD_CANDIDATES = 36
    DUPLICATE_CHECK_RETRY_TIMES = 3
    DUPLICATE_CHECK_RETRY_GAP = 1

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
            gold_collar=None,
            link: str = "",
            encode_res_id: str = "",
            recentActiveTime: datetime = None,
            age=None,
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
        self.encode_res_id = encode_res_id
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
        self._md_text_cache = {}
        self.resume_detail_response_text = None
        self.work_exp_response_text = None
        self.last_screening_duplicate_keyword = ''
        self.last_screening_duplicate_reason = ''
        self.last_screening_chat_tag = ''
        self.diagnostic_trace_id = ''

    def set_simple_resume(self):
        self.simple_resume = chatBot.send(self.rawResume, ENUM_MODEL_ID.GET_SIMPLE_RESUME)

    def set_job_requirement(self):
        self.job_requirement = get_ah_result_dict(get_job_data(self.position_id))['results'][0][
            'summary']
        self.job_deep_requirement = self.job_requirement.split('深匹要求：')[1]

    def set_first_check(self):
        self.set_job_requirement()

        self.firstCheckComment = chatBot.send(f'【个人信息：】{self.rawResume}【岗位要求：】{self.job_deep_requirement}',
                                              ENUM_MODEL_ID.GET_FIRST_CHECK,
                                              trace_id=self.diagnostic_trace_id)
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
            ENUM_MODEL_ID.GET_FACT_CHECK,
            trace_id=self.diagnostic_trace_id)
        if '不匹配' in self.fact_check_comment:
            self.fact_check_comment_label = '不匹配'
        elif '非常匹配' in self.fact_check_comment:
            self.fact_check_comment_label = '非常匹配'
        else:
            self.fact_check_comment_label = '匹配'

    def check_screening_is_duplicate_with_resume_code(self):
        self.is_duplicate = False
        self.is_duplicate_pass = False
        self.is_duplicate_with_current_position = False
        self.duplicate_position_id_list = []
        self.duplicate_position_name_list = []
        self.resume_id = None
        self.last_screening_duplicate_keyword = ''
        self.last_screening_duplicate_reason = ''

        if not self.incharge_id:
            logger.warning(f'smart_keywords 查重跳过，候选人={self.name}，原因=缺少 incharge_id')
            self.last_screening_duplicate_reason = 'missing_incharge_id'
            self._dump_resume_code_debug_snapshot(
                reason='missing_incharge_id',
                duplicate_request_payload={
                    'user_id': self.incharge_id,
                    'position_id': self.position_id,
                    'smart_keywords': self.smart_keywords,
                }
            )
            return

        if not self.position_id:
            logger.warning(f'smart_keywords 查重跳过，候选人={self.name}，原因=缺少 position_id')
            self.last_screening_duplicate_reason = 'missing_position_id'
            self._dump_resume_code_debug_snapshot(
                reason='missing_position_id',
                duplicate_request_payload={
                    'user_id': self.incharge_id,
                    'position_id': self.position_id,
                    'smart_keywords': self.smart_keywords,
                }
            )
            return

        if not self.smart_keywords:
            logger.warning(f'smart_keywords 查重跳过，候选人={self.name}，原因=smart_keywords 为空')
            self.last_screening_duplicate_reason = 'missing_smart_keywords'
            self._dump_resume_code_debug_snapshot(
                reason='missing_smart_keywords',
                duplicate_request_payload={
                    'user_id': self.incharge_id,
                    'position_id': self.position_id,
                    'smart_keywords': self.smart_keywords,
                }
            )
            return

        keywords_candidates = self.smart_keywords_candidates or [self.smart_keywords]
        current_position_id = Candidate._normalize_id(self.position_id)
        logger.info(
            f"高潜查重开始，candidate={self.name}，position_id={self.position_id}，"
            f"user_id={self.incharge_id}，resume_code={self.link or 'none'}，"
            f"smart_keywords_default={self.smart_keywords}，candidate_count={len(keywords_candidates)}，"
            f"smart_keywords_candidates={keywords_candidates}"
        )

        for keyword in keywords_candidates:
            logger.info(
                f"高潜查重请求，candidate={self.name}，position_id={self.position_id}，"
                f"user_id={self.incharge_id}，smart_keyword={keyword}"
            )
            duplicate_raw_response = duplicate_screening(
                user_id=self.incharge_id,
                position_id=self.position_id,
                smart_keywords=keyword,
                trace_id=self.diagnostic_trace_id,
            )
            duplicate_response = self._parse_duplicate_screening_response(duplicate_raw_response)
            if duplicate_response is None:
                self.last_screening_duplicate_reason = 'duplicate_response_invalid'
                logger.info(
                    f"高潜查重响应无效，candidate={self.name}，position_id={self.position_id}，"
                    f"smart_keyword={keyword}，reason={self.last_screening_duplicate_reason}"
                )
                continue

            records = duplicate_response.get('records') or []
            duplicate_flag = str(duplicate_response.get('duplicate', '')).lower()
            record_positions = [Candidate._normalize_id(item.get('position_id')) for item in records]
            logger.info(
                f"高潜查重响应，candidate={self.name}，position_id={self.position_id}，"
                f"smart_keyword={keyword}，duplicate={duplicate_response.get('duplicate')}，"
                f"records_count={len(records)}，record_positions={record_positions}"
            )
            if duplicate_flag not in ('yes', '1', 'true'):
                continue

            self.is_duplicate = True
            self.last_screening_duplicate_keyword = keyword
            self.last_screening_duplicate_reason = 'duplicate_hit'

            for duplicate_position in records:
                duplicate_position_id = duplicate_position.get('position_id')
                self.duplicate_position_id_list.append(duplicate_position_id)
                self.duplicate_position_name_list.append(duplicate_position.get('Position', '未知岗位'))
                if Candidate._normalize_id(duplicate_position_id) == current_position_id:
                    self.is_duplicate_pass = True
                    self.is_duplicate_with_current_position = True
                    self.resume_id = duplicate_position.get('id')
                    logger.info(
                        f'与当前岗位重复，候选人={self.name}，position_id={self.position_id}，'
                        f'smart_keywords={keyword}，screening_id={self.resume_id}'
                    )
                    return

            logger.info(
                f"高潜查重命中但当前岗位未命中，candidate={self.name}，position_id={self.position_id}，"
                f"smart_keyword={keyword}，record_positions={record_positions}"
            )

        if self.is_duplicate and not self.is_duplicate_with_current_position:
            self.last_screening_duplicate_reason = 'duplicate_not_current_position'
            logger.info(
                f'高潜查重命中但未命中当前岗位，候选人={self.name}，当前岗位={self.position_id}，'
                f'smart_keywords_candidates={keywords_candidates}，重复岗位={self.duplicate_position_id_list}'
            )
        elif not self.is_duplicate:
            self.last_screening_duplicate_reason = 'duplicate_not_found'
            self.is_duplicate_pass = False
            logger.info(
                f"高潜查重结束未命中，candidate={self.name}，position_id={self.position_id}，"
                f"reason={self.last_screening_duplicate_reason}，"
                f"smart_keywords_candidates={keywords_candidates}"
            )

    def _parse_duplicate_screening_response(self, response):
        if response is None:
            logger.warning(f'smart_keywords 查重失败，候选人={self.name}，原因=响应为空')
            self.last_screening_duplicate_reason = 'duplicate_response_none'
            self._dump_resume_code_debug_snapshot(reason='duplicate_response_none')
            return None

        response_text = ''
        try:
            response_text = response.content.decode('utf-8', errors='replace')
        except Exception:
            response_text = str(getattr(response, 'text', ''))

        try:
            payload = json.loads(response_text)
        except Exception as e:
            logger.warning(
                f'smart_keywords 查重失败，候选人={self.name}，原因=响应不是有效 JSON，'
                f'status_code={getattr(response, "status_code", None)}，body={response_text[:300]}'
            )
            self.last_screening_duplicate_reason = 'duplicate_response_not_json'
            self._dump_resume_code_debug_snapshot(
                reason='duplicate_response_not_json',
                duplicate_request_payload={
                    'user_id': self.incharge_id,
                    'position_id': self.position_id,
                    'smart_keywords': self.smart_keywords,
                },
                duplicate_response_text=response_text,
                duplicate_response_status=getattr(response, 'status_code', None),
                error=str(e),
            )
            return None

        if not isinstance(payload, dict):
            logger.warning(f'smart_keywords 查重失败，候选人={self.name}，原因=响应 JSON 不是对象')
            self.last_screening_duplicate_reason = 'duplicate_response_not_dict'
            self._dump_resume_code_debug_snapshot(
                reason='duplicate_response_not_dict',
                duplicate_request_payload={
                    'user_id': self.incharge_id,
                    'position_id': self.position_id,
                    'smart_keywords': self.smart_keywords,
                },
                duplicate_response_text=response_text,
                duplicate_response_status=getattr(response, 'status_code', None),
            )
            return None

        return payload

    def check_is_duplicate_with_smart_keywords(self):
        self.is_duplicate = False
        self.is_duplicate_with_current_position = False
        self.resume_id = None

        if not self.incharge_id:
            logger.warning(f'人才库 smart_keywords 查重跳过，候选人={self.name}，原因=缺少 incharge_id')
            return
        if not self.position_id:
            logger.warning(f'人才库 smart_keywords 查重跳过，候选人={self.name}，原因=缺少 position_id')
            return
        if not self.smart_keywords:
            logger.warning(f'人才库 smart_keywords 查重跳过，候选人={self.name}，原因=smart_keywords 为空')
            return

        keywords_candidates = self.smart_keywords_candidates or [self.smart_keywords]
        for index, keyword in enumerate(keywords_candidates, start=1):
            logger.info(
                f'【调试】人才库 smart_keywords 查重请求，候选人={self.name}，'
                f'user_id={self.incharge_id}，position_id={self.position_id}，'
                f'candidate={index}/{len(keywords_candidates)}，smart_keywords={keyword}'
            )
            duplicate_response = self._duplicate_with_retry(
                'smart_keywords',
                user_id=self.incharge_id,
                position_id=self.position_id,
                smart_keywords=keyword,
            )
            duplicate_data_len = len(duplicate_response.get('data') or []) if isinstance(duplicate_response, dict) else 0
            logger.info(
                f'【调试】人才库 smart_keywords 查重响应，候选人={self.name}，'
                f'candidate={index}/{len(keywords_candidates)}，'
                f'duplicate={duplicate_response.get("duplicate") if isinstance(duplicate_response, dict) else "invalid"}，'
                f'data_len={duplicate_data_len}'
            )
            duplicate_flag = str(duplicate_response.get('duplicate', '')).lower()
            if duplicate_flag in ('yes', '1', 'true'):
                self.is_duplicate = True
                duplicate_data = duplicate_response.get('data') or []
                if duplicate_data:
                    self.resume_id = duplicate_data[0].get('id')
                for duplicate_position in duplicate_data:
                    duplicate_position_id = duplicate_position.get('position_id')
                    if Candidate._normalize_id(duplicate_position_id) == Candidate._normalize_id(self.position_id):
                        self.is_duplicate_with_current_position = True
                        self.resume_id = duplicate_position.get('id')
                        break
                logger.info(
                    f'人才库 smart_keywords 查重命中，候选人={self.name}，position_id={self.position_id}，'
                    f'resume_id={self.resume_id}，is_current_position={self.is_duplicate_with_current_position}，'
                    f'smart_keywords={keyword}'
                )
                return

        logger.info(
            f'人才库 smart_keywords 查重未命中，候选人={self.name}，position_id={self.position_id}，'
            f'smart_keywords_candidates={keywords_candidates}'
        )

    def _check_local_upload_ledger(self, encode_res_id):
        normalized_encode_res_id = Candidate._normalize_id(encode_res_id)
        if not normalized_encode_res_id:
            return False

        record = get_resume_upload_record(self.position_id, normalized_encode_res_id)
        if not record:
            return False

        self.is_duplicate = True
        self.is_duplicate_with_current_position = True
        self.resume_id = record.get('resume_id')
        logger.info(
            f'本地上传台账命中，候选人={self.name}，position_id={self.position_id}，'
            f'encode_res_id={normalized_encode_res_id}，resume_id={self.resume_id}，'
            f'uploaded_at={record.get("uploaded_at") or "unknown"}'
        )
        return True

    def _record_local_upload_ledger(self, encode_res_id, resume_id):
        normalized_encode_res_id = Candidate._normalize_id(encode_res_id or self.encode_res_id)
        if not normalized_encode_res_id or not resume_id:
            return
        record_resume_upload(
            self.position_id,
            normalized_encode_res_id,
            resume_id,
            self.name,
        )

    def _duplicate_with_retry(self, source_label, **kwargs):
        for attempt in range(1, self.DUPLICATE_CHECK_RETRY_TIMES + 1):
            try:
                return get_ah_result_dict(duplicate(**kwargs))
            except AnyJobResponseError as e:
                logger.warning(
                    f'AnyJob duplicate check response invalid, source={source_label}, '
                    f'attempt={attempt}/{self.DUPLICATE_CHECK_RETRY_TIMES}, '
                    f'candidate={self.name}, position_id={self.position_id}, error={e}'
                )
                if attempt >= self.DUPLICATE_CHECK_RETRY_TIMES:
                    logger.warning(
                        f'AnyJob duplicate check failed after retries, source={source_label}, '
                        f'candidate={self.name}, position_id={self.position_id}'
                    )
                    raise
                time.sleep(self.DUPLICATE_CHECK_RETRY_GAP)
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f'AnyJob duplicate check request failed after http retries, source={source_label}, '
                    f'candidate={self.name}, position_id={self.position_id}, error={e}'
                )
                raise AnyJobResponseError('AnyJob duplicate check request failed') from e

    def _check_duplicate_by_link_value(self, link_value, source_label):
        normalized_link = Candidate._normalize_id(link_value)
        if not normalized_link:
            logger.info(
                f'人才库 {source_label} 查重跳过，候选人={self.name}，原因=标识为空'
            )
            return
        if not self.incharge_id:
            logger.warning(
                f'人才库 {source_label} 查重跳过，候选人={self.name}，原因=缺少 incharge_id'
            )
            return
        if not self.position_id:
            logger.warning(
                f'人才库 {source_label} 查重跳过，候选人={self.name}，原因=缺少 position_id'
            )
            return

        self.is_duplicate = False
        self.is_duplicate_with_current_position = False
        self.resume_id = None

        logger.info(
            f'【调试】人才库 {source_label} 查重请求，候选人={self.name}，'
            f'user_id={self.incharge_id}，position_id={self.position_id}，link={normalized_link}'
        )
        duplicate_response = self._duplicate_with_retry(
            source_label,
            user_id=self.incharge_id,
            position_id=self.position_id,
            link=normalized_link,
        )
        duplicate_data_len = len(duplicate_response.get('data') or []) if isinstance(duplicate_response, dict) else 0
        logger.info(
            f'【调试】人才库 {source_label} 查重响应，候选人={self.name}，'
            f'duplicate={duplicate_response.get("duplicate") if isinstance(duplicate_response, dict) else "invalid"}，'
            f'data_len={duplicate_data_len}'
        )
        duplicate_flag = str(duplicate_response.get('duplicate', '')).lower()
        if duplicate_flag in ('yes', '1', 'true'):
            self.is_duplicate = True
            duplicate_data = duplicate_response.get('data') or []
            if duplicate_data:
                self.resume_id = duplicate_data[0].get('id')
            for duplicate_position in duplicate_data:
                duplicate_position_id = duplicate_position.get('position_id')
                if Candidate._normalize_id(duplicate_position_id) == Candidate._normalize_id(self.position_id):
                    self.is_duplicate_with_current_position = True
                    self.resume_id = duplicate_position.get('id')
                    break
            logger.info(
                f'人才库 {source_label} 查重命中，候选人={self.name}，position_id={self.position_id}，'
                f'resume_id={self.resume_id}，is_current_position={self.is_duplicate_with_current_position}，'
                f'link={normalized_link}'
            )
        else:
            logger.info(
                f'人才库 {source_label} 查重未命中，候选人={self.name}，position_id={self.position_id}，'
                f'link={normalized_link}'
            )

    def check_is_duplicate_with_encode_res_id(self, encode_res_id=None):
        self._check_duplicate_by_link_value(
            encode_res_id or self.encode_res_id,
            'encodeResId',
        )

    def check_is_duplicate_with_link(self):
        self._check_duplicate_by_link_value(self.link, 'link')

    def check_is_duplicate_with_phone_vx(self, phone=None, vx=None):
        self.is_duplicate = False
        self.is_duplicate_with_current_position = False
        self.resume_id = None

        contact_fields = Candidate._build_resume_contact_fields(phone, vx)
        if not contact_fields:
            logger.info(
                f'人才库 phone/vx 查重跳过，候选人={self.name}，原因=联系方式为空'
            )
            return

        logger.info(
            f'【调试】人才库 phone/vx 查重请求，候选人={self.name}，'
            f'user_id={self.incharge_id}，position_id={self.position_id}，'
            f'phone={"有" if contact_fields.get("phone") else "无"}，'
            f'weixin={"有" if contact_fields.get("weixin") else "无"}'
        )
        duplicate_response = self._duplicate_with_retry(
            'phone/vx',
            user_id=self.incharge_id,
            position_id=self.position_id,
            phone=contact_fields.get('phone'),
            vx=contact_fields.get('weixin'),
        )
        duplicate_data_len = len(duplicate_response.get('data') or []) if isinstance(duplicate_response, dict) else 0
        logger.info(
            f'【调试】人才库 phone/vx 查重响应，候选人={self.name}，'
            f'duplicate={duplicate_response.get("duplicate") if isinstance(duplicate_response, dict) else "invalid"}，'
            f'data_len={duplicate_data_len}'
        )
        duplicate_flag = str(duplicate_response.get('duplicate', '')).lower()
        if duplicate_flag in ('yes', '1', 'true'):
            self.is_duplicate = True
            duplicate_data = duplicate_response.get('data') or []
            if duplicate_data:
                self.resume_id = duplicate_data[0].get('id')
            for duplicate_position in duplicate_data:
                duplicate_position_id = duplicate_position.get('position_id')
                if Candidate._normalize_id(duplicate_position_id) == Candidate._normalize_id(self.position_id):
                    self.is_duplicate_with_current_position = True
                    self.resume_id = duplicate_position.get('id')
                    break
            logger.info(
                f'人才库 phone/vx 查重命中，候选人={self.name}，position_id={self.position_id}，'
                f'resume_id={self.resume_id}，is_current_position={self.is_duplicate_with_current_position}'
            )
        else:
            logger.info(
                f'人才库 phone/vx 查重未命中，候选人={self.name}，position_id={self.position_id}'
            )

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
        cache_key = (Candidate._normalize_id(phone), Candidate._normalize_id(vx))
        cached_md_text = self._md_text_cache.get(cache_key)
        if cached_md_text:
            logger.info(
                f"复用已生成的简历解析结果，候选人={self.name}，phone={'有' if phone else '无'}，vx={'有' if vx else '无'}"
            )
            return cached_md_text

        logger.info(
            f"开始调用简历解析工具，候选人={self.name}，phone={'有' if phone else '无'}，vx={'有' if vx else '无'}"
        )

        md_text = chatBot.send(self.rawResume, ENUM_MODEL_ID.RESUME_TRANSLATOR)

        md_split = md_text.split('---')

        if phone:
            md_split[0] = f'{md_split[0]}\n### 手机号: {phone}'
        if vx:
            md_split[0] = f'{md_split[0]}\n### 微信号: {vx}'

        md_text = '\n---\n'.join(md_split)
        self._md_text_cache[cache_key] = md_text

        return md_text

    def check_status(self, check_test):
        if '不匹配' == check_test:
            status = '待筛选'
        else:
            status = '初审待定'

        return status
    def position_question_check(self,chat_history,position_question):
        bot_reply = chatBot.send(f"【历史聊天记录：】{chat_history}【岗位问题：】{position_question}",ENUM_MODEL_ID.SON_POSITION_QUESTION_CHECK)
        if bot_reply == '是':
            return True
        else:
            return False

    @staticmethod
    def prepend_comment_prefix(comment, prefix):
        if not comment:
            return prefix
        return f"{prefix}，{comment}"

    @staticmethod
    def _build_resume_contact_fields(phone=None, vx=None):
        """与 duplicate.php 字段对齐，确保联系方式写入结构化索引供后续查重命中。"""
        fields = {}
        normalized_phone = Candidate._normalize_id(phone)
        normalized_vx = Candidate._normalize_id(vx)
        if normalized_phone:
            fields['phone'] = normalized_phone
        if normalized_vx:
            # duplicate.php 使用 weixin；初筛接口使用 wechat，add-resume 与 duplicate 保持一致。
            fields['weixin'] = normalized_vx
        return fields

    @staticmethod
    def _compute_coins_cost(fact_check_comment_label: str, status_tags, chat_history: str) -> int:
        """人才库上传金币：优先「有回复但未通过初审→30」，再「通过初审且强意向→80」等。"""
        text = chat_history or ''
        has_candidate_reply = '候选人：' in text
        not_passed_initial = '不匹配' in fact_check_comment_label
        passed_initial = not not_passed_initial
        tag_int = int(status_tags)

        if has_candidate_reply and not_passed_initial:
            return 30
        if passed_initial and tag_int == STATUS_TAG_STRONG_INTENT:
            return 80
        if passed_initial and not has_candidate_reply:
            return 40
        if '非常匹配' in fact_check_comment_label:
            return 60 if tag_int >= TAG_THRESHOLD_FOR_60 else 80
        if fact_check_comment_label == '匹配':
            return 50
        return 20

    @staticmethod
    def _parse_anyjob_response(response, action_name: str, candidate_name: str):
        if response is None:
            logger.warning(f"{action_name}失败，候选人={candidate_name}，原因=响应为空")
            return None

        status_code = getattr(response, 'status_code', None)
        if status_code != 200:
            body = getattr(response, 'text', '')
            logger.warning(
                f"{action_name}失败，候选人={candidate_name}，status_code={status_code}，body={body[:300]}"
            )
            return None

        try:
            payload = response.json()
        except Exception as e:
            logger.warning(f"{action_name}失败，候选人={candidate_name}，原因=响应不是有效 JSON: {e}")
            return None

        if isinstance(payload, dict):
            code = payload.get('code')
            if code not in (None, 0, '0', 1, '1', 200, '200'):
                logger.warning(
                    f"{action_name}失败，候选人={candidate_name}，code={code}，message={payload.get('message', '')}"
                )
                return None

        return payload

    @staticmethod
    def _extract_resume_id(payload, candidate_name: str):
        if not isinstance(payload, dict):
            logger.warning(f"上传简历失败，候选人={candidate_name}，原因=返回体不是对象")
            return None

        data = payload.get('data')
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data.get('id') or data.get('resume_id')

        logger.warning(f"上传简历失败，候选人={candidate_name}，原因=返回体缺少 resume_id")
        return None

    @staticmethod
    def _normalize_id(value):
        if value is None:
            return ''
        return str(value).strip()

    @staticmethod
    def _find_first_value(payload, keys):
        if isinstance(payload, dict):
            for key in keys:
                value = payload.get(key)
                if value not in (None, ''):
                    return value
            for value in payload.values():
                found = Candidate._find_first_value(value, keys)
                if found not in (None, ''):
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = Candidate._find_first_value(item, keys)
                if found not in (None, ''):
                    return found
        return None

    @staticmethod
    def _normalize_age(value):
        if value in (None, ''):
            return None
        if isinstance(value, (int, float)):
            age = int(value)
            if 1900 <= age <= datetime.now().year:
                return Candidate._calculate_age_from_birth(age)
            return age if 0 < age < 100 else None

        text = str(value)
        birth_match = re.search(r'(\d{4})\D{0,3}(\d{1,2})?', text)
        if birth_match:
            return Candidate._calculate_age_from_birth(birth_match.group(1), birth_match.group(2))

        short_birth_match = re.search(r'(?<!\d)(\d{2})[年/-](\d{1,2})?', text)
        if short_birth_match:
            year = int(short_birth_match.group(1))
            current_two_digit_year = datetime.now().year % 100
            full_year = 2000 + year if year <= current_two_digit_year else 1900 + year
            return Candidate._calculate_age_from_birth(full_year, short_birth_match.group(2))

        match = re.search(r'(\d{1,2})', text)
        if not match:
            return None

        age = int(match.group(1))
        return age if 0 < age < 100 else None

    @staticmethod
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

    @staticmethod
    def _extract_age_from_resume(base_info_dict):
        age = Candidate._normalize_age(Candidate._find_first_value(base_info_dict, ('age', 'ageLabel')))
        if age:
            return age

        birth_year = Candidate._find_first_value(base_info_dict, ('birthYear', 'birthdayYear', 'bornYear'))
        birth_month = Candidate._find_first_value(base_info_dict, ('birthMonth', 'birthdayMonth', 'bornMonth'))
        age = Candidate._calculate_age_from_birth(birth_year, birth_month)
        if age:
            return age

        birth_label = Candidate._find_first_value(
            base_info_dict,
            ('birthYearMonthLabel', 'birthdayLabel', 'birthday', 'birthDate')
        )
        if birth_label:
            match = re.search(r'(\d{4})\D{0,3}(\d{1,2})?', str(birth_label))
            if match:
                return Candidate._calculate_age_from_birth(match.group(1), match.group(2))

        return None

    @staticmethod
    def _is_meaningful_salary(value):
        text = str(value or '').strip()
        if not text:
            return False
        lowered = text.lower()
        invalid_tokens = ('面议', '保密', '不详', '未填', '暂无', '不限', '未知', '无', 'none', 'null', 'nan', 'n/a')
        return not any(token in lowered for token in invalid_tokens)

    def _get_screening_salary(self, clean_resume):
        if Candidate._is_meaningful_salary(self.salary):
            return self.salary

        salary = RegexUtils.extract_salary(clean_resume)
        if salary and Candidate._is_meaningful_salary(salary[0]):
            return salary[0]

        return ''

    @staticmethod
    def _collapse_spaces(value):
        if not value:
            return ''
        normalized = unicodedata.normalize('NFKC', str(value))
        return ' '.join(normalized.split())

    @staticmethod
    def _get_name_first_char(name):
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
        # 优先使用 AnyJob 简历统一码常见格式：字段以下划线拼接
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

        # 兼容 AnyJob 库中历史数据的中英文括号差异：在已有候选基础上再叠加"括号形态"维度，
        # 同一份 keyword 同时尝试 [原文 / 全半角 / 全全角] 三种形态，提高查重命中率。
        expanded = []
        for kw in keywords:
            for variant in Candidate._bracket_variants(kw):
                if variant and variant not in expanded:
                    expanded.append(variant)
                    if len(expanded) >= Candidate.MAX_SMART_KEYWORD_CANDIDATES:
                        return expanded
        return expanded

    # 仅覆盖圆括号（） / ()。如未来发现还有其他括号形态导致漏判，
    # 可以在这里继续追加 mapping，例如 【】↔[]、〔〕↔[] 等。
    _BRACKET_TO_HALF = str.maketrans({'（': '(', '）': ')'})
    _BRACKET_TO_FULL = str.maketrans({'(': '（', ')': '）'})

    @staticmethod
    def _bracket_variants(keyword):
        """生成 keyword 的括号形态变体，用于多 key 查重兜底。

        - 不含任何圆括号时直接返回单元素列表，避免无谓的 candidate 膨胀。
        - 含括号时返回 [原文, 全半角化, 全全角化] 去重保序后的列表，
          以兼容 AnyJob 库内历史数据中 ()/（） 不一致的情况。
        """
        if not keyword:
            return []
        if not any(c in keyword for c in '()（）'):
            return [keyword]

        variants = [
            keyword,
            keyword.translate(Candidate._BRACKET_TO_HALF),
            keyword.translate(Candidate._BRACKET_TO_FULL),
        ]
        seen = []
        for v in variants:
            if v and v not in seen:
                seen.append(v)
        return seen

    @staticmethod
    def _resolve_resume_link(base_info_dict, encode_res_id=None):
        extracted_link = Candidate._extract_resume_code(base_info_dict)
        if extracted_link:
            return extracted_link
        return ''

    @staticmethod
    def _extract_resume_code(base_info_dict):
        if not isinstance(base_info_dict, dict):
            return ''

        basic_info_form = base_info_dict.get('basicInfoForm') or {}
        candidate_keys = [
            'link',
            'smart_keywords',
            'resumeCode',
            'resumeUniqueCode',
            'resUniqueCode',
            'resumeUniqueId',
        ]

        for source in (base_info_dict, basic_info_form):
            for key in candidate_keys:
                value = source.get(key)
                if value:
                    return str(value).strip()

        return ''

    def _dump_resume_code_debug_snapshot(
            self,
            reason,
            duplicate_request_payload=None,
            duplicate_response_text=None,
            duplicate_response_status=None,
            error=None
    ):
        try:
            debug_dir = ensure_dir_exists(get_save_path() / 'debug' / 'save_resume_duplicate_screening')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            candidate_name = ''.join(ch if ch.isalnum() else '_' for ch in (self.name or 'unknown'))[:50]
            debug_file = debug_dir / f'{timestamp}_{candidate_name}.json'

            payload = {
                'reason': reason,
                'candidate_name': self.name,
                'position_id': self.position_id,
                'incharge_id': self.incharge_id,
                'resume_code': self.link,
                'smart_keywords': self.smart_keywords,
                'duplicate_request_payload': duplicate_request_payload or {},
                'duplicate_response_status': duplicate_response_status,
                'duplicate_response_text': duplicate_response_text,
                'resume_detail_response_text': self.resume_detail_response_text,
                'work_exp_response_text': self.work_exp_response_text,
                'raw_resume': json.loads(self.rawResume) if self.rawResume else None,
                'error': error,
            }

            debug_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            logger.info(f'已写入简历统一码查重调试快照: {debug_file}')
        except Exception:
            logger.warning(f'写入简历统一码查重调试快照失败，候选人={self.name}')
            logger.warning(traceback.format_exc())

    @staticmethod
    def format_contact_note(phone=None, vx=None):
        note_parts = []
        if phone:
            note_parts.append(f'电话：{phone}')
        if vx:
            note_parts.append(f'微信：{vx}')
        return '；'.join(note_parts)

    def set_contact_note(self, phone=None, vx=None):
        self.note = Candidate.format_contact_note(phone, vx)
        return self.note

    def sync_screening_resume_chat_state(self, tag, chat_history):
        if not self.resume_id:
            logger.warning(f"高潜回写失败，候选人={self.name}，原因=缺少 screening_id")
            return False

        logger.info(
            f"高潜回写开始，候选人={self.name}，screening_id={self.resume_id}，tag={tag or '空'}"
        )
        response = update_screening_resume(
            self.resume_id,
            chat_tags=tag,
            chat_history=chat_history
        )
        payload = Candidate._parse_anyjob_response(response, '回写高潜聊天状态', self.name)
        if not payload:
            logger.warning(f"高潜回写失败，候选人={self.name}，screening_id={self.resume_id}")
            return False

        logger.info(f"高潜回写成功，候选人={self.name}，screening_id={self.resume_id}")
        return True

    def _get_screening_source(self):
        if self.gold_collar:
            return ENUM_CANDIDATE_CLASSIFY.LIE_PIN_GOLD.value
        return ENUM_CANDIDATE_CLASSIFY.LIE_PIN.value

    def _build_screening_comment(self, clean_resume):
        recommendation = RegexUtils.extract_recommendation(clean_resume)
        if self.is_clients:
            recommendation_text = recommendation[0] if recommendation else ''
            return f"{self.fact_check_comment_label}，{recommendation_text}"

        if self.is_duplicate:
            if self.duplicate_position_name_list:
                return f"重复：{'，'.join(self.duplicate_position_name_list)}，{self.fact_check_comment}"
            return f"重复：但是无具体岗位，{self.fact_check_comment}"

        return f"{self.fact_check_comment_label}，{'，'.join(self.fact_check_comment.split('，')[3:])}"

    def _build_screening_resume_payload(self, clean_resume, comment):
        self.set_simple_resume()
        education = extract_highest_education(self.rawResume)

        params = {
            'name': self.name,
            'liepin_keywords': self.liepin_keywords,
            'smart_keywords': self.smart_keywords,
            'current_company': self.currentCompany,
            'current_position': self.currentPosition,
            'school': education['school'],
            'major': education['major'],
            'resume_content': clean_resume,
            'ai_summary': self.simple_resume,
            'comment': comment,
            'source': self._get_screening_source(),
        }

        if self.recentActiveTime:
            params['activity_time'] = self.recentActiveTime.strftime("%Y-%m-%d")

        salary = self._get_screening_salary(clean_resume)
        location = RegexUtils.extract_location(clean_resume)
        tags = RegexUtils.extract_tags(clean_resume)
        if self.age:
            params['age'] = self.age
        if salary:
            params['salary'] = salary
        if location:
            params['location'] = location[0]
        if tags:
            params['tags'] = tags[0]

        return params

    @staticmethod
    def _parse_chat_tags(tags_text):
        if not tags_text:
            return []
        normalized = str(tags_text).replace('，', ',')
        return [item.strip() for item in normalized.split(',') if item and item.strip()]

    @staticmethod
    def _pick_tag_by_priority(tags):
        if not tags:
            return ''
        priority_map = {tag: index for index, tag in enumerate(TAG_PRIORITY)}
        sorted_tags = sorted(
            tags,
            key=lambda item: priority_map.get(item, len(TAG_PRIORITY))
        )
        return sorted_tags[0]

    @staticmethod
    def _select_single_chat_tag(rule_tag, model_tags):
        rule_candidates = [
            tag for tag in Candidate._parse_chat_tags(rule_tag)
            if tag in ALLOWED_CHAT_TAGS
        ]
        if rule_candidates:
            return Candidate._pick_tag_by_priority(rule_candidates)
        model_candidates = [
            tag for tag in Candidate._parse_chat_tags(model_tags)
            if tag in ALLOWED_CHAT_TAGS
        ]
        if model_candidates:
            return Candidate._pick_tag_by_priority(model_candidates)

        return DEFAULT_SINGLE_CHAT_TAG

    @staticmethod
    def _format_activity_time(activity_time):
        if not activity_time:
            return None
        if isinstance(activity_time, datetime):
            return activity_time.strftime('%Y-%m-%d %H:%M:%S')
        return str(activity_time)

    def sync_high_potential_by_smart_keywords(self, chat_history, phone=None, vx=None, rule_tag=None, activity_time=None):
        self.check_screening_is_duplicate_with_resume_code()
        if not self.is_duplicate_with_current_position:
            logger.info(
                f"高潜同步跳过，candidate={self.name}，position_id={self.position_id}，"
                f"duplicate_hit={self.is_duplicate}，reason={self.last_screening_duplicate_reason}，"
                f"last_keyword={self.last_screening_duplicate_keyword or 'none'}，"
                f"has_phone={'yes' if phone else 'no'}，has_vx={'yes' if vx else 'no'}"
            )
            return False

        model_tags = None
        if Candidate._parse_chat_tags(rule_tag):
            chat_tag = Candidate._select_single_chat_tag(rule_tag, None)
        else:
            model_tags = chatBot.send(f"【历史聊天记录：】{chat_history}", ENUM_MODEL_ID.GET_CHAT_TAGS)
            chat_tag = Candidate._select_single_chat_tag(None, model_tags)
        self.last_screening_chat_tag = chat_tag
        logger.info(
            f"高潜同步标签计算，candidate={self.name}，position_id={self.position_id}，"
            f"rule_tag={rule_tag or 'none'}，model_tags={model_tags or 'none'}，"
            f"selected_single_tag={chat_tag or 'none'}"
        )

        update_kwargs = {
            'chat_history': chat_history,
            # 始终覆盖为单一标签，避免历史多标签残留。
            'chat_tags': chat_tag,
        }
        formatted_activity_time = Candidate._format_activity_time(activity_time)
        if formatted_activity_time:
            update_kwargs['activity_time'] = formatted_activity_time
        logger.info(
            f"高潜同步回写请求，candidate={self.name}，position_id={self.position_id}，"
            f"screening_id={self.resume_id}，activity_time={formatted_activity_time or 'none'}，"
            f"chat_history_len={len(chat_history or '')}，chat_tags={chat_tag or 'none'}"
        )

        response = update_screening_resume(self.resume_id, **update_kwargs)
        payload = Candidate._parse_anyjob_response(response, '统一高潜回写', self.name)
        update_success = bool(payload)
        logger.info(
            f"高潜同步结果，candidate={self.name}，position_id={self.position_id}，"
            f"smart_keyword_used={self.last_screening_duplicate_keyword or 'none'}，"
            f"duplicate_hit={self.is_duplicate_with_current_position}，screening_id={self.resume_id}，"
            f"update_success={update_success}，chat_tags={chat_tag or 'none'}"
        )
        return update_success

    def sync_existing_resume_chat_state(self, chat_history, status_tags):
        if not self.resume_id:
            logger.warning(f"已有简历回写失败，候选人={self.name}，原因=缺少 resume_id")
            return False

        logger.info(
            f"已有简历回写开始，候选人={self.name}，resume_id={self.resume_id}，tag={status_tags or '空'}"
        )
        chat_response = update_chat_history(self.resume_id, chat_history)
        chat_payload = Candidate._parse_anyjob_response(chat_response, '回写已有简历聊天记录', self.name)
        if not chat_payload:
            logger.warning(f"已有简历聊天记录回写失败，候选人={self.name}，resume_id={self.resume_id}")
            return False

        tag_response = update_status_tag(self.resume_id, status_tags)
        tag_payload = Candidate._parse_anyjob_response(tag_response, '回写已有简历标签', self.name)
        if not tag_payload:
            logger.warning(f"已有简历标签回写失败，候选人={self.name}，resume_id={self.resume_id}")
            return False

        logger.info(f"已有简历回写成功，候选人={self.name}，resume_id={self.resume_id}")
        return True

    def check_is_duplicate_with_fs(self, phone, fs_cookies_path=None, fs_position_name=None):
        if not fs_cookies_path or not fs_position_name:
            return False

        if not Path(fs_cookies_path).exists():
            logger.warning(f"飞书查重 cookies 文件不存在，跳过飞书查重: {fs_cookies_path}")
            return False

        required_go_to_page_params = {
            'name': fs_position_name,
        }
        missing_go_to_page_params = FSSpider.get_missing_required_params(
            FSSpider.go_to_recommend_page,
            **required_go_to_page_params
        )
        if missing_go_to_page_params:
            logger.info(f"飞书查重跳过，岗位页缺少必填参数: {missing_go_to_page_params}")
            return False

        recommend_candidate_params = {
            'resume_name': self.name,
            'resume_phone': phone,
            'resume_school': self.schoolName,
        }
        missing_recommend_candidate_params = FSSpider.get_missing_required_params(
            FSSpider.recommend_candidate,
            **recommend_candidate_params
        )
        if missing_recommend_candidate_params:
            logger.info(f"飞书查重跳过，候选人缺少必填参数: {missing_recommend_candidate_params}")
            return False

        fs_spider = None
        try:
            with open(fs_cookies_path, 'r', encoding='utf-8') as f:
                fs_cookies = json.load(f)

            fs_spider = FSSpider(fs_cookies)
            fs_spider.login()

            if not fs_spider.go_to_recommend_page(**required_go_to_page_params):
                logger.warning(f"飞书查重未找到岗位，跳过该候选人飞书查重: {fs_position_name}")
                return False

            return fs_spider.recommend_candidate(**recommend_candidate_params)
        except Exception as e:
            logger.warning(f"飞书查重执行失败，跳过飞书查重: {e}")
            return False
        finally:
            if fs_spider:
                try:
                    fs_spider.quit()
                except Exception as e:
                    logger.warning(f"关闭飞书查重浏览器失败: {e}")


    def evaluate_before_first_chat(self) -> str:
        """开聊前筛选：查重 + 事实判断。返回 passed / skipped_duplicate / skipped_mismatch。"""
        self.check_is_clients()
        self.check_screening_is_duplicate_with_resume_code()
        if self.is_duplicate_with_current_position:
            logger.info(
                f"开聊前筛选跳过（当前岗位高潜重复），candidate={self.name}，position_id={self.position_id}，"
                f"screening_id={self.resume_id}，保留现有高潜资料"
            )
            return 'skipped_duplicate'
        self.set_fact_check()
        if self.fact_check_comment_label == '不匹配':
            return 'skipped_mismatch'
        return 'passed'

    def upload_screening_resume_to_anyJob(self, fact_check_already_done: bool = False) -> str:
        trace_id = self.diagnostic_trace_id or 'none'
        logger.info(
            f"[高潜上传] trace_id={trace_id} stage=start candidate={self.name} "
            f"position_id={self.position_id} incharge_id_present={bool(self.incharge_id)} "
            f"smart_keywords_present={bool(self.smart_keywords)} raw_resume_len={len(self.rawResume or '')}"
        )
        self.check_is_clients()

        self.check_screening_is_duplicate_with_resume_code()

        # 仅当前岗位命中 smart_keywords 重复时，才跳过新增高潜。
        if self.is_duplicate_with_current_position:
            logger.info(
                f"高潜新增跳过（当前岗位重复），trace_id={trace_id}，candidate={self.name}，position_id={self.position_id}，"
                f"screening_id={self.resume_id}，smart_keyword={self.last_screening_duplicate_keyword or 'none'}，"
                f"保留现有高潜资料"
            )
            return 'skipped_duplicate'

        if not fact_check_already_done:
            self.set_fact_check()

        # 事实判断
        if self.fact_check_comment_label == '不匹配':
            logger.info(
                f"[高潜上传] trace_id={trace_id} stage=finish result=skipped_mismatch "
                f"candidate={self.name} position_id={self.position_id}"
            )
            return 'skipped_mismatch'

        clean_resume = chatBot.send(
            self.rawResume,
            ENUM_MODEL_ID.GET_CLEAN_RESUME,
            trace_id=self.diagnostic_trace_id,
        )
        comment = self._build_screening_comment(clean_resume)
        logger.info(
            f"[高潜上传] trace_id={trace_id} stage=payload_ready candidate={self.name} "
            f"clean_resume_len={len(clean_resume or '')} comment_len={len(comment or '')}"
        )

        # 每判断一个合适上传人才，h5发帖一次
        h5_response = h5_post(
            self.position_id,
            '发现匹配人才',
            f'姓名：{"猎聘 " + self.name} 匹配原因：{comment}',
            trace_id=self.diagnostic_trace_id,
        )
        h5_summary = summarize_anyjob_response(h5_response)
        logger.info(
            f"[高潜上传] trace_id={trace_id} stage=h5_post_result candidate={self.name} "
            f"http_status={h5_summary['http_status']} code={h5_summary['code']} "
            f"message={h5_summary['message'] or 'none'}"
        )

        params = self._build_screening_resume_payload(clean_resume, comment)

        upload_response = add_screening_resume(
            position_id=self.position_id,
            incharge_id=self.incharge_id,
            status='待联系',
            coins_cost=2,
            trace_id=self.diagnostic_trace_id,
            **params
        )
        upload_summary = summarize_anyjob_response(upload_response)
        logger.info(
            f"[高潜上传] trace_id={trace_id} stage=finish result=uploaded_assumed "
            f"candidate={self.name} position_id={self.position_id} "
            f"http_status={upload_summary['http_status']} code={upload_summary['code']} "
            f"message={upload_summary['message'] or 'none'} "
            f"screening_id={upload_summary['screening_id']}"
        )
        return 'uploaded'

    def upload_chat_history_and_tags(self, chat_history):
        return self.sync_high_potential_by_smart_keywords(chat_history=chat_history)

    def sync_liepin_resume_note(self, lp_api, encode_res_id, userc_encode_id=None, phone=None, vx=None):
        self.set_contact_note(phone, vx)
        if not lp_api:
            logger.info(f"猎聘备注跳过，候选人={self.name}，原因=猎聘接口客户端未初始化")
            return "skipped_no_lp_api"
        if not encode_res_id:
            logger.info(f"猎聘备注跳过，候选人={self.name}，原因=缺少 encode_res_id")
            return "skipped_no_encode_res_id"
        if not userc_encode_id:
            logger.info(f"猎聘备注跳过，候选人={self.name}，原因=缺少 usercEncodeId")
            return "skipped_no_userc_encode_id"
        if not phone and not vx:
            logger.info(f"猎聘备注跳过，候选人={self.name}，原因=最终上传信息中无联系方式")
            return "skipped_no_contact"
        if not self.note:
            logger.info(f"猎聘备注跳过，候选人={self.name}，原因=最终上传备注内容为空")
            return "skipped_no_contact_note"

        logger.info(
            f"开始同步猎聘备注，候选人={self.name}，encode_res_id={encode_res_id}，"
            f"usercEncodeId={userc_encode_id}，phone={'有' if phone else '无'}，vx={'有' if vx else '无'}"
        )
        note_list_response = lp_api.get_resume_note_list(encode_res_id)
        if note_list_response.status_code == 200 and self.note in note_list_response.text:
            logger.info(f"猎聘备注已存在，跳过保存，候选人={self.name}，encode_res_id={encode_res_id}")
            return "duplicate"

        save_response = lp_api.save_resume_note(encode_res_id, userc_encode_id, self.note)
        try:
            payload = save_response.json()
        except Exception:
            payload = {}

        code = payload.get('code')
        flag = payload.get('flag')
        success = save_response.status_code == 200 and flag != 0 and code in (None, 0, '0', 1, '1', 200, '200')
        if success:
            logger.info(
                f"猎聘备注接口保存成功，候选人={self.name}，encode_res_id={encode_res_id}，"
                f"usercEncodeId={userc_encode_id}"
            )
            return "saved"

        logger.warning(
            f"猎聘备注接口保存失败，候选人={self.name}，encode_res_id={encode_res_id}，"
            f"usercEncodeId={userc_encode_id}，status_code={save_response.status_code}，body={save_response.text[:500]}"
        )
        return "failed"

    def _capture_current_position_screening_id(self):
        """当前岗位若已有高潜初筛记录，返回 screening_id；并重置查重状态以便继续走正式库上传。"""
        self.check_screening_is_duplicate_with_resume_code()
        if not self.is_duplicate_with_current_position or not self.resume_id:
            return None

        screening_id = self.resume_id
        logger.info(
            f"意向上传前发现当前岗位已有高潜，candidate={self.name}，position_id={self.position_id}，"
            f"screening_id={screening_id}，smart_keyword={self.last_screening_duplicate_keyword or 'none'}"
        )
        self.is_duplicate = False
        self.is_duplicate_pass = False
        self.is_duplicate_with_current_position = False
        self.resume_id = None
        return screening_id

    def _graduate_screening_after_resume_upload(self, screening_id, resume_id, chat_history, phone, vx, chat_tag=None):
        """正式简历上传成功后，回写高潜初筛记录，避免同岗位高潜与意向并存造成重复感知。"""
        if chat_tag:
            chat_tag = Candidate._select_single_chat_tag(chat_tag, None)
        else:
            model_tags = chatBot.send(f"【历史聊天记录：】{chat_history}", ENUM_MODEL_ID.GET_CHAT_TAGS)
            chat_tag = Candidate._select_single_chat_tag(None, model_tags)
        update_kwargs = {
            'chat_history': chat_history,
            'chat_tags': chat_tag,
        }
        if phone:
            update_kwargs['phone'] = phone
        if vx:
            update_kwargs['wechat'] = vx

        logger.info(
            f"高潜转正式回写开始，candidate={self.name}，position_id={self.position_id}，"
            f"screening_id={screening_id}，resume_id={resume_id}，chat_tags={chat_tag or 'none'}"
        )
        response = update_screening_resume(screening_id, **update_kwargs)
        payload = Candidate._parse_anyjob_response(response, '高潜转正式回写', self.name)
        if payload:
            logger.info(
                f"高潜转正式回写成功，candidate={self.name}，screening_id={screening_id}，resume_id={resume_id}"
            )
            return True

        logger.warning(
            f"高潜转正式回写失败，candidate={self.name}，screening_id={screening_id}，resume_id={resume_id}"
        )
        return False

    def upload_resume_to_anyJob(self, phone, vx, chat_history, recommend_id, account_name,
                                fs_cookies_path=None, fs_position_name=None, lp_api=None,
                                encode_res_id=None, userc_encode_id=None):
        self.set_incharge_id_by_recommend_id(recommend_id)

        # 清空上游高潜库（screening）查重残留状态，确保意向库上传独立查重。
        # 否则保存简历预筛阶段 sync_high_potential_by_smart_keywords 写入的
        # is_duplicate/resume_id(=screening_id) 会在 encodeResId/link 缺失时穿透，
        # 导致误判“当前岗位已存在”而只回写、不调用 add_resume。
        self.is_duplicate = False
        self.is_duplicate_pass = False
        self.is_duplicate_with_current_position = False
        self.resume_id = None
        self.duplicate_position_id_list = []
        self.duplicate_position_name_list = []

        normalized_encode_res_id = Candidate._normalize_id(encode_res_id or self.encode_res_id)
        if normalized_encode_res_id and not self.encode_res_id:
            self.encode_res_id = normalized_encode_res_id

        # 意向查重：本地台账 -> smart_keywords -> 电话/微信
        try:
            self._check_local_upload_ledger(normalized_encode_res_id)
            if not self.is_duplicate:
                self.check_is_duplicate_with_smart_keywords()
            if not self.is_duplicate and (phone or vx):
                self.check_is_duplicate_with_phone_vx(phone, vx)
        except AnyJobResponseError:
            logger.warning(
                f'AnyJob duplicate check failed after retries; skip upload, candidate={self.name}, '
                f'position_id={self.position_id}, encode_res_id={normalized_encode_res_id}'
            )
            logger.warning(traceback.format_exc())
            return False
        status_tags = chatBot.send(f'【聊天记录：】{chat_history}', ENUM_MODEL_ID.GET_TAG_BY_CHAT_HISTORY)

        if self.is_duplicate:
            if self.is_duplicate_with_current_position:
                self._record_local_upload_ledger(normalized_encode_res_id, self.resume_id)
            sync_success = self.sync_existing_resume_chat_state(chat_history, status_tags)
            try:
                note_result = self.sync_liepin_resume_note(
                    lp_api, encode_res_id, userc_encode_id, phone, vx
                )
                if note_result == 'saved':
                    logger.info(
                        f"猎聘备注同步成功，候选人={self.name}，encode_res_id={encode_res_id}"
                    )
                elif note_result == 'duplicate':
                    logger.info(
                        f"猎聘备注已存在，跳过同步，候选人={self.name}，encode_res_id={encode_res_id}"
                    )
                elif note_result not in (
                    'skipped_no_lp_api', 'skipped_no_encode_res_id', 'skipped_no_userc_encode_id',
                    'skipped_no_contact', 'skipped_no_contact_note'
                ):
                    logger.info(
                        f"猎聘备注未执行写入，候选人={self.name}，encode_res_id={encode_res_id}，result={note_result}"
                    )
            except Exception as e:
                logger.warning(
                    f"猎聘备注同步失败，候选人={self.name}，encode_res_id={encode_res_id}，error={e}"
                )
            if self.is_duplicate_with_current_position:
                logger.info(f"简历未上传，当前岗位已存在，候选人={self.name}，resume_id={self.resume_id}")
            else:
                logger.info(f"简历未上传，候选人已在库中存在，候选人={self.name}，resume_id={self.resume_id}")
            self.is_duplicate_with_current_position = False
            return sync_success

        screening_id_on_current_position = self._capture_current_position_screening_id()

        logger.info(
            f'【调试】准备上传新简历，候选人={self.name}，position_id={self.position_id}，'
            f'smart_keywords={self.smart_keywords}，phone={"有" if phone else "无"}，vx={"有" if vx else "无"}，'
            f'linked_screening_id={screening_id_on_current_position or "none"}'
        )

        self.set_fact_check()

        # 事实判断
        if self.fact_check_comment_label == '不匹配':
            check_label = '一般匹配'
        else:
            check_label = self.fact_check_comment_label

        md_resume = self.get_md_text(phone, vx)

        status = self.check_status(self.fact_check_comment_label)

        if self.is_clients:
            comment = f'{check_label}' + '，' + f"{'，'.join(self.fact_check_comment.split('，')[3:])}"
        else:
            comment = f'{self.fact_check_comment}'

        if self.check_is_duplicate_with_fs(phone, fs_cookies_path, fs_position_name):
            comment = self.prepend_comment_prefix(comment, f'飞书查重：{fs_position_name}')

        # 业务逻辑要求是20消耗，实际代码场景不可能碰的上，写一个挂着

        coins_cost = Candidate._compute_coins_cost(
            self.fact_check_comment_label,
            status_tags,
            chat_history,
        )

        if self.gold_collar:
            source = ENUM_CANDIDATE_CLASSIFY.LIE_PIN_GOLD.value
        else:
            source = ENUM_CANDIDATE_CLASSIFY.LIE_PIN.value

        try:
            note_result = self.sync_liepin_resume_note(
                lp_api, encode_res_id, userc_encode_id, phone, vx
            )
            if note_result == 'saved':
                logger.info(
                    f"猎聘备注同步成功，候选人={self.name}，encode_res_id={encode_res_id}"
                )
            elif note_result == 'duplicate':
                logger.info(
                    f"猎聘备注已存在，跳过同步，候选人={self.name}，encode_res_id={encode_res_id}"
                )
            elif note_result not in (
                'skipped_no_lp_api', 'skipped_no_encode_res_id', 'skipped_no_userc_encode_id',
                'skipped_no_contact', 'skipped_no_contact_note'
            ):
                logger.info(
                    f"猎聘备注未执行写入，候选人={self.name}，encode_res_id={encode_res_id}，result={note_result}"
                )
        except Exception as e:
            logger.warning(
                f"猎聘备注同步失败，候选人={self.name}，encode_res_id={encode_res_id}，error={e}"
            )

        add_resume_kwargs = {
            'position_id': self.position_id,
            'resume': md_resume,
            'user_id': self.incharge_id,
            'smart_keywords': self.smart_keywords,
            'status': status,
            'comment': comment,
            'recommend_by': recommend_id,
            'status_tags': status_tags,
            'chat_history': f'{chat_history} \n猎聘账号:{account_name[0]}某',
            'coins_cost': coins_cost,
            'source': source,
            'expect_salary': self.salary,
        }
        add_resume_kwargs.update(Candidate._build_resume_contact_fields(phone, vx))
        add_response = add_resume(**add_resume_kwargs)
        logger.info(
            f'【调试】add_resume 请求已发送，候选人={self.name}，position_id={self.position_id}，'
            f'smart_keywords={self.smart_keywords}，'
            f'phone={"有" if add_resume_kwargs.get("phone") else "无"}，'
            f'weixin={"有" if add_resume_kwargs.get("weixin") else "无"}'
        )

        add_payload = Candidate._parse_anyjob_response(add_response, '上传简历', self.name)
        if not add_payload:
            logger.warning(f"简历上传失败，候选人={self.name}，未打印 H5 上传成功提示")
            return False

        resume_id = Candidate._extract_resume_id(add_payload, self.name)
        if not resume_id:
            logger.warning(f"简历上传失败，候选人={self.name}，未打印 H5 上传成功提示")
            return False

        self.resume_id = resume_id
        logger.info(f"简历上传成功，候选人={self.name}，resume_id={resume_id}")
        self._record_local_upload_ledger(normalized_encode_res_id, resume_id)

        update_response = update_resume(
            resume_id=resume_id,
            other_expected_locations=self.now_region
        )
        update_payload = Candidate._parse_anyjob_response(update_response, '更新简历附加信息', self.name)
        if update_payload:
            logger.info(f"简历附加信息更新成功，候选人={self.name}，resume_id={resume_id}")
        else:
            logger.warning(f"简历已上传但附加信息更新失败，候选人={self.name}，resume_id={resume_id}")

        h5_post(self.position_id, '意向人选上传',
                f'来自{self.currentCompany}的{self.name}已上传系统中')
        logger.info(f"H5 上传成功提示已打印，候选人={self.name}，resume_id={resume_id}")

        if screening_id_on_current_position:
            self._graduate_screening_after_resume_upload(
                screening_id_on_current_position,
                resume_id,
                chat_history,
                phone,
                vx,
                self.last_screening_chat_tag,
            )

        return True

    def upload_hunter_resume_to_anyJob(self, phone, vx, chat_history, son_position_id_list, recommend_id,
                                       account_name, fs_cookies_path=None, fs_position_name=None, lp_api=None,
                                       encode_res_id=None, userc_encode_id=None):
        parent_position_id = self.position_id
        upload_success = self.upload_resume_to_anyJob(
            phone, vx, chat_history, recommend_id, account_name, fs_cookies_path, fs_position_name,
            lp_api=lp_api, encode_res_id=encode_res_id, userc_encode_id=userc_encode_id
        )
        if not upload_success:
            self.position_id = parent_position_id
            logger.warning(
                f'HM parent position upload skipped or failed, skip son positions, '
                f'candidate={self.name}, position_id={parent_position_id}'
            )
            return False

        position_data = get_ah_result_dict(get_job_data(parent_position_id))['results'][0]['name_summary']
        positon_question = position_data.split('【岗位问题】')[1].split('【二次会话】')[0]

        for son_position_id in son_position_id_list or []:
            if self.position_question_check(chat_history,positon_question):
                self.position_id = son_position_id
                self.upload_resume_to_anyJob(
                    phone, vx, chat_history, recommend_id, account_name, fs_cookies_path, fs_position_name,
                    lp_api=lp_api, encode_res_id=encode_res_id, userc_encode_id=userc_encode_id
                )

        self.position_id = parent_position_id
        return upload_success

    @classmethod
    def from_raw_resume(cls, base_info_dict, work_exp_dict, position_id, incharge_id=None, encode_res_id=None):
        """
        base_info_dict : 第一个 JSON 的 data 字段
        work_exp_dict  : 第二个 JSON 的 data 字段（数组）
        """

        name = base_info_dict.get("showName", "") or ""

        active_time_str = base_info_dict.get("activeTime")  # "2025/12/10"
        recentActiveTime = None
        if isinstance(active_time_str, str):
            try:
                dt = datetime.strptime(active_time_str, "%Y/%m/%d")
                # 转换为 13 位时间戳再恢复 datetime
                ts_13 = int(dt.timestamp() * 1000)
                recentActiveTime = datetime.fromtimestamp(ts_13 / 1000)
            except Exception:
                recentActiveTime = None


        work_list = work_exp_dict if isinstance(work_exp_dict, list) else []
        first_work = work_list[0] if len(work_list) > 0 else {}

        currentCompany = first_work.get("rwCompname", "") or ""
        currentPosition = first_work.get("rwTitle", "") or ""


        edu_list = base_info_dict.get("eduExpFormList") or []
        first_edu = edu_list[0] if len(edu_list) > 0 else {}

        schoolName = first_edu.get("redSchool", "") or ""
        major = first_edu.get("redSpecial", "") or ""


        purposes = base_info_dict.get("resExpectInfoDtos") or []
        first_purpose = purposes[0] if len(purposes) > 0 else {}

        salary = first_purpose.get("wantSalaryShow", "") or ""
        if salary:
            salary = chatBot.send(salary,ENUM_MODEL_ID.GET_CLEAN_SALARY)

        age = cls._extract_age_from_resume(base_info_dict)
        now_region = base_info_dict.get('basicInfoForm',{}).get('dqName','')

        raw_resume = {
            "base": base_info_dict,
            "workExp": work_exp_dict
        }

        raw_resume_str = json.dumps(raw_resume, ensure_ascii=False)


        normalized_encode_res_id = cls._normalize_id(encode_res_id)
        return cls(
            name=name,
            currentCompany=currentCompany,
            currentPosition=currentPosition,
            schoolName=schoolName,
            major=major,
            rawResume=raw_resume_str,
            salary=salary,
            position_id=position_id,
            incharge_id=incharge_id,
            recentActiveTime=recentActiveTime,
            now_region=now_region,
            link=cls._resolve_resume_link(base_info_dict, normalized_encode_res_id),
            encode_res_id=normalized_encode_res_id,
            age=age,
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


# Manual demo removed from repository import; use synthetic fixtures for local testing.
