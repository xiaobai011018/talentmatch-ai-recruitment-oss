"""
@describe:
@fileName: lp.py
@time    : 2025/11/28 下午12:54
@author  : duke
"""
import json
import time
import hashlib
import re
import requests
import uuid
from datetime import datetime
from urllib.parse import urlencode
from tqdm import tqdm
from backend.config.lp import *
from copy import deepcopy
from backend.utils.decorator.http_retry import http_retry
from backend.config.httpRetryConfig import HTTP_TIME_OUT_LP, HTTP_RETRY_GAP, HTTP_RETRY_TIMES
from backend.logger.logger import get_logger

logger = get_logger(__name__)
LP_TRACE_APIS = {
    'search_job_list',
    'search_condition_session_list',
    'get_chat_his',
    'get_resume_detail',
    'get_work_exp',
    'get_resume_note_list',
    'save_resume_note',
}


class UserProxy:
    def __init__(self, cookies):
        self.cookies = cookies
        self.cookies_name_val_dict = {c['name']: c['value'] for c in cookies}
        self.client_id = None
        self._resume_work_experiences = {}

    def _get_headers(self):
        headers = deepcopy(TEMP_LP_HEADERS)
        headers['X-XSRF-TOKEN'] = self.cookies_name_val_dict['XSRF-TOKEN']
        headers['X-Fscp-Trace-Id'] = str(uuid.uuid4())
        headers['X-Fscp-Std-Info'] = f'{{"client_id": "{self.client_id}"}}'
        return headers

    def _get_payload(self, payload):
        payload = [f'{key} = {json.dumps(val)}' for key, val in payload.items()]
        payload = '&'.join(payload)
        payload = payload.replace('\"', '')
        payload = payload.replace(' ', '')
        return payload

    @staticmethod
    def _truncate_text(text, max_len=500):
        if text is None:
            return ''
        text = str(text)
        if len(text) <= max_len:
            return text
        return text[:max_len] + '...'

    def _ensure_client_id(self):
        if self.client_id:
            return
        self._get_client_id()
        logger.info(f'猎聘 client_id 初始化成功: {self.client_id}')

    def _log_lp_response_if_abnormal(self, api_name, url, response, payload=None, expected_top_level_key=None):
        reasons = []
        payload_preview = self._truncate_text(payload, 200) if payload is not None else ''
        body_preview = self._truncate_text(getattr(response, 'text', ''), 500)
        status_code = getattr(response, 'status_code', None)

        json_keys = None
        parsed = None
        if status_code != 200:
            reasons.append(f'status_code={status_code}')

        try:
            parsed = response.json()
            if isinstance(parsed, dict):
                json_keys = list(parsed.keys())
                if expected_top_level_key and expected_top_level_key not in parsed:
                    reasons.append(f'missing_top_level_key={expected_top_level_key}')
                if parsed.get('flag') == 0:
                    reasons.append('flag=0')
                code = parsed.get('code')
                if code not in (None, 0, '0', 1, '1', 200, '200'):
                    reasons.append(f'code={code}')
            elif expected_top_level_key:
                reasons.append('json_not_object')
        except Exception:
            reasons.append('non_json_response')

        if reasons:
            logger.warning(
                f"猎聘官方接口异常 | api={api_name} | url={url} | reasons={reasons} | "
                f"client_id={self.client_id} | payload={payload_preview} | "
                f"content_type={response.headers.get('content-type', '') if getattr(response, 'headers', None) else ''} | "
                f"json_keys={json_keys} | body={body_preview}"
            )

    def _post(self, api_name, url, payload=None, expected_top_level_key=None, timeout=HTTP_TIME_OUT_LP):
        self._ensure_client_id()
        payload_preview = self._truncate_text(payload, 200) if payload is not None else ''
        trace_enabled = api_name in LP_TRACE_APIS

        if trace_enabled:
            logger.info(
                f"猎聘接口请求开始 | api={api_name} | url={url} | client_id={self.client_id} | "
                f"timeout={timeout}s | payload={payload_preview}"
            )

        started_at = time.time()
        response = requests.post(
            url,
            headers=self._get_headers(),
            cookies=self.cookies_name_val_dict,
            data=payload,
            timeout=timeout
        )
        elapsed_ms = int((time.time() - started_at) * 1000)

        if trace_enabled:
            logger.info(
                f"猎聘接口请求结束 | api={api_name} | url={url} | status_code={response.status_code} | "
                f"elapsed_ms={elapsed_ms} | client_id={self.client_id}"
            )

        self._log_lp_response_if_abnormal(api_name, url, response, payload, expected_top_level_key)
        return response

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def _get_client_id(self):
        resp = self._get_homepage()
        match = re.search(PATTERN_LP_HOME_JS, resp.text)
        if not match:
            raise ValueError(f"猎聘首页未匹配到前端 JS 地址，body={self._truncate_text(resp.text, 500)}")
        url = 'https:' + match.group()
        resp = requests.get(url, timeout=HTTP_TIME_OUT_LP)
        match = re.search(PATTERN_LP_CLIENT_ID, resp.text)
        if not match:
            raise ValueError(f"猎聘前端 JS 未匹配到 client_id，body={self._truncate_text(resp.text, 500)}")
        self.client_id = match.group(1)
        return resp

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def _get_homepage(self):
        return requests.get(API_LP_HOME, headers=TEMP_LP_HEADERS_HOME, cookies=self.cookies_name_val_dict,
                            timeout=HTTP_TIME_OUT_LP)

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def search_resumes(self, searchParamsInputVo, curPage=0):
        searchParamsInputVo['curPage'] = curPage
        payload = {
            'searchParamsInputVo': searchParamsInputVo,
            'logForm': {"ckId": str(uuid.uuid4()), "skId": '', "fkId": '', "searchScene": "refresh"},
            'version': 'V5',
        }
        payload = [f"{key}={json.dumps(val, separators=(',', ':'))}" for key, val in payload.items()]
        payload = '&'.join(payload)

        return self._post('search_resumes', API_LP_SEARCH_RESUMES, payload)

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def create_chat(self, encodeUsercId, hjobId, imApp=1, hasSayHi=True):
        payload = {
            'imApp': imApp,
            'hasSayHi': hasSayHi,
            'encodeUsercId': encodeUsercId,
            'ck_id': str(uuid.uuid4()),
            'hjobId': hjobId
        }
        payload = self._get_payload(payload)

        return self._post('create_chat', API_LP_CREATE_CHAT, payload)

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def search_condition_session_list(self, curPage=0, imUserType=2, imApp=1, pageSize=30, **kwargs):
        # msgSourceKey, hasResume, jobKind, jobId, unRead
        payload = {
            'imUserType': imUserType,
            'imId': self.cookies_name_val_dict['imId_2'],
            'imApp': imApp,
            'curPage': curPage,
            'pageSize': pageSize,
        }

        payload.update(**kwargs)

        payload = self._get_payload(payload)

        return self._post('search_condition_session_list', API_LP_SEARCH_SESSION, payload, expected_top_level_key='data')

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def search_page_session_list(self, curPage, sortValue=None, imApp=1, imUserType=2,
                                 pageSize=30):
        payload = {
            'imUserType': imUserType,
            'imId': self.cookies_name_val_dict['imId_2'],
            'imApp': imApp,
            'curPage': curPage,
            'pageSize': pageSize,
        }

        if sortValue:
            payload['sortValue'] = sortValue

        payload = self._get_payload(payload)

        return self._post('search_page_session_list', API_LP_SEARCH_SESSION, payload, expected_top_level_key='data')

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def search_job_list(self, imApp=1, curPage=0, pageSize=100):
        payload = {
            'imApp': imApp,
            'curPage': curPage,
            'pageSize': pageSize
        }

        payload = self._get_payload(payload)

        return self._post('search_job_list', API_LP_SEARCH_JOB, payload, expected_top_level_key='data')

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def get_chat_his(self, oppositeImId, maxMessageId=None, pageSize=20, imUserType=2, imApp=1):
        payload = {
            'imId': self.cookies_name_val_dict['imId_2'],
            'imUserType': imUserType,
            'imApp': imApp,
            'oppositeImId': oppositeImId,
            'pageSize': pageSize
        }
        if maxMessageId:
            payload['maxMessageId'] = maxMessageId

        payload = self._get_payload(payload)

        return self._post('get_chat_his', API_LP_GET_CHAT_HIS, payload, expected_top_level_key='data')

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def read_msg(self, oppositeImId, imUserType=2, imApp=1):
        payload = {
            'imId': self.cookies_name_val_dict['imId_2'],
            'imUserType': imUserType,
            'imApp': imApp,
            'oppositeImId': oppositeImId
        }

        payload = self._get_payload(payload)

        return self._post('read_msg', API_LP_READ_MSG, payload)

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def send_msg(self, oppositeImId, oppositeUserId, msgType, msg, imUserType=2, imApp=1,
                 oppositeImUserType=0, chatType=0, count=1):
        payload = {
            'imId': self.cookies_name_val_dict['imId_2'],
            'imClientId': self.cookies_name_val_dict['imClientId_2'],
            'oppositeImId': oppositeImId,
            'oppositeUserId': oppositeUserId,
            'msgType': msgType,
            'msgTime': str(int(time.time() * 1000)),
            'count': count,
            'imUserType': imUserType,
            'imApp': imApp,
            'oppositeImUserType': oppositeImUserType,
            'chatType': chatType
        }
        payload = self._get_payload(payload)

        payload += '&payload={"ext":{"extType":1,"extBody":{"bizType":"1","bizData":{"quote":{}},"bsData":{}}},"bodies":[{"msg":"' + msg + '","type":"txt"}],"push":"1"}'

        return self._post('send_msg', API_LP_SEND_MSG, payload)

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def get_resume_detail(self, encodeResId):
        payload = 'paramForm={"res_id_encode":"' + encodeResId + '","pgRef":"h_pc_im_page:h_pc_im_message_whole_res_btn@' + encodeResId + ':2:","encryptResId":"","resIdEncode":"' + encodeResId + '"}'

        response = self._post('get_resume_detail', API_LP_GET_RESUME_DETAIL, payload, expected_top_level_key='data')
        if response.status_code != 200:
            return response

        try:
            body = response.json()
            resume_detail = body['data']['resumeDetailVo']
        except (ValueError, KeyError, TypeError):
            return response
        if not isinstance(resume_detail, dict):
            return response

        base_info = resume_detail.get('baseInfo') or {}
        normalized_detail = deepcopy(resume_detail)
        normalized_detail.update({
            'showName': base_info.get('name', ''),
            'activeTime': resume_detail.get('lastLoginTime'),
            'basicInfoForm': {
                **base_info,
                'resJobtitle': base_info.get('title', ''),
            },
            'eduExpFormList': resume_detail.get('eduExperiences') or [],
            'resExpectInfoDtos': resume_detail.get('jobWantInfos') or [],
            'usercIdEncode': resume_detail.get('encodeUsercId', ''),
        })
        self._resume_work_experiences[encodeResId] = resume_detail.get('workExperiences') or []

        normalized_body = deepcopy(body)
        normalized_body['data'] = normalized_detail
        response._content = json.dumps(normalized_body, ensure_ascii=False).encode('utf-8')
        response.encoding = 'utf-8'
        return response

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def get_work_exp(self, code, encodeResId):
        if encodeResId in self._resume_work_experiences:
            response = requests.Response()
            response.status_code = 200
            response.url = API_LP_GET_RESUME_WORK_EXP
            response.headers['Content-Type'] = 'application/json;charset=UTF-8'
            response.encoding = 'utf-8'
            response._content = json.dumps({
                'data': self._resume_work_experiences[encodeResId]
            }, ensure_ascii=False).encode('utf-8')
            return response

        hashlib_value = hashlib.md5(f"{encodeResId}".encode()).hexdigest()

        payload = {
            'code': code,
            'v': 1.4,
            'r': hashlib_value[0:5] + hashlib_value[0:7],
            'resIdEncode': encodeResId
        }

        payload = self._get_payload(payload)

        return self._post('get_work_exp', API_LP_GET_RESUME_WORK_EXP, payload, expected_top_level_key='data')

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def send_ask_wx_or_phone_msg(self, oppositeImId, bizType, imUserType=2, imApp=1):
        payload = {
            'oppositeImId': oppositeImId,
            'imId': self.cookies_name_val_dict['imId_2'],
            'imUserType': imUserType,
            'imApp': imApp,
            'bizType': bizType
        }

        payload = self._get_payload(payload)

        return self._post('send_ask_wx_or_phone_msg', API_LP_SEND_WX_OR_PHONE_MSG, payload)

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def get_phone_number(self, oppositeImId, encodeTel, imUserType=2, imApp=2):
        payload = {
            'encodeTel': encodeTel,
            'data': encodeTel,
            'encodePhone': encodeTel,
            'oppositeImId': oppositeImId,
            'imId': self.cookies_name_val_dict['imId_2'],
            'imUserType': imUserType,
            'imApp': imApp
        }

        payload = self._get_payload(payload)

        return self._post('get_phone_number', API_LP_GET_PHONE_NUM, payload, expected_top_level_key='data')

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def get_account_info(self):

        return self._post('get_account_info', API_LP_GET_ACCOUNT_INFO)

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def get_encode_number(self, oppositeImId, encodeNum, imUserType=2, imApp=1, bizKey=2):
        payload = {
            'oppositeImId': oppositeImId,
            'encodeNum': encodeNum,
            'imUserType': imUserType,
            'imApp': imApp,
            'bizKey': bizKey,
            'imId': self.cookies_name_val_dict['imId_2']
        }
        payload = self._get_payload(payload)

        return self._post('get_encode_number', API_LP_GET_ENCODE_PHONE_NUM, payload, expected_top_level_key='data')

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def get_resume_note_list(self, resIdEncode):
        payload = urlencode({
            'resIdEncode': resIdEncode,
            'cnResIdEncode': resIdEncode,
            'lastId': '',
            'lastShareId': ''
        })
        return self._post(
            'get_resume_note_list',
            API_LP_GET_RESUME_NOTE_LIST,
            payload,
            expected_top_level_key='data'
        )

    @http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
    def save_resume_note(self, resIdEncode, usercEncodeId, rcContext, shareFlag=1):
        payload = urlencode({
            'rcContext': rcContext,
            'shareFlag': shareFlag,
            'usercEncodeId': usercEncodeId,
            'resIdEncode': resIdEncode
        })
        return self._post(
            'save_resume_note',
            API_LP_SAVE_RESUME_NOTE,
            payload
        )


# Manual demo removed from repository import; use synthetic fixtures for local testing.
