"""
@describe:
@fileName: bot_io.py
@time    : 2025/9/17 18:05
@author  : duke
"""
import requests
from src.config.bot import *
from src.utils.decorator import http_retry
from src.config.http import *


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def send(msg, chatbot_id):
    if isinstance(chatbot_id, ENUM_MODEL_ID):
        chatbot_id = chatbot_id.value

    return requests.post(API_MODELS, data={
        'prompt': msg,
        'chatbotID': chatbot_id,
    }, headers=BOT_HEADERS, timeout=HTTP_TIME_OUT_BOT)
