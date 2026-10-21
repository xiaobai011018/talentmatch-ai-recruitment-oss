"""
@describe:
@fileName: bot_io.py.py
@time    : 2025/9/17 18:05
@author  : duke
"""
import json
import time

import requests
from backend.config.chatBotApiConfig import *
from backend.utils.decorator.http_retry import http_retry
from backend.config.httpRetryConfig import *
from backend.utils.excel_generator.excel_generator import logger


def _compact_text(text, max_len=300):
    normalized = ' '.join((text or '').split())
    if len(normalized) <= max_len:
        return normalized
    return normalized[:max_len] + '...'


def _extract_content(response_text):
    payload = json.loads(response_text)
    return payload['choices'][0]['message']['content']


@http_retry(HTTP_RETRY_TIMES, HTTP_RETRY_GAP)
def send(msg, chatbot_id, trace_id=None):
    # 如果传入的是枚举类型，获取其值
    if hasattr(chatbot_id, 'value'):
        chatbot_id = chatbot_id.value
    trace = trace_id or 'none'
    logger.info(f'[AI调用] trace_id={trace} stage=request model_id={chatbot_id} input_len={len(msg or "")}')
    logger.info(f'模型输入摘要：{_compact_text(msg)}')

    started_at = time.perf_counter()
    try:
        res = requests.post(API_MODELS, data={
            'prompt': msg,
            'chatbotID': chatbot_id,
        }, headers=BOT_HEADERS, timeout=HTTP_TIME_OUT_BOT)

        content = _extract_content(res.content.decode('utf-8'))
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.warning(
            f'[AI调用] trace_id={trace} stage=exception model_id={chatbot_id} '
            f'elapsed_ms={elapsed_ms} exception_type={type(e).__name__} reason={e}'
        )
        raise

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info(
        f'[AI调用] trace_id={trace} stage=response model_id={chatbot_id} '
        f'http_status={res.status_code} elapsed_ms={elapsed_ms} output_len={len(content or "")}'
    )
    logger.info(f'模型输出：{_compact_text(content, max_len=500)}')

    return content


# Manual demo removed from repository import; use synthetic fixtures for local testing.
