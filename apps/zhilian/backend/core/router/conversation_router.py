
from fastapi import APIRouter, HTTPException

from backend.core.logger.logger import get_logger
from backend.core.model.reply_model import reply_model
from backend.core.model.save_resume_data import save_resume_data
from backend.core.service.conversation_service import conversation_service
from backend.manger import ZhilianAuthenticationError

logger = get_logger()
router = APIRouter()
service = conversation_service()

@router.post('/start_auto_reply')
async def start_auto_reply(data: reply_model):
    service.start_auto_reply(data)
    return {'messages': 'ok'}

@router.post('/stop_auto_reply')
def stop_auto_reply():
    service.stop_auto_reply()
    return {'messages': 'ok'}
@router.post('/start_second_conversation')
def start_second_conversation(data: reply_model):
    service.start_second_conversation(data)
    return {'messages': 'ok'}
@router.post('/start_save_resume')
def start_save_resume(data: save_resume_data):
    try:
        service.start_save_resume(data)
    except ZhilianAuthenticationError as exc:
        logger.error(str(exc))
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {'messages': 'ok'}
