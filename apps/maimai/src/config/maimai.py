"""
@describe:
@fileName: maimai.py
@time    : 2025/9/19 14:38
@author  : duke
"""

import re

COOKIES_EXPIRED_KEYWORD = ''

MM_VERSION_1 = '6.2.30'
MM_VERSION_2 = '5.0.2'
MM_VERSION_3 = '1.0.0'
MM_VERSION_4 = '5.2.18'

MM_OFFICIAL_IDs = set()
MM_OFFICIAL_IDs.add(62913)
MM_OFFICIAL_IDs.add(6)
MM_OFFICIAL_IDs.add(0)

# 脉脉系统/营销类会话，自动回复应忽略
MM_SKIP_MSG_NAMES = frozenset({
    '脉脉', '会员小助手', '招聘小助手', '人脉小助手', '脉脉官方服务', '社区创作者小助理',
})

# 候选人有效回复的消息类型（不限于 type=0 纯文字）
MM_CANDIDATE_REPLY_TYPES = frozenset((0, 116, 118, 123))

MM_COOKIES_DEFAULT_LEN = 11

FIRST_CONTACT_CANDIDATE_RESUME_KEYS = ['id', 'current_company', 'companies', 'large_comps', 'edu']

AUTO_REPLY_SLEEP_TIME = 300

# ----------------------------------------------------------------------------------------------------

TEMPLATE_MM_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9",
    # "Connection": "keep-alive",
    # "Content-Type": "text/plain;charset=UTF-8",
    "Host": "maimai.cn",
    "Origin": "https://maimai.cn",
    "priority": "u=1, i",
    "Referer": "https://maimai.cn/ent/v41/recruit/talents?tab=1",
    "Sec-Ch-Ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "same-origin",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "X-Csrf-Token": None,
}

# API_MM_SEARCH_BASIC = 'https://maimai.cn/api/ent/v3/search/basic'
API_MM_SEARCH_BASIC = 'https://maimai.cn/api/ent/v3/search/basic?channel=www&is_mapping_pfs=1&need_mapping_banner=1&version=1.0.0'

TEMPLATE_PAYLOAD_MM_SEARCH_BASIC = {
    "search": {"cities": "",
               "companyscope": 0,
               "degrees": "",
               "is_direct_chat": 0,
               "positions": "",
               "professions": "",
               "provinces": "",
               "query": "",
               "schools": "",
               "sortby": "0",
               "worktimes": "",
               "gender": "",
               "age": "",
               "salary": "",
               "region_scope": "0,1",
               "ht_provinces": "",
               "ht_cities": "",
               "query_relation": 0,
               "major": "",
               "only_bachelor_degree": None,
               "min_only_bachelor_degree": None,
               "max_only_bachelor_degree": None,
               "graduation_year": None,
               "dynamic_valid_days": 90,
               "has_social_relation": "",
               "company_interaction": "",
               "uploaded_resume": 0,
               "delivered_or_can_chat": 0,
               "job_hunting_status": [],
               "exclude_recently_viewed": 0,  # take care
               "recently_untouched_valid_days": 90,  # take care
               "remark": {"remarked": 0, "content": ""},
               "in_project": 0,
               "is_friend": 0,
               "paginationParam": {"page": 1, "size": 30},
               "page": 0,
               "size": 30,
               # "sid": "",
               # "sessionid": "",
               "highlight_exp": 1,
               "data_version": "4.1",
               "allcompanies": "",
               "search_query": "",
               "is_985": 0,
               "is_211": 0,
               "is_top_500": 0,
               "is_world_500": 0,
               "mapping_pfs": ""  # 行业方向
               }
}

API_MM_SEND = 'https://maimai.cn/groundhog/job/v3/direct/recruiter/send'

TEMPLATE_PARAMS_MM_SEND = {
    'auto_req': 'phone',
    'channel': 'www',
    # 'co_id': '',
    'confirmed': 1,
    'data_version': 4.1,
    'fr': 'talentDiscover_discover_list_pc',
    # 'greet_name': '',
    # 'greet_text': '',
    'is_has_name': 1,
    # 'jid': 0,
    # 'lic_id': '',
    'project_id': 0,
    'search_double_exposure': 0,
    'template_id': None,
    # 'u': '',
    # 'u2': '',
    'version': MM_VERSION_2,
}

API_MM_BATCH_SEND = 'https://maimai.cn/groundhog/job/v3/direct/recruiter/batch_send'

API_MM_ADD_JOB = 'https://maimai.cn/sdk/jobs/publish_job/add_job'

