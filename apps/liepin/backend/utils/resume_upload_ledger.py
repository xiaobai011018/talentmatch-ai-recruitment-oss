"""
意向人才库本地上传台账：按 (position_id, encode_res_id) 记录已成功上传的简历，跨任务去重。
"""
import json
import threading
from datetime import datetime
from pathlib import Path

from backend.logger.logger import get_logger
from backend.utils.filePathUtils.FilePathUtils import ensure_dir_exists, get_save_path

logger = get_logger(__name__)

_LEDGER_LOCK = threading.Lock()
_LEDGER_FILENAME = 'resume_upload_ledger.json'


def _ledger_path() -> Path:
    return ensure_dir_exists(get_save_path() / 'ledger') / _LEDGER_FILENAME


def _build_key(position_id, encode_res_id) -> str:
    normalized_position_id = str(position_id or '').strip()
    normalized_encode_res_id = str(encode_res_id or '').strip()
    if not normalized_position_id or not normalized_encode_res_id:
        return ''
    return f'{normalized_position_id}:{normalized_encode_res_id}'


def _load_records() -> dict:
    ledger_file = _ledger_path()
    if not ledger_file.exists():
        return {}
    try:
        payload = json.loads(ledger_file.read_text(encoding='utf-8'))
    except Exception as e:
        logger.warning(f'读取本地上传台账失败，将按空台账处理: {e}')
        return {}

    records = payload.get('records') if isinstance(payload, dict) else None
    return records if isinstance(records, dict) else {}


def _save_records(records: dict):
    ledger_file = _ledger_path()
    payload = {
        'records': records,
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    ledger_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def get_record(position_id, encode_res_id):
    key = _build_key(position_id, encode_res_id)
    if not key:
        return None
    with _LEDGER_LOCK:
        return _load_records().get(key)


def is_uploaded(position_id, encode_res_id) -> bool:
    return get_record(position_id, encode_res_id) is not None


def record_upload(position_id, encode_res_id, resume_id, candidate_name=None):
    key = _build_key(position_id, encode_res_id)
    if not key:
        logger.warning(
            f'本地上传台账写入跳过，原因=缺少 position_id 或 encode_res_id，'
            f'candidate={candidate_name or "未知候选人"}'
        )
        return False

    record = {
        'position_id': str(position_id).strip(),
        'encode_res_id': str(encode_res_id).strip(),
        'resume_id': resume_id,
        'candidate_name': candidate_name or '',
        'uploaded_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    with _LEDGER_LOCK:
        records = _load_records()
        records[key] = record
        _save_records(records)

    logger.info(
        f'本地上传台账已记录，candidate={candidate_name or "未知候选人"}，'
        f'position_id={position_id}，encode_res_id={encode_res_id}，resume_id={resume_id}'
    )
    return True
