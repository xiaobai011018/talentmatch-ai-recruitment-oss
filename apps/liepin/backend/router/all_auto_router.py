from fastapi import APIRouter

from backend.logger.logger import get_logger
from backend.model.all_auto_data import all_auto_data
from backend.service.all_auto_service import all_auto_service

logger = get_logger(__name__)

router = APIRouter()
service = all_auto_service()

@router.post('/')
def all_auto(data:all_auto_data):
    service.all_auto(data)
    return {'messages': 'ok'}