"""
@describe:
@fileName: bot.py
@time    : 2025/10/9 11:08
@author  : duke
"""
from enum import Enum

API_MODELS = 'https://model.example.invalid/api/completions/quora.php'


class ENUM_MODEL_ID(Enum):
    GET_TAG_BY_CHAT_HISTORY = '__TALENTMATCH_MODEL_22__'
    SECOND_CONTACT_MSG_GEN = '__TALENTMATCH_MODEL_23__'
    AUTO_REPLY_MSG_GEN = '__TALENTMATCH_MODEL_24__'
    GET_AI_FAST_STRATEGY = '__TALENTMATCH_MODEL_25__'
    GET_AI_RANDOM_STRATEGY = '__TALENTMATCH_MODEL_26__'
    GET_AI_DEEP_STRATEGY = '__TALENTMATCH_MODEL_27__'
    GET_CLEAN_RESUME = '__TALENTMATCH_MODEL_08__'
    GET_SIMPLE_RESUME = '__TALENTMATCH_MODEL_19__'
    GET_FIRST_CHECK = '__TALENTMATCH_MODEL_05__'
    GET_FACT_CHECK = '__TALENTMATCH_MODEL_06__'
    GET_FIRST_CONVERSATION_SIMPLE_CHECK = '__TALENTMATCH_MODEL_28__'
    GET_CHAT_TAGS = '__TALENTMATCH_MODEL_29__'
    RESUME_TRANSLATOR = '__TALENTMATCH_MODEL_30__'
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
