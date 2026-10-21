import os
from fastapi import APIRouter,UploadFile,File
from backend.core.logger.logger import get_logger
from backend.core.utils.path_util import path_util

logger = get_logger()
router = APIRouter()
@router.post("/excel")
async def upload_excel(file: UploadFile = File(...)):
    excel_path = path_util.get_excel_path()
    os.makedirs(excel_path, exist_ok=True)
    save_path = os.path.join(excel_path, file.filename)
    with open(save_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    return {"filename": file.filename, "size": len(content)}
