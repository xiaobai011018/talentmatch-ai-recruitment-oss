"""
----------------------------------------------------
 File Name:        searchConditionRouter
 Author:           hoges
 Created Date:     2025/10/16
 Last Modified:    2025/10/16
 Python Version:   
----------------------------------------------------
"""
import json
import os
from pathlib import Path
from fastapi import Request
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from backend.logger.logger import get_logger
from backend.model.first_conversation_data import first_conversation_data
from backend.model.upload_screening_data import upload_screening_data
from backend.service.SearchConditionService import SearchConditionService
from backend.utils.filePathUtils.FilePathUtils import get_save_path

logger = get_logger()

router = APIRouter()
service = SearchConditionService()


@router.post("/sessionFile")
async def upload_session_file(file: UploadFile = File(...)):
    os.makedirs(get_save_path(), exist_ok=True)  # 确保目录存在
    sessionPath = os.path.join(get_save_path(), 'session')
    os.makedirs(sessionPath, exist_ok=True)
    save_path = os.path.join(sessionPath, file.filename)

    with open(save_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    return {"filename": file.filename, "size": len(content)}

@router.post("/cookiesFile")
async def upload_cookies_file(request: Request,file: UploadFile = File(None)):
    # 如果 file 是空的, 就尝试从 request.form() 里拿其他文件字段
    if file is None:
        form = await request.form()

        # 想拿名为 "zhilian-cookie-txt" 的文件对象
        zhilian_cookie_txt_file = form.get("zhilian-cookie-txt")

        if isinstance(zhilian_cookie_txt_file, UploadFile):
            file = zhilian_cookie_txt_file
        else:
            return {"error": "No file uploaded under recognized names"}


    os.makedirs(get_save_path(), exist_ok=True)  # 确保目录存在
    cookiesPath = os.path.join(get_save_path(), 'cookies')
    os.makedirs(cookiesPath, exist_ok=True)
    save_path = os.path.join(cookiesPath, file.filename)

    with open(save_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    return {"filename": file.filename, "size": len(content)}


@router.delete("/cookiesFile")
def delete_cookies_file(fileName: str = Query(..., description="cookies 文件名")):
    if not fileName or Path(fileName).name != fileName or "\\" in fileName:
        raise HTTPException(status_code=400, detail="无效的 cookies 文件名")

    cookies_dir = (get_save_path() / "cookies").resolve()
    cookies_dir.mkdir(parents=True, exist_ok=True)
    file_path = (cookies_dir / fileName).resolve()

    if file_path.parent != cookies_dir:
        raise HTTPException(status_code=400, detail="无效的 cookies 文件路径")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"文件 {fileName} 不存在")

    try:
        file_path.unlink()
    except OSError as e:
        logger.error(f"删除 cookies 文件失败: {fileName}, {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除文件 {fileName} 失败")

    return {"deleted": True, "fileName": fileName}

@router.post("/excelFile")
async def upload_excel_file(request: Request,file: UploadFile = File(None)):
    # 如果 file 是空的, 就尝试从 request.form() 里拿其他文件字段
    if file is None:
        form = await request.form()

        # 想拿名为 "zhilian-cookie-txt" 的文件对象
        zhilian_cookie_txt_file = form.get("zhilian-cookie-txt")

        if isinstance(zhilian_cookie_txt_file, UploadFile):
            file = zhilian_cookie_txt_file
        else:
            return {"error": "No file uploaded under recognized names"}


    os.makedirs(get_save_path(), exist_ok=True)  # 确保目录存在
    excelPath = os.path.join(get_save_path(), 'excel')
    os.makedirs(excelPath, exist_ok=True)
    save_path = os.path.join(excelPath, file.filename)

    with open(save_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    return {"filename": file.filename, "size": len(content)}

@router.get("/cookiesList")
def get_cookies_list():
    try:
        cookies_dir = os.path.join(get_save_path(), "cookies")
        os.makedirs(cookies_dir, exist_ok=True)
        files = os.listdir(cookies_dir)

        cookies_list = []
        for idx, filename in enumerate(files, start=1):
            file_path = os.path.join(cookies_dir, filename)
            # 使用最后修改时间作为导入时间
            import_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
            cookies_list.append({
                "id": idx,
                "fileName": filename,
                "importTime": import_time
            })

        return cookies_list
    except Exception as e:
        return {"error": str(e)}

@router.get("/getCookieByFileName")
def get_cookie_by_file_name(fileName: str = Query(..., description="cookies 文件名")):
    """
    根据文件名获取对应 cookies 内容
    """
    cookies_dir = os.path.join(get_save_path(), "cookies")
    file_path = os.path.join(cookies_dir, fileName)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件 {fileName} 不存在")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)  # 假设 cookies 文件是 JSON 格式
        return data
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"文件 {fileName} JSON 解析失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件 {fileName} 出错: {str(e)}")

# @router.post("/upload_screening")
# def upload_screening(data: upload_screening_data):
#     service.upload_screening(data)
#     return {'messages': 'ok'}

@router.post("/first_conversation")
def first_conversation(data: first_conversation_data):
    service.first_conversation(data)
    return {'messages': 'ok'}


@router.get("/searchAccounts")
def search_accounts(keyword: str = ""):
    try:
        accounts = service.search_accounts(keyword)
        return accounts
    except Exception as e:
        logger.error(f"搜索猎头账号失败: {str(e)}")
        raise HTTPException(status_code=500, detail="搜索失败")


@router.get("/searchPositions")
def search_positions(hunterId, keyword: str = ""):
    try:
        positions = service.search_positions(hunterId, keyword)
        return positions
    except Exception as e:
        logger.error(f"搜索岗位失败: {str(e)}")
        raise HTTPException(status_code=500, detail="搜索失败")


@router.get('/searchStrategies')
def search_conditions(positionId, keyword: str = ''):
    try:
        searchStrategies = service.search_conditions(positionId, keyword)
        return searchStrategies
    except Exception as e:
        logger.error(f'搜索策略失败{str(e)}')
        raise HTTPException(status_code=500, detail='搜索失败')
