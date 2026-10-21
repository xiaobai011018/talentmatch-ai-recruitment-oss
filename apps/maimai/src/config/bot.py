"""
@describe:
@fileName: bot.py
@time    : 2025/10/9 11:08
@author  : duke
"""
from enum import Enum

API_MODELS = 'https://model.example.invalid/api/completions/quora.php'


class ENUM_MODEL_ID(Enum):
    SECOND_CONTACT_MSG_GEN = '__TALENTMATCH_MODEL_23__'
    AUTO_REPLY_MSG_GEN = '__TALENTMATCH_MODEL_24__'
    CANDIDATE_TAGS_GEN = '__TALENTMATCH_MODEL_29__'
    RESUME_TRANSLATOR = '__TALENTMATCH_MODEL_30__'
    MATCH_CHECK_FIRST = '__TALENTMATCH_MODEL_05__'
    MATCH_CHECK_SECOND = '__TALENTMATCH_MODEL_06__'
    GET_TAG_BY_CHAT_HISTORY = '__TALENTMATCH_MODEL_22__'
    RESUME_BATCH_PRE_CHECK = '__TALENTMATCH_MODEL_35__'
    CLEAN_SCREENING_RESUME = '__TALENTMATCH_MODEL_08__'
    AI_SUMMARY_RESUME = '__TALENTMATCH_MODEL_19__'
    GET_CLEAN_SALARY = "__TALENTMATCH_MODEL_31__"


BOT_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded;",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}