TEMPLATE_PAYLOAD_MM_ADD_JOB = {
    'ai_info': {},
    'appid': 2,
    'data_version': '4.1',
    'ejid': None,
    'infos': {
        # "position": "算法工程师",
        # "company": "",
        # "description": "",
        "is_hunter": False,
        "stags": "",
        # "province": "",
        "city": "全部",
        # "email": "",
        "custom_text": "",
        # "address": "",
        "is_public": 1,
        "is_regular": 0,
        "major_keywords": "",
        "profession": "",
        "major": "",
        "profession_new": "0101",
        "major_new": "01",
        "profession_path": "",
        # "crtime": "",
        "profession_name": "社交网络",
        # "cid": ,
        "ai_info": {},
        "industry": "00",
        # "position_type": "",
        "position_keywords": [],
        "work_time": 5,
        "degree": 0,
        # "salary_min": ,
        # "salary_max": ,
        # "salary_share": ,
        "position_key": "",
        "associated_project": {
            "from_private": "",
            "private_project_id": ""
        },
        "golden_tag": 1
    }
}

API_MM_ADD_JOB_PRE_INFO = 'https://maimai.cn/sdk/jobs/publish_job/add_pre_info'

TEMPLATE_PARAMS_MM_ADD_JOB_PRE_INFO = {
    'client': 'pc',
    'ejid': None,
    'formType': 'publish',
    'project_type': 0,
    # 'u':,
}

API_MM_JOB_LIST = 'https://maimai.cn/api/ent/job/namelist'

TEMPLATE_PARAMS_MM_JOB_LIST = {
    'channel': 'www',
    'is_new_add': 1,
    'size': 200,
    # 'uid': ,
    'version': MM_VERSION_3,
}

# API_MM_IS_ADMIN = 'https://maimai.cn/sdk/company/is_admin'

API_MM_CURRENT = 'https://maimai.cn/api/ent/user/current'

TEMPLATE_PARAMS_MM_CURRENT = {
    'channel': 'www',
    'version': MM_VERSION_3,
    # 't': 't_',
}

API_MM_CHAT = 'https://maimai.cn/chat?fr=ent&in_iframe=1&scene=talent_bank'

PATTERN_MM_CSRF = re.compile(r'\\u0022_csrf\\u0022:\\u0022(.*?)\\u0022')
PATTERN_MM_CSRF_TOKEN = re.compile(r'\\u0022_csrf_token\\u0022:\\u0022(.*?)\\u0022')

API_MM_GET_MSG_LDTIME = 'https://maimai.cn/sdk/chat/msg/v5/get_msg_by_ldtime'

TEMPLATE_PARAMS_MM_GET_MSG_LDTIME = {
    # u:,
    'channel': 'web_im',
    'version': MM_VERSION_1,
    # '_csrf':,
    # '_csrf_token':'',
    'ver_code': 'web_1',
    'push_permit': 1,
    'appid': 1,
    # 'count': 100,
    'page': 0,
    # 'only_unread':1,
}

API_MM_GET_RESUME = 'https://maimai.cn/api/ent/talent/basic'

TEMPLATE_PARAMS_MM_GET_RESUME = {
    'channel': 'www',
    'data_version': '3.1',
    'need_ai_info': 0,
    'resume_project_id': None,
    'show_tip': 0,
    # 'to_uid':,
    # 'trackable_token':,
    'version': MM_VERSION_3,
}

API_MM_CONTACT = 'https://maimai.cn/contact/comment_list/{0}?jsononly=1'

API_MM_MOBILE_REQ = 'https://maimai.cn/groundhog/job/v3/direct/mobile_req'

TEMPLATE_PARAMS_MM_MOBILE_REQ = {
    # 'mid':,
    # 'u2':,
    # 'ejid': None,
    'btn': 'bar',
    # 'u':,
    'channel': 'web_im',
    'version': MM_VERSION_1,
    # '_csrf':,
    # '_csrf_token':,
    'ver_code': 'web_1',
    'push_permit': 1,
    'appid': 1,
}

API_MM_VX_REQ = 'https://maimai.cn/sdk/chat/groundhog/job/v3/direct/wechat_req'

TEMPLATE_PARAMS_VX_MOBILE_REQ = {
    # 'mid':,
    # 'u2':,
    # 'ejid': None,
    'btn': 'bar',
    # 'u':,
    'channel': 'web_im',
    'version': MM_VERSION_1,
    # '_csrf':,
    # '_csrf_token':,
    'ver_code': 'web_1',
    'push_permit': 1,
    'appid': 1,
}

