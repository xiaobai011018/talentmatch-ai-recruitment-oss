"""
@describe:
@fileName: bot_io.py.py
@time    : 2025/9/17 18:05
@author  : duke
"""
import json
import time

import requests
from backend.core.config.chatBotApiConfig import *
from backend.core.utils.decorator.http_retry import http_retry
from backend.core.config.httpRetryConfig import *
from backend.core.utils.excel_generator.excel_generator import logger


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def send(msg, chatbot_id):
    logger.info(msg)
    # 如果传入的是枚举类型，获取其值
    if hasattr(chatbot_id, 'value'):
        chatbot_id = chatbot_id.value
    logger.info(f'模型编号：{chatbot_id}')

    start_time = time.time()
    response = requests.post(API_MODELS, data={
        'prompt': msg,
        'chatbotID': chatbot_id,
    }, headers=BOT_HEADERS, timeout=HTTP_TIMEOUT)
    logger.info(f'模型请求完成，模型编号：{chatbot_id}，耗时：{time.time() - start_time:.2f}s')

    content = json.loads(response.content.decode('utf-8'))['choices'][0]['message']['content']

    logger.info(f'{content}')
    return content


# Manual demo removed from repository import; use synthetic fixtures for local testing.
