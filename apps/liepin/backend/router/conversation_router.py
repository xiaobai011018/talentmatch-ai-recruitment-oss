
from fastapi import APIRouter

from backend.logger.logger import get_logger
from backend.model.reply_model import reply_model
from backend.model.save_resume_data import save_resume_data
from backend.service.conversation_service import conversation_service

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
    service.start_save_resume(data)
    return {'messages': 'ok'}