API_MM_GET_DIALOG = 'https://maimai.cn/groundhog/msg/v5/get_dlg'

TEMPLATE_PARAMS_MM_GET_DIALOG = {
    # u: ,
    'channel': 'web_im',
    'version': MM_VERSION_1,
    # '_csrf': ,
    # '_csrf_token': ,
    'ver_code': 'web_1',
    'push_permit': 1,
    'appid': 1,
    # mid: ,
    'before_did': 0,
    # 'count': 10,
}

MM_SECOND_CONTACT_LIMIT = 2

API_MM_ADD_DIALOG = 'https://maimai.cn/groundhog/msg/v5/add_dlg'

TEMPLATE_PARAMS_MM_ADD_DIALOG = {
    # u: ,
    'channel': 'web_im',
    'version': MM_VERSION_1,
    # '_csrf': ,
    # '_csrf_token': ,
    'ver_code': 'web_1',
    'push_permit': 1,
    'appid': 1,
}

API_MM_ENTER_MSG = 'https://maimai.cn/groundhog/msg/v5/enter_msg'

TEMPLATE_PARAMS_MM_ENTER_MSG = {
    # 'mid': ,
    # 'u': ,
    'channel': 'web_im',
    'version': MM_VERSION_4,
    # '_csrf': ,
    # '_csrf_token': ,
    'ver_code': 'web_1',
    'push_permit': 1,
    'appid': 1,
}

PATTERN_MM_MOBILE = re.compile(r'call\?phone_number=(\d+)')
PATTERN_MM_VX = re.compile(
    r'(?:微信号\s*[:：]?\s*|(?:微信|[Vv][Xx]|[Ww]e[Cc]hat)(?:\s*[:：]\s*|\s+))'
    r'([A-Za-z0-9][A-Za-z0-9._-]{2,31})(?![A-Za-z0-9._-])'
)

# API_MM_PULL_MSG = 'https://maimai.cn/groundhog/msg/v5/pull_msg'
#
# TEMPLATE_PARAMS_MM_PULL_MSG = {
#     # 'mid': ,
#     # 'u': ,
#     'channel': 'web_im',
#     'version': MM_VERSION_1,
#     # '_csrf': ,
#     # '_csrf_token': ,
#     'ver_code': 'web_1',
#     'push_permit': 1,
#     'appid': 1,
#     # 'mtime':,
#     'next_ctime': None,
#     'is_top': None,
# }

API_MM_CLEAR_BADGE = 'https://maimai.cn/groundhog/msg/v5/clear_badge'

TEMPLATE_PARAMS_MM_CLEAR_BADGE = {
    # 'mid': ,
    # 'u': ,
    'channel': 'web_im',
    'version': MM_VERSION_1,
    # '_csrf': ,
    # '_csrf_token': ,
    'ver_code': 'web_1',
    'push_permit': 1,
    'appid': 1,
    # 'last_did':,
}

# ----------------------------------------------------------------------------------------------------
# 反自动化签名与 v41 新接口（旧 /api/ent/v3/search/basic、/api/ent/talent/basic 已废弃，返回 10003）
API_MM_REGISTER_PUBKEY = 'https://maimai.cn/sdk/jobs/security/register_pubkey'
API_MM_ANTI_TALENT_BASIC = 'https://maimai.cn/sdk/jobs/anti_automation/talent/basic'
API_MM_ANTI_SEARCH_BASIC = 'https://maimai.cn/sdk/jobs/anti_automation/search/basic'

# talents 页 main bundle 的 hash（register_pubkey 需要）
MM_MAIN_SCRIPT_HASH = 'cf34c'
# X-ENT-TOKEN 有效期（毫秒）
MM_ENTOKEN_TTL_MS = 1800000

TEMPLATE_PARAMS_MM_ANTI_TALENT_BASIC = {
    'fr': 1,
    'need_ai_info': 1,
    'show_tip': 1,
    'data_version': '3.1',
    'version': MM_VERSION_3,
    'channel': 'www',
    # 'u' / 'uid'（招聘官）、'to_uid' / 'trackable_token'（候选人）动态注入
}

TEMPLATE_PARAMS_MM_ANTI_SEARCH_BASIC = {
    'channel': 'www',
    'version': MM_VERSION_3,
    'data_version': '4.1',
    'is_mapping_pfs': 1,
    'need_mapping_banner': 1,
    # 'u' / 'uid'（招聘官）动态注入
}
