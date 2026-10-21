import json
import random
import time
import traceback
from typing import Any, Optional
from datetime import datetime
from uuid import uuid4
from backend.api.anyJobApi import get_ah_result_dict, get_job_data, h5_ai_add_count, h5_post, h5_ai_update_status, \
    get_incharge_id_by_position_id, update_screening_resume
from backend.config.anyJobConfig import ENUM_H5_AI_STATUS
from backend.config.chatBotApiConfig import ENUM_MODEL_ID
from backend.entity.candidate import Candidate
from tqdm import tqdm

from backend.entity.searchCondition import SearchCondition
from backend.logger.logger import get_logger
import backend.api.chatBotApi as chatBot
from backend.utils.filePathUtils.FilePathUtils import get_save_path
from backend.utils.msg.history_msg import get_clean_history_msg, get_wx_and_phone, get_chat_context
from backend.utils.regex.regex_utils import RegexUtils
import backend.api.lp as lp
import pandas as pd

logger = get_logger(__name__)

_LP_CREATE_CHAT_OK_CODES = {0, '0', 1, '1', 200, '200'}


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
        self.current_job_list = []
        self._recommend_id_cache = {}
        self._account_name_cache = None

    @staticmethod
    def _safe_account_label(cookies_path):
        return str(cookies_path).replace('\\', '/').rsplit('/', 1)[-1]

    @staticmethod
    def _response_diagnostic_summary(response):
        summary = {
            'http_status': getattr(response, 'status_code', None) if response is not None else None,
            'flag': None,
            'code': None,
            'message': '',
            'data_present': False,
        }
        if response is None:
            return summary
        try:
            payload = response.json()
        except Exception:
            return summary
        if not isinstance(payload, dict):
            return summary
        summary['flag'] = payload.get('flag')
        summary['code'] = payload.get('code')
        summary['message'] = str(payload.get('msg') or payload.get('message') or '')[:200]
        summary['data_present'] = bool(payload.get('data'))
        return summary

    @staticmethod
    def _save_excel_chat_status(df, excel_path, row, status, run_id, trace_id):
        old_status = df.at[row, 'is_chat'] if 'is_chat' in df.columns else None
        logger.info(
            f"[Excel状态] run_id={run_id} trace_id={trace_id} stage=save_start "
            f"row={row} old_status={old_status} new_status={status} file={excel_path}"
        )
        df.at[row, 'is_chat'] = status
        started_at = time.perf_counter()
        try:
            df.to_excel(excel_path, index=False)
        except Exception:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                f"[Excel状态] run_id={run_id} trace_id={trace_id} stage=save_failed "
                f"row={row} new_status={status} elapsed_ms={elapsed_ms} file={excel_path}"
            )
            raise
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            f"[Excel状态] run_id={run_id} trace_id={trace_id} stage=save_success "
            f"row={row} new_status={status} elapsed_ms={elapsed_ms} file={excel_path}"
        )

    @staticmethod
    def _get_session_latest_time(session):
        latest_msg_time = session.get('latestMsgTime')
        if not latest_msg_time:
            return None
        return datetime.fromtimestamp(latest_msg_time / 1000)

    @staticmethod
    def _should_stop_session_fetch(session_list, stop_before_time):
        if not stop_before_time or not session_list:
            return False
        first_msg_time = session_list[0].get('latestMsgTime')
        last_msg_time = session_list[-1].get('latestMsgTime')
        if not first_msg_time or not last_msg_time:
            return False
        # 仅在当前页明显按最新消息倒序时启用早停，避免误伤其它排序场景。
        if first_msg_time < last_msg_time:
            return False
        return datetime.fromtimestamp(last_msg_time / 1000) <= stop_before_time

    def _get_recommend_id(self, position_id):
        cache_key = str(position_id)
        if cache_key not in self._recommend_id_cache:
            res = get_ah_result_dict(get_incharge_id_by_position_id(position_id))
            self._recommend_id_cache[cache_key] = res['results'][0]['incharge_id']
        return self._recommend_id_cache[cache_key]

    def _get_auto_reply_job_context(self, position_id, hunter_mode, job_name=None):
        try:
            job_result = get_ah_result_dict(get_job_data(position_id))
            results = job_result.get('results') if isinstance(job_result, dict) else None
            if not results:
                logger.warning(
                    f"自动回复跳过：岗位资料缺失 position_id={position_id}，job_name={job_name}，reason=results为空"
                )
                return None

            job_item = results[0] if isinstance(results[0], dict) else {}
            job_data = job_item.get('name_summary')
            if not isinstance(job_data, str) or not job_data.strip():
                logger.warning(
                    f"自动回复跳过：岗位资料缺失 position_id={position_id}，job_name={job_name}，reason=name_summary为空"
                )
                return None

            if hunter_mode:
                markers = ['【岗位信息】', '【岗位问题】', '【二次会话】']
                missing_markers = [marker for marker in markers if marker not in job_data]
                if missing_markers:
                    logger.warning(
                        f"自动回复跳过：岗位资料格式不完整 position_id={position_id}，job_name={job_name}，"
                        f"missing_markers={missing_markers}"
                    )
                    return None

                return {
                    'job_requirement': job_data.split('【岗位信息】')[1].split('【岗位问题】')[0],
                    'job_questions': job_data.split('【岗位问题】')[1].split('【二次会话】')[0],
                }

            if '【二次会话】' not in job_data:
                logger.warning(
                    f"自动回复跳过：岗位资料格式不完整 position_id={position_id}，job_name={job_name}，"
                    f"missing_markers=['【二次会话】']"
                )
                return None

            return {
                'job_requirement': job_data.split('【二次会话】')[0],
                'job_questions': None,
            }
        except Exception as e:
            logger.warning(
                f"自动回复跳过：获取岗位资料失败 position_id={position_id}，job_name={job_name}，reason={e}"
            )
            logger.warning(traceback.format_exc())
            return None

    @staticmethod
    def _fetch_job_list(lp_api, retry_times=3):
        for attempt in range(1, retry_times + 1):
            response = lp_api.search_job_list()
            try:
                payload = json.loads(response.text)
            except Exception:
                logger.info(f'获取账号下职位错误，执行第{attempt}次重试')
                logger.warning(traceback.format_exc())
                continue

            job_list = payload.get('data', {}).get('chatJob', {}).get('jobTagDetailDtos')
            if isinstance(job_list, list):
                logger.info(f'获取账号下职位成功，职位数={len(job_list)}')
                return job_list

            logger.info(f'获取账号下职位错误，执行第{attempt}次重试')
            logger.warning(f"职位列表接口返回异常结构: {json.dumps(payload, ensure_ascii=False)[:500]}")

        logger.warning('获取账号下职位失败，已达到最大重试次数')
        return []

    def _get_account_name(self, lp_api):
        if self._account_name_cache is None:
            self._account_name_cache = json.loads(lp_api.get_account_info().text)['data']['userName']
        return self._account_name_cache

    def _build_save_resume_session_context(self, lp_api, session, position_id, encode_res_id):
        chat_context = get_chat_context(self.current_cookies, session['oppositeImId'], lp_api=lp_api)
        chat_history = '\n'.join(chat_context['clean_msg'])

        response = lp_api.get_resume_detail(encode_res_id)
        resume_detail_response_text = response.text
        resume_detail = json.loads(resume_detail_response_text)['data']

        response = lp_api.get_work_exp(
            resume_detail.get('basicInfoForm', {}).get('resJobtitle'),
            encode_res_id
        )
        work_exp_response_text = response.text
        resume_work_exp = json.loads(work_exp_response_text).get('data', {})

        recommend_id = self._get_recommend_id(position_id)
        candidate = Candidate.from_raw_resume(
            resume_detail,
            resume_work_exp,
            position_id,
            recommend_id,
            encode_res_id=encode_res_id,
        )
        candidate.resume_detail_response_text = resume_detail_response_text
        candidate.work_exp_response_text = work_exp_response_text

        if resume_detail.get('goldUser', False):
            candidate.gold_collar = True

        session_latest_time = self._get_session_latest_time(session)
        candidate.sync_high_potential_by_smart_keywords(
            chat_history=chat_history,
            phone=chat_context['clean_phone'],
            vx=chat_context['clean_wx'],
            rule_tag=chat_context['conversation_status'],
            activity_time=session_latest_time,
        )

        if not (chat_context['clean_phone'] or chat_context['clean_wx']):
            logger.info(f"{session['name']}没有获得电话或者微信，被跳过")
            return None

        return {
            'session': session,
            'candidate': candidate,
            'recommend_id': recommend_id,
            'chat_history': chat_history,
            'clean_msg': chat_context['clean_msg'],
            'clean_bot_msg': chat_context['clean_bot_msg'],
            'clean_candidate_msg': chat_context['clean_candidate_msg'],
            'clean_phone': chat_context['clean_phone'],
            'clean_wx': chat_context['clean_wx'],
            'encode_res_id': encode_res_id,
            'userc_encode_id': resume_detail.get('usercIdEncode') or resume_detail.get('usercEncodeId'),
        }

    def _collect_save_resume_session_contexts(self, lp_api, session_list, position_id, start_time, end_time):
        session_contexts = []
        session_list.reverse()
        total_sessions = len(session_list)
        logger.info(f"保存简历预筛开始，position_id={position_id}，session_count={total_sessions}")

        for index, session in enumerate(session_list, start=1):
            encode_res_id = self._get_session_encode_res_id(session, '保存简历预筛')
            if not encode_res_id:
                continue

            if index == 1 or index % 10 == 0 or index == total_sessions:
                logger.info(
                    f"保存简历预筛进度，position_id={position_id}，current={index}/{total_sessions}，"
                    f"name={session.get('name', '未知候选人')}"
                )

            if session.get('unReadCnt') != 0:
                logger.info(f"{session['name']}有未读消息，被跳过")
                continue

            latest_msg_time = self._get_session_latest_time(session)
            if latest_msg_time and latest_msg_time <= start_time:
                logger.info(f"获取的对话:{session['name']}最后聊天时间小于开始范围,被跳过")
                continue
            if latest_msg_time and latest_msg_time >= end_time:
                logger.info(f"获取的对话:{session['name']}最后聊天时间大于结束范围,结束程序")
                break

            try:
                session_context = self._build_save_resume_session_context(lp_api, session, position_id, encode_res_id)
            except Exception:
                logger.warning(
                    f"保存简历预筛失败，position_id={position_id}，name={session.get('name', '未知候选人')}，"
                    f"encode_res_id={encode_res_id}"
                )
                logger.warning(traceback.format_exc())
                continue
            if session_context:
                session_contexts.append(session_context)

        logger.info(
            f"保存简历预筛结束，position_id={position_id}，passed_count={len(session_contexts)}，"
            f"total_count={total_sessions}"
        )
        return session_contexts

    @staticmethod
    def _get_session_encode_res_id(session, scene: str):
        encode_res_id = session.get('encodeResId')
        if encode_res_id:
            return encode_res_id

        session_name = session.get('name', '未知候选人')
        opposite_im_id = session.get('oppositeImId', '未知会话')
        logger.info(
            f"{scene}跳过会话：缺少 encodeResId，候选人={session_name}，oppositeImId={opposite_im_id}"
        )
        return None

    @staticmethod
    def _fetch_all_session_list(lp_api, stop_before_time=None, **kwargs):
        all_sessions = []
        cur_page = 0
        page_size = 30
        max_pages = 2000
        previous_page_signature = None
        seen_session_ids = set()

        while True:
            response = lp_api.search_condition_session_list(curPage=cur_page, pageSize=page_size, **kwargs)
            session_list = json.loads(response.text).get('data', {}).get('list') or []
            if not session_list:
                break

            current_page_signature = tuple(
                str(session.get('oppositeImId') or session.get('encodeResId') or '')
                for session in session_list
            )
            if current_page_signature and current_page_signature == previous_page_signature:
                logger.warning(
                    f"会话分页结果重复，提前结束拉取，cur_page={cur_page}，page_size={page_size}"
                )
                break

            page_new_count = 0
            for session in session_list:
                session_id = str(session.get('oppositeImId') or session.get('encodeResId') or '')
                if session_id and session_id in seen_session_ids:
                    continue
                if session_id:
                    seen_session_ids.add(session_id)
                all_sessions.append(session)
                page_new_count += 1

            if cur_page == 0 or cur_page % 10 == 0:
                logger.info(
                    f"会话列表拉取进度，cur_page={cur_page}，page_size={page_size}，"
                    f"current_page_count={len(session_list)}，new_page_count={page_new_count}，total_sessions={len(all_sessions)}"
                )

            if page_new_count == 0:
                logger.warning(
                    f"会话分页未拉到新数据，提前结束拉取，cur_page={cur_page}，page_size={page_size}"
                )
                break

            if Manger._should_stop_session_fetch(session_list, stop_before_time):
                logger.info(
                    f"保存简历会话分页提前结束：当前页已早于开始范围，cur_page={cur_page}，"
                    f"last_latestMsgTime={session_list[-1].get('latestMsgTime')}"
                )
                break
            if len(session_list) < page_size:
                break
            if cur_page >= max_pages:
                logger.warning(
                    f"会话分页达到安全上限，提前结束拉取，cur_page={cur_page}，page_size={page_size}"
                )
                break

            previous_page_signature = current_page_signature
            cur_page += 1

        return all_sessions

    def set_cookies(self, cookies_path):
        with open(cookies_path, 'r') as f:
            cookies = json.load(f)

        self.current_cookies = cookies

    def set_job_list(self):
        lp_api = lp.UserProxy(self.current_cookies)
        job_list = self._fetch_job_list(lp_api)
        self.current_job_list += job_list

    def check_and_set_job(self, position_id):
        lp_api = lp.UserProxy(self.current_cookies)
        self.current_job_list += self._fetch_job_list(lp_api)

        if not self.current_job_list:
            logger.info('账号下没有可用职位，跳过岗位匹配')
            return False

        for job in self.current_job_list:
            if str(position_id) in job['jobName']:
                self.current_position["position_name"] = job['jobName']
                self.current_job_id = job['jobId']
                self.current_job_kind = job['jobKind']
                self.current_position["position_id"] = position_id
                return True

        if not self.current_position:
            logger.info('账号下没有这个岗位')
            return False

        return False

    def upload_screening_resume(self, cookies_path, search_condition, position_id, incharge_id):
        self.__init__()
        self.set_cookies(cookies_path)
        self.set_job_list()
        lp_api = lp.UserProxy(self.current_cookies)

        job_id = None

        for job in self.current_job_list:
            try:
                if position_id == RegexUtils.get_position_id(job['jobName']):
                    job_id = job['jobId']
            except Exception as e:
                continue

        if not job_id:
            logger.info(f"账号下没有这个职位,被跳过")
            return

        resume_list = []

        page = 0
        pbar = tqdm(desc='分页搜索简历', unit='page')

        while True:
            res = lp_api.search_resumes(search_condition.to_dict(), curPage=page)
            res_list = json.loads(res.text).get('data', {}).get('resList')
            if not res_list:
                logger.info('简历遍历到头')
                break
            resume_list += res_list
            page += 1
            pbar.update(1)

        res = get_job_data(position_id)
        data = get_ah_result_dict(res)
        pname = data['result'][0]['position_name']

        execl_filepath = str(
            get_save_path() / 'candidate' / f'{pname}_{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.xlsx')

        for resume in tqdm(resume_list):
            response = lp_api.get_resume_detail(resume['simpleResumeForm']['resIdEncode'])

            resume_detail = json.loads(response.text)['data']

            response = lp_api.get_work_exp(resume_detail.get('basicInfoForm', {}).get('resJobtitle'),
                                           resume['simpleResumeForm']['resIdEncode'])

            resume_work_exp = json.loads(response.text).get('data', {})

            candidate = Candidate.from_raw_resume(resume_detail, resume_work_exp, position_id, incharge_id)

            if resume_detail.get('goldUser', False):
                candidate.gold_collar = True

            candidate.upload_screening_resume_to_anyJob()

            candidate.to_excel_row(execl_filepath)

    @staticmethod
    def _new_first_conversation_stats():
        return {
            'target_hit': 0,
            'precheck_passed': 0,
            'precheck_skipped_mismatch': 0,
            'precheck_skipped_duplicate': 0,
            'create_chat_attempted': 0,
            'create_chat_ok': 0,
            'create_chat_fail': 0,
            'reported_conversations': 0,
            'uploaded': 0,
            'upload_skipped': 0,
            'reported_reviews': 0,
        }

    @staticmethod
    def _parse_create_chat_response(response) -> tuple[bool, str, Any, bool]:
        """返回 (是否成功, 原因, code, 是否额度用尽)。"""
        try:
            parsed = response.json()
        except Exception as e:
            return False, f'json_parse_error:{e}', None, False

        code = parsed.get('code')
        flag = parsed.get('flag')
        msg = parsed.get('msg') or parsed.get('message') or ''

        if str(code) == '5000':
            return False, 'quota_exhausted', code, True

        if code in _LP_CREATE_CHAT_OK_CODES or flag in (1, '1'):
            return True, 'ok', code, False

        if flag in (0, '0'):
            return False, f'flag=0 msg={msg}', code, False

        if code is not None and code not in _LP_CREATE_CHAT_OK_CODES:
            return False, f'code={code} msg={msg}', code, False

        if response.status_code == 200:
            return True, 'http_200_assumed_ok', code, False

        return False, f'http_{response.status_code} msg={msg}', code, False

    def _log_first_conversation_summary(self, stats: dict, position_id, limit_cont: int, reason: str):
        logger.info(
            f'[初次会话] 结束汇总 reason={reason} position_id={position_id} limit={limit_cont} '
            f'命中模型={stats["target_hit"]} 开聊前通过={stats["precheck_passed"]} '
            f'开聊前跳过不匹配={stats["precheck_skipped_mismatch"]} '
            f'开聊前跳过重复={stats["precheck_skipped_duplicate"]} '
            f'尝试开聊={stats["create_chat_attempted"]} 开聊成功={stats["create_chat_ok"]} '
            f'开聊失败={stats["create_chat_fail"]} 上报会话数={stats["reported_conversations"]} '
            f'高潜上传={stats["uploaded"]} 高潜跳过={stats["upload_skipped"]} '
            f'上报审核数={stats["reported_reviews"]} 本地成功开聊计数={self.first_conversation_count}'
        )

    def _fetch_candidate_for_first_conversation(self, lp_api, res_id_encode: str, position_id: int) -> Optional[Candidate]:
        response = lp_api.get_resume_detail(res_id_encode)
        resume_detail = json.loads(response.text).get('data')
        if not resume_detail:
            logger.warning(f'[初次会话] 拉取简历详情为空 resId={res_id_encode}')
            return None
        response = lp_api.get_work_exp(
            resume_detail.get('basicInfoForm', {}).get('resJobtitle'),
            res_id_encode,
        )
        resume_work_exp = json.loads(response.text).get('data', {})
        incharge_id = get_ah_result_dict(get_incharge_id_by_position_id(position_id))['results'][0]['incharge_id']
        candidate = Candidate.from_raw_resume(resume_detail, resume_work_exp, position_id, incharge_id)
        if resume_detail.get('goldUser', False):
            candidate.gold_collar = True
        return candidate

    def first_conversation(self, cookies_path, search_condition, limit_cont, position_id):
        self.__init__()
        stats = self._new_first_conversation_stats()
        logger.info(
            f'[初次会话] 开始 position_id={position_id} limit={limit_cont} cookies={cookies_path}'
        )
        self.set_cookies(cookies_path)
        self.set_job_list()
        lp_api = lp.UserProxy(self.current_cookies)

        job_id = None

        for job in self.current_job_list:
            try:
                if str(position_id) in job['jobName']:
                    job_id = job['jobId']
            except Exception as e:
                continue

        if not job_id:
            logger.info(f'[初次会话] 账号下没有这个职位,被跳过 position_id={position_id}')
            self._log_first_conversation_summary(stats, position_id, limit_cont, 'no_job_id')
            return

        page = 0
        pbar = tqdm(desc='分页搜索简历', unit='page')

        job_requirement = get_ah_result_dict(get_job_data(position_id))['results'][0][
            'summary']
        job_simple_check = job_requirement.split('初筛要求：')[1].split('深匹要求：')[0]

        try:
            while True:
                lp_api.get_account_info()
                response = lp_api.search_resumes(search_condition.to_dict(), curPage=page)
                res_list = json.loads(response.text).get('data', {}).get('resList')
                if not res_list:
                    logger.info('[初次会话] 简历遍历到头')
                    break
                bot_clean_list_str = chatBot.send(
                    f"【岗位要求：】{job_simple_check}【简历列表：】{response.text}",
                    ENUM_MODEL_ID.GET_FIRST_CONVERSATION_SIMPLE_CHECK,
                )
                if bot_clean_list_str == '[]':
                    logger.info(f'[初次会话] page={page} 模型未返回候选人')
                    page += 1
                    pbar.update(1)
                    continue
                target_list = [item.strip() for item in bot_clean_list_str.split(',') if item.strip()]
                logger.info(
                    f'[初次会话] page={page} 本页简历数={len(res_list)} 模型返回target数={len(target_list)}'
                )
                for res in res_list:
                    if self.first_conversation_count >= limit_cont:
                        logger.info(
                            f'[初次会话] 已达成功开聊上限 {self.first_conversation_count}/{limit_cont}，退出'
                        )
                        self._log_first_conversation_summary(stats, position_id, limit_cont, 'limit_reached')
                        return

                    res_id = res['simpleResumeForm']['resIdEncode']
                    if res_id not in target_list:
                        continue

                    stats['target_hit'] += 1
                    candidate = self._fetch_candidate_for_first_conversation(lp_api, res_id, position_id)
                    if not candidate:
                        continue

                    precheck_status = candidate.evaluate_before_first_chat()
                    logger.info(
                        f'[初次会话] 开聊前筛选 name={candidate.name} resId={res_id} 结果={precheck_status}'
                    )
                    if precheck_status == 'skipped_mismatch':
                        stats['precheck_skipped_mismatch'] += 1
                        continue
                    if precheck_status == 'skipped_duplicate':
                        stats['precheck_skipped_duplicate'] += 1
                        continue

                    stats['precheck_passed'] += 1
                    time.sleep(random.uniform(2, 4))
                    lp_api.search_job_list()
                    time.sleep(random.uniform(5, 7))

                    stats['create_chat_attempted'] += 1
                    userc_id = res['usercIdEncode']
                    logger.info(
                        f'[初次会话] create_chat 请求 name={candidate.name} usercIdEncode={userc_id} jobId={job_id}'
                    )
                    chat_response = lp_api.create_chat(userc_id, job_id)
                    time.sleep(random.uniform(5, 6))
                    ok, reason, code, pay_exhausted = self._parse_create_chat_response(chat_response)
                    body_preview = (chat_response.text or '')[:300]
                    logger.info(
                        f'[初次会话] create_chat 结果 name={candidate.name} success={ok} code={code} '
                        f'reason={reason} body={body_preview}'
                    )

                    if pay_exhausted:
                        stats['create_chat_fail'] += 1
                        self.pay_flag = True
                        logger.info('[初次会话] create_chat 额度用尽 code=5000，停止本账号')
                        self._log_first_conversation_summary(stats, position_id, limit_cont, 'quota_exhausted')
                        return

                    if not ok:
                        stats['create_chat_fail'] += 1
                        logger.info(
                            f'[初次会话] 上报 count_conversations 跳过(开聊失败) name={candidate.name}'
                        )
                        continue

                    stats['create_chat_ok'] += 1
                    h5_ai_add_count(position_id, count_conversations=1)
                    stats['reported_conversations'] += 1
                    self.first_conversation_count += 1
                    logger.info(
                        f'[初次会话] 上报 count_conversations +1 name={candidate.name} '
                        f'累计成功开聊={self.first_conversation_count}/{limit_cont}'
                    )

                    upload_status = candidate.upload_screening_resume_to_anyJob(fact_check_already_done=True)
                    logger.info(
                        f'[初次会话] 高潜上传 name={candidate.name} 结果={upload_status}'
                    )
                    if upload_status == 'uploaded':
                        h5_ai_add_count(position_id, count_resume_reviews=1)
                        stats['reported_reviews'] += 1
                        stats['uploaded'] += 1
                        logger.info(
                            f'[初次会话] 上报 count_resume_reviews +1 name={candidate.name}'
                        )
                    else:
                        stats['upload_skipped'] += 1
                        logger.info(
                            f'[初次会话] 上报 count_resume_reviews 跳过({upload_status}) name={candidate.name}'
                        )

                page += 1
                pbar.update(1)
        finally:
            pbar.close()

        self._log_first_conversation_summary(stats, position_id, limit_cont, 'search_finished')

    def _process_excel_resume_candidate(
            self,
            lp_api,
            resume,
            job_id,
            position_id,
            row,
            candidate_index,
            run_id,
            account_label,
    ):
        trace_id = f"{run_id}-r{row}-c{candidate_index + 1}"
        res_id = resume['simpleResumeForm']['resIdEncode']
        res_id_suffix = str(res_id)[-8:]
        logger.info(
            f"[Excel初次会话] run_id={run_id} trace_id={trace_id} stage=candidate_start "
            f"row={row} candidate_index={candidate_index + 1} position_id={position_id} "
            f"account={account_label} res_id_suffix={res_id_suffix}"
        )

        time.sleep(random.uniform(13, 19))
        chat_started_at = time.perf_counter()
        chat_response = lp_api.create_chat(resume['usercIdEncode'], job_id)
        chat_elapsed_ms = int((time.perf_counter() - chat_started_at) * 1000)
        chat_summary = self._response_diagnostic_summary(chat_response)
        logger.info(
            f"[Excel初次会话] run_id={run_id} trace_id={trace_id} stage=create_chat_result "
            f"row={row} elapsed_ms={chat_elapsed_ms} http_status={chat_summary['http_status']} "
            f"flag={chat_summary['flag']} code={chat_summary['code']} "
            f"message={chat_summary['message'] or 'none'}"
        )
        if chat_response.json().get('code', None) == "5000":
            logger.info(
                f"[Excel初次会话] run_id={run_id} trace_id={trace_id} stage=quota_exhausted "
                f"row={row} account={account_label}"
            )
            return True

        h5_ai_add_count(position_id, trace_id=trace_id, count_conversations=1)

        detail_started_at = time.perf_counter()
        detail_response = lp_api.get_resume_detail(res_id)
        detail_elapsed_ms = int((time.perf_counter() - detail_started_at) * 1000)
        detail_summary = self._response_diagnostic_summary(detail_response)
        logger.info(
            f"[Excel初次会话] run_id={run_id} trace_id={trace_id} stage=resume_detail_result "
            f"row={row} elapsed_ms={detail_elapsed_ms} http_status={detail_summary['http_status']} "
            f"flag={detail_summary['flag']} code={detail_summary['code']} "
            f"data_present={detail_summary['data_present']} "
            f"message={detail_summary['message'] or 'none'}"
        )
        resume_detail = json.loads(detail_response.text)['data']

        work_exp_started_at = time.perf_counter()
        work_exp_response = lp_api.get_work_exp(
            resume_detail.get('basicInfoForm', {}).get('resJobtitle'),
            res_id,
        )
        work_exp_elapsed_ms = int((time.perf_counter() - work_exp_started_at) * 1000)
        work_exp_summary = self._response_diagnostic_summary(work_exp_response)
        logger.info(
            f"[Excel初次会话] run_id={run_id} trace_id={trace_id} stage=work_exp_result "
            f"row={row} elapsed_ms={work_exp_elapsed_ms} http_status={work_exp_summary['http_status']} "
            f"flag={work_exp_summary['flag']} code={work_exp_summary['code']} "
            f"data_present={work_exp_summary['data_present']} "
            f"message={work_exp_summary['message'] or 'none'}"
        )
        resume_work_exp = json.loads(work_exp_response.text).get('data', {})

        incharge_response = get_incharge_id_by_position_id(position_id, trace_id=trace_id)
        incharge_payload = get_ah_result_dict(incharge_response)
        incharge_results = incharge_payload.get('results') if isinstance(incharge_payload, dict) else None
        logger.info(
            f"[Excel初次会话] run_id={run_id} trace_id={trace_id} stage=incharge_result "
            f"row={row} position_id={position_id} "
            f"results_count={len(incharge_results) if isinstance(incharge_results, list) else 0}"
        )
        incharge_id = incharge_payload['results'][0]['incharge_id']

        candidate = Candidate.from_raw_resume(resume_detail, resume_work_exp, position_id, incharge_id)
        candidate.diagnostic_trace_id = trace_id
        upload_status = candidate.upload_screening_resume_to_anyJob()
        logger.info(
            f"[Excel初次会话] run_id={run_id} trace_id={trace_id} stage=screening_result "
            f"row={row} candidate={candidate.name} result={upload_status}"
        )
        h5_ai_add_count(position_id, trace_id=trace_id, count_resume_reviews=1)
        logger.info(
            f"[Excel初次会话] run_id={run_id} trace_id={trace_id} stage=candidate_finish "
            f"row={row} chat_result=assumed_success screening_result={upload_status}"
        )
        return False

    def first_conversation_by_excel(self, cookies_path, excel_path, current_row, run_id=None):
        run_id = run_id or uuid4().hex[:12]
        account_label = self._safe_account_label(cookies_path)
        self.__init__()
        self.set_cookies(cookies_path)
        self.set_job_list()
        lp_api = lp.UserProxy(self.current_cookies)

        df = pd.read_excel(excel_path, sheet_name=0)
        logger.info(
            f"[Excel初次会话] run_id={run_id} stage=start account={account_label} "
            f"file={excel_path} current_row={current_row} total_rows={df.shape[0]}"
        )

        excel_dict = df.to_dict()

        for row in tqdm(range(current_row, df.shape[0])):
            row_trace_id = f"{run_id}-r{row}"
            logger.info(
                f"[Excel初次会话] run_id={run_id} trace_id={row_trace_id} stage=row_start "
                f"row={row} account={account_label} name={excel_dict.get('name', {}).get(row, 'unknown')}"
            )

            # 无意义操作，用于防止人机验证
            lp_api.get_account_info()

            if not excel_dict.get('apply_position', {}):
                logger.info(f'表格{excel_path}格式有误,没有 apply_position')
                return row, False

            if str(excel_dict.get('is_chat', {}).get(row)) == '1.0':
                logger.info(f"第{row}行{excel_dict['name'][row]}已聊过，被跳过")
                continue
            if str(excel_dict.get('is_chat', {}).get(row)) == '2.0':
                logger.info(f"第{row}行{excel_dict['name'][row]}聊天状态异常，被跳过")
                continue
            try:
                position_id = RegexUtils.get_position_id(excel_dict['apply_position'][row])
            except Exception as e:
                logger.info(
                    f"[Excel初次会话] run_id={run_id} trace_id={row_trace_id} "
                    f"stage=position_parse_failed row={row} reason={e}"
                )
                self._save_excel_chat_status(df, excel_path, row, 2, run_id, row_trace_id)
                continue

            job_id = None

            for job in self.current_job_list:
                try:
                    if position_id == RegexUtils.get_position_id(job['jobName']):
                        job_id = job['jobId']
                except Exception as e:
                    continue

            if not job_id:
                logger.info(
                    f"[Excel初次会话] run_id={run_id} trace_id={row_trace_id} stage=job_not_found "
                    f"row={row} position_id={position_id} account={account_label}"
                )
                self._save_excel_chat_status(df, excel_path, row, 2, run_id, row_trace_id)
                continue

            sc = SearchCondition()

            sc.keyword = excel_dict['keywords'][row]

            search_started_at = time.perf_counter()
            res = lp_api.search_resumes(sc.to_dict(), curPage=0)
            search_elapsed_ms = int((time.perf_counter() - search_started_at) * 1000)

            resume_list = json.loads(res.text).get('data', {}).get('resList')
            search_summary = self._response_diagnostic_summary(res)
            logger.info(
                f"[Excel初次会话] run_id={run_id} trace_id={row_trace_id} stage=search_result "
                f"row={row} position_id={position_id} elapsed_ms={search_elapsed_ms} "
                f"http_status={search_summary['http_status']} flag={search_summary['flag']} "
                f"code={search_summary['code']} message={search_summary['message'] or 'none'} "
                f"resume_count={len(resume_list) if isinstance(resume_list, list) else 0}"
            )

            if not resume_list:
                logger.info(
                    f"[Excel初次会话] run_id={run_id} trace_id={row_trace_id} "
                    f"stage=no_resume row={row} position_id={position_id}"
                )
                self._save_excel_chat_status(df, excel_path, row, 2, run_id, row_trace_id)
                continue
            # 无意义操作，用于防止人机验证
            lp_api.search_job_list()

            # 无论搜到多少个，只发前两个
            if len(resume_list) >= 2:
                for candidate_index in range(2):
                    try:
                        pay_exhausted = self._process_excel_resume_candidate(
                            lp_api=lp_api,
                            resume=resume_list[candidate_index],
                            job_id=job_id,
                            position_id=position_id,
                            row=row,
                            candidate_index=candidate_index,
                            run_id=run_id,
                            account_label=account_label,
                        )
                    except Exception:
                        logger.exception(
                            f"[Excel初次会话] run_id={run_id} "
                            f"trace_id={row_trace_id}-c{candidate_index + 1} "
                            f"stage=candidate_failed row={row} position_id={position_id}"
                        )
                        raise
                    if pay_exhausted:
                        return row, True
                self._save_excel_chat_status(df, excel_path, row, 1, run_id, row_trace_id)

            else:
                try:
                    pay_exhausted = self._process_excel_resume_candidate(
                        lp_api=lp_api,
                        resume=resume_list[0],
                        job_id=job_id,
                        position_id=position_id,
                        row=row,
                        candidate_index=0,
                        run_id=run_id,
                        account_label=account_label,
                    )
                except Exception:
                    logger.exception(
                        f"[Excel初次会话] run_id={run_id} trace_id={row_trace_id}-c1 "
                        f"stage=candidate_failed row={row} position_id={position_id}"
                    )
                    raise
                if pay_exhausted:
                    return row, True
                self._save_excel_chat_status(df, excel_path, row, 1, run_id, row_trace_id)

        logger.info(
            f"[Excel初次会话] run_id={run_id} stage=finish account={account_label} "
            f"file={excel_path} final_row={df.shape[0]}"
        )
        return df.shape[0], True

    def auto_reply(self, cookies_path, reply_mode, hunter_mode, position_id=None):
        self.__init__()
        self.set_cookies(cookies_path)
        self.set_job_list()
        lp_api = lp.UserProxy(self.current_cookies)

        if reply_mode == 'all':
            # 全岗位回复获取正确需要对话的对话框
            # 遍历所有岗位
            # 获取每个岗位下面的未读队列
            logger.info('获取职位队列，处理对应会话表')
            for job in tqdm(self.current_job_list):
                try:
                    position_id = RegexUtils.get_position_id(job['jobName'])
                    response = lp_api.search_condition_session_list(unRead=True, jobId=job['jobId'],
                                                                    jobKind=job['jobKind'])
                    session_list = json.loads(response.text)['data']['list']
                    if not session_list:
                        continue
                    self.current_session_list = session_list
                except Exception as e:
                    logger.info(f"当前账号下职位：{job['jobName']}没有职位数字,被跳过")
                    logger.info(traceback.format_exc())
                    continue
                self.auto_reply_session_list(lp_api, hunter_mode, position_id, job.get('jobName'))

        else:
            # 单独岗位回复获取正确需要对话的对话框
            # 检查账号下是否有这个岗位
            # 查询时携带这个岗位查询

            # 检查账号下是否有这个岗位
            if not self.check_and_set_job(position_id):
                return

            response = lp_api.search_condition_session_list(unRead=True, jobId=self.current_job_id,
                                                            jobKind=self.current_job_kind)
            session_list = json.loads(response.text)["data"]['list']
            if not session_list:
                return
            self.current_session_list += session_list

            self.auto_reply_session_list(lp_api, hunter_mode, position_id)

    def auto_reply_session_list(self, lp_api: lp.UserProxy, hunter_mode, position_id: str | Any, job_name=None):
        # 处理每个会话
        logger.info('处理对话')

        job_context = self._get_auto_reply_job_context(position_id, hunter_mode, job_name)
        if not job_context:
            return
        h5_ai_update_status(position_id, ENUM_H5_AI_STATUS.REPLYING)

        for session in tqdm(self.current_session_list):
            encode_res_id = self._get_session_encode_res_id(session, '自动回复')
            if not encode_res_id:
                continue

            chat_context = get_chat_context(self.current_cookies, session['oppositeImId'], lp_api=lp_api)
            clean_msg = chat_context['clean_msg']
            clean_bot_msg = chat_context['clean_bot_msg']
            clean_candidate_msg = chat_context['clean_candidate_msg']
            clean_phone = chat_context['clean_phone']
            clean_vx = chat_context['clean_wx']
            conversation_status = chat_context['conversation_status']

            if clean_candidate_msg:
                h5_post(position_id, '意向人选回复',
                        f"<{session['name']}>发送消息：{clean_candidate_msg[-1].split('：')[1]}")

                h5_ai_add_count(position_id, count_replies=1)

            response = lp_api.get_resume_detail(encode_res_id)

            resume_detail = json.loads(response.text)['data']

            response = lp_api.get_work_exp(resume_detail.get('basicInfoForm', {}).get('resJobtitle'),
                                           encode_res_id)

            resume_work_exp = json.loads(response.text).get('data', {})

            raw_resume_str = json.dumps(resume_detail, indent=4, ensure_ascii=False) + '\n' + json.dumps(
                resume_work_exp, indent=4, ensure_ascii=False)

            msg = '\n'.join(clean_msg)

            if clean_phone or clean_vx:
                msg += "\n【系统信息】：已获得候选人联系方式（电话或微信）"

            if hunter_mode:
                job_requirement = job_context['job_requirement']
                job_questions = job_context['job_questions']
                reply = chatBot.send(f"【岗位信息：】{job_requirement}【岗位问题：】{job_questions}【聊天记录：】{msg}",
                                     ENUM_MODEL_ID.GET_HUNTER_AUTO_REPLY)
            else:
                job_requirement = job_context['job_requirement']
                reply = chatBot.send(f"【职位要求：】{job_requirement}【候选人信息：】{raw_resume_str}【聊天记录：】{msg}",
                                     ENUM_MODEL_ID.AUTO_REPLY_MSG_GEN)

            response = lp_api.send_msg(session['oppositeImId'], session['oppositeUserId'], 'txt', reply)

            response = lp_api.send_ask_wx_or_phone_msg(session['oppositeImId'], 1)
            response = lp_api.send_ask_wx_or_phone_msg(session['oppositeImId'], 2)

            response = lp_api.read_msg(session['oppositeImId'])

            recommend_id = self._get_recommend_id(position_id)
            candidate = Candidate.from_raw_resume(resume_detail, resume_work_exp, position_id, recommend_id)
            candidate.sync_high_potential_by_smart_keywords(
                chat_history='\n'.join(clean_msg),
                phone=clean_phone,
                vx=clean_vx,
                rule_tag=conversation_status,
                activity_time=self._get_session_latest_time(session),
            )

    def second_conversation(self, cookies_path, reply_mode, position_id=None):
        self.__init__()
        self.set_cookies(cookies_path)
        self.set_job_list()
        lp_api = lp.UserProxy(self.current_cookies)
        if reply_mode == 'all':
            logger.info('获取职位队列，处理对应会话表')
            for job in tqdm(self.current_job_list):
                self.current_session_list = []
                try:
                    position_id = RegexUtils.get_position_id(job['jobName'])
                    response = lp_api.search_condition_session_list(jobId=job['jobId'], jobKind=job['jobKind'])
                    session_list = json.loads(response.text)['data']['list']
                    if not session_list:
                        continue
                    for session in session_list:
                        if not session['unReadCnt'] == 0:
                            logger.info(f"{session['name']}有未读消息，被跳过")
                            continue

                        (clean_msg, clean_bot_msg, clean_candidate_msg) = get_clean_history_msg(self.current_cookies,
                                                                                                session['oppositeImId'],
                                                                                                lp_api=lp_api)
                        if clean_bot_msg and len(clean_bot_msg) >= 3:
                            logger.info(f"候选人{session['name']}已被聊三句话，跳过二次激活")
                            continue

                        if clean_candidate_msg:
                            logger.info(f"候选人{session['name']}已回复，跳过二次激活")
                            continue

                        (clean_phone, clean_wx) = get_wx_and_phone(self.current_cookies,
                                                                   session['oppositeImId'],
                                                                   lp_api=lp_api)
                        if clean_phone or clean_wx:
                            logger.info(f"候选人{session['name']}已获得电话微信，跳过二次激活")
                            continue

                        self.current_session_list.append(session)
                except Exception as e:
                    logger.info(f"当前账号下职位：{job['jobName']}没有职位数字,被跳过")
                    logger.info(traceback.format_exc())
                    continue

                self.second_conversation_session_list(lp_api, position_id)
        else:
            if not self.check_and_set_job(position_id):
                return

            response = lp_api.search_condition_session_list(jobId=self.current_job_id, jobKind=self.current_job_kind)
            session_list = json.loads(response.text)["data"]['list']
            if not session_list:
                return
            for session in session_list:
                if not session['unReadCnt'] == 0:
                    logger.info(f"{session['name']}有未读消息，被跳过")
                    continue

                (clean_msg, clean_bot_msg, clean_candidate_msg) = get_clean_history_msg(self.current_cookies,
                                                                                        session['oppositeImId'],
                                                                                        lp_api=lp_api)

                if clean_bot_msg and len(clean_bot_msg) >= 3:
                    logger.info(f"候选人{session['name']}已被聊三句话，跳过二次激活")
                    continue

                if clean_candidate_msg:
                    logger.info(f"候选人{session['name']}已回复，跳过二次激活")

                (clean_phone, clean_wx) = get_wx_and_phone(self.current_cookies,
                                                           session['oppositeImId'],
                                                           lp_api=lp_api)
                if clean_phone or clean_wx:
                    logger.info(f"候选人{session['name']}已获得电话微信，跳过二次激活")
                    continue

                self.current_session_list.append(session)

            self.second_conversation_session_list(lp_api, position_id)

    def second_conversation_session_list(self, lp_api: lp.UserProxy, position_id):
        logger.info('处理会话中')

        h5_ai_update_status(position_id, ENUM_H5_AI_STATUS.ACTIVATING)

        for session in tqdm(self.current_session_list):
            encode_res_id = self._get_session_encode_res_id(session, '二次会话')
            if not encode_res_id:
                continue

            resp = get_job_data(position_id)
            data = get_ah_result_dict(resp)['results'][0]
            summary = data['summary']
            name_summary = data['name_summary']
            job_requirement = f"深匹要求：{summary.split('深匹要求：')[1]} {name_summary.split('【公司信息】')[0]}"

            (clean_msg, _, _) = get_clean_history_msg(self.current_cookies, session['oppositeImId'], lp_api=lp_api)
            his_msg = '\n'.join(clean_msg)

            response = lp_api.get_resume_detail(encode_res_id)

            if response.status_code != 200:
                logger.warning(f"简历详情获取失败，跳过该会话 | encode_res_id={encode_res_id} | status_code={response.status_code} | oppositeImId={session.get('oppositeImId')}")
                continue

            try:
                resume_detail = json.loads(response.text)['data']
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"简历详情JSON解析失败，跳过该会话 | encode_res_id={encode_res_id} | error={str(e)} | response_text={response.text[:200]}")
                continue

            response = lp_api.get_work_exp(resume_detail.get('basicInfoForm', {}).get('resJobtitle'),
                                           encode_res_id)

            try:
                resume_work_exp = json.loads(response.text).get('data', {})
            except json.JSONDecodeError as e:
                logger.warning(f"工作经历JSON解析失败，使用空数据 | encode_res_id={encode_res_id} | error={str(e)}")
                resume_work_exp = {}

            raw_resume_str = json.dumps(resume_detail, indent=4, ensure_ascii=False) + '\n' + json.dumps(
                resume_work_exp, indent=4, ensure_ascii=False)

            second_contact_msg = chatBot.send(
                f'【岗位信息：】{job_requirement} 【候选人信息：】{raw_resume_str}【历史聊天记录：】{his_msg}',
                ENUM_MODEL_ID.SECOND_CONTACT_MSG_GEN
            )

            response = lp_api.send_msg(session['oppositeImId'], session['oppositeUserId'], 'txt', second_contact_msg)

            response = lp_api.send_ask_wx_or_phone_msg(session['oppositeImId'], 1)
            response = lp_api.send_ask_wx_or_phone_msg(session['oppositeImId'], 2)

            response = lp_api.read_msg(session['oppositeImId'])

    def save_resume(self, cookies_path, reply_mode, start_time, end_time, hunter_mode, position_id=None,
                    son_position_id_list=None, fs_cookies_path=None, fs_position_name=None):
        self.__init__()
        self.set_cookies(cookies_path)
        self.set_job_list()
        logger.info(f"保存简历开始，reply_mode={reply_mode}，job_count={len(self.current_job_list)}")
        lp_api = lp.UserProxy(self.current_cookies)
        if reply_mode == 'all':
            logger.info('获取职位队列，处理对应会话表')
            for job in tqdm(self.current_job_list):
                self.current_session_list = []
                try:
                    position_id = RegexUtils.get_position_id(job['jobName'])
                    logger.info(f"开始处理岗位，job_name={job['jobName']}，position_id={position_id}")
                    session_list = self._fetch_all_session_list(
                        lp_api,
                        jobId=job['jobId'],
                        jobKind=job['jobKind'],
                        stop_before_time=start_time
                    )

                    if not session_list:
                        logger.info(f"岗位无会话可处理，job_name={job['jobName']}")
                        continue

                    self.current_session_list = self._collect_save_resume_session_contexts(
                        lp_api,
                        session_list,
                        position_id,
                        start_time,
                        end_time
                    )
                    logger.info(
                        f"岗位预筛完成，job_name={job['jobName']}，upload_candidate_count={len(self.current_session_list)}"
                    )

                except Exception as e:
                    logger.info(f"处理岗位会话失败，已跳过：{job['jobName']}")
                    logger.info(traceback.format_exc())
                    continue

                if hunter_mode:
                    self.save_resume_session_list(
                        lp_api,
                        position_id,
                        hunter_mode,
                        son_position_id_list,
                        fs_cookies_path,
                        fs_position_name
                    )
                else:
                    self.save_resume_session_list(
                        lp_api,
                        position_id,
                        hunter_mode,
                        fs_cookies_path=fs_cookies_path,
                        fs_position_name=fs_position_name
                    )
        else:
            try:
                if not self.check_and_set_job(position_id):
                    return

                self.current_session_list = []
                session_list = self._fetch_all_session_list(
                    lp_api,
                    jobId=self.current_job_id,
                    jobKind=self.current_job_kind,
                    stop_before_time=start_time
                )

                if not session_list:
                    return

                self.current_session_list = self._collect_save_resume_session_contexts(
                    lp_api,
                    session_list,
                    position_id,
                    start_time,
                    end_time
                )
                logger.info(f"单岗位预筛完成，position_id={position_id}，upload_candidate_count={len(self.current_session_list)}")
                if hunter_mode:
                    self.save_resume_session_list(
                        lp_api,
                        position_id,
                        hunter_mode,
                        son_position_id_list,
                        fs_cookies_path,
                        fs_position_name
                    )
                else:
                    self.save_resume_session_list(
                        lp_api,
                        position_id,
                        hunter_mode,
                        fs_cookies_path=fs_cookies_path,
                        fs_position_name=fs_position_name
                    )
            except Exception:
                logger.info(f"处理单岗位会话失败，已跳过：position_id={position_id}")
                logger.info(traceback.format_exc())
                return

    def save_resume_session_list(self, lp_api, position_id, hunter_mode, son_position_id_list=None,
                                 fs_cookies_path=None, fs_position_name=None):
        logger.info(f"处理会话，position_id={position_id}，session_count={len(self.current_session_list)}")

        h5_ai_update_status(position_id, ENUM_H5_AI_STATUS.RESUME_UPDATING_SCREENING)
        account_name = self._get_account_name(lp_api)
        logger.info("猎聘备注使用接口直连模式，不再初始化备注浏览器")

        total_sessions = len(self.current_session_list)
        success_count = 0
        skipped_count = 0
        failed_count = 0
        for index, session_context in enumerate(self.current_session_list, start=1):
            session = session_context['session']
            candidate = session_context['candidate']
            recommend_id = session_context['recommend_id']
            clean_phone = session_context['clean_phone']
            clean_wx = session_context['clean_wx']
            chat_history = session_context['chat_history']
            encode_res_id = session_context.get('encode_res_id')
            userc_encode_id = session_context.get('userc_encode_id')
            logger.info(
                f"保存简历上传进度，position_id={position_id}，current={index}/{total_sessions}，"
                f"name={session.get('name', '未知候选人')}"
            )

            try:
                if hunter_mode:
                    upload_success = candidate.upload_hunter_resume_to_anyJob(
                        clean_phone,
                        clean_wx,
                        chat_history,
                        son_position_id_list,
                        recommend_id,
                        account_name,
                        fs_cookies_path,
                        fs_position_name,
                        lp_api=lp_api,
                        encode_res_id=encode_res_id,
                        userc_encode_id=userc_encode_id
                    )
                else:
                    upload_success = candidate.upload_resume_to_anyJob(
                        clean_phone,
                        clean_wx,
                        chat_history,
                        recommend_id,
                        account_name,
                        fs_cookies_path,
                        fs_position_name,
                        lp_api=lp_api,
                        encode_res_id=encode_res_id,
                        userc_encode_id=userc_encode_id
                    )

                if not upload_success:
                    skipped_count += 1
                    logger.warning(
                        f"保存简历跳过后续猎聘消息动作，position_id={position_id}，"
                        f"current={index}/{total_sessions}，name={session.get('name', '未知候选人')}，"
                        f"encode_res_id={encode_res_id or 'none'}，原因=上传或查重流程未成功"
                    )
                    continue

                lp_api.send_ask_wx_or_phone_msg(session['oppositeImId'], 1)
                lp_api.send_ask_wx_or_phone_msg(session['oppositeImId'], 2)
                lp_api.read_msg(session['oppositeImId'])
                success_count += 1
            except Exception:
                failed_count += 1
                logger.warning(
                    f"保存简历处理单个候选人失败，已跳过，position_id={position_id}，"
                    f"current={index}/{total_sessions}，name={session.get('name', '未知候选人')}，"
                    f"encode_res_id={encode_res_id or 'none'}"
                )
                logger.warning(traceback.format_exc())
                continue

        logger.info(
            f"保存简历处理完成，position_id={position_id}，session_count={total_sessions}，"
            f"success={success_count}，skipped={skipped_count}，failed={failed_count}"
        )


# Manual demo removed from repository import; use synthetic fixtures for local testing.
