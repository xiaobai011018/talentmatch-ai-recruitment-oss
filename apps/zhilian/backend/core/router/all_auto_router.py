from fastapi import APIRouter, HTTPException

from backend.core.logger.logger import get_logger
from backend.core.model.all_auto_data import all_auto_data
from backend.core.service.all_auto_service import all_auto_service
from backend.manger import ZhilianAuthenticationError

logger = get_logger(__name__)

router = APIRouter()
service = all_auto_service()

@router.post('/')
def all_auto(data:all_auto_data):
    try:
        service.all_auto(data)
    except ZhilianAuthenticationError as exc:
        logger.error(str(exc))
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {'messages': 'ok'}
