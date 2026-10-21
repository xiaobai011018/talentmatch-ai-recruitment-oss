import os
import os.path
import sys, threading, webbrowser
import uvicorn
from dotenv import load_dotenv
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles
from backend.core.router import search_condition_router, conversation_router, all_auto_router,upload_router
from backend.core.utils.path_util import path_util

load_dotenv()

# 本机若开启 Clash/Surge 等代理，requests 会走 HTTP_PROXY，访问业务 API 可能被 403/reset。
# 将项目依赖的域名加入 NO_PROXY，让这些请求直连。
_API_NO_PROXY_HOSTS = (
    'rd6.zhaopin.com',
    'api-h.liepin.com',
    '127.0.0.1',
    'localhost',
)
_existing_no_proxy = os.environ.get('NO_PROXY', '')
_merged = [h.strip() for h in (_existing_no_proxy.split(',') if _existing_no_proxy else []) + list(_API_NO_PROXY_HOSTS) if h.strip()]
os.environ['NO_PROXY'] = ','.join(dict.fromkeys(_merged))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_dist_path() -> Path:
    """
    返回静态资源 dist 目录路径
    支持：
    - 开发环境
    - PyInstaller onedir 模式
    - PyInstaller onefile 模式 (使用 sys._MEIPASS)
    """
    # PyInstaller (onefile)
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "resources" / "dist"

    # PyInstaller (onedir)
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / "resources" / "dist"

    # 开发环境
    return path_util.get_dict_path()

dist_dir = get_dist_path()
index_file = os.path.join(dist_dir,"index.html")

# 先注册后端路由，确保 API 路径优先匹配，再挂载静态文件应用以处理前端请求
app.include_router(search_condition_router.router, prefix="/api/search_condition", tags=["search_condition"])

app.include_router(upload_router.router, prefix="/api/upload", tags=["upload"])
app.include_router(conversation_router.router, prefix="/api/conversation", tags=["conversation"])
app.include_router(all_auto_router.router, prefix='/api/all_auto',tags=['all_auto_data'])

app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")


@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    # 仅对非 API 路径返回前端 index.html，让前端路由工作
    if full_path.startswith("api/"):
        return {"detail": "Not Found"}
    return FileResponse(index_file)



if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Start FastAPI service")
    parser.add_argument(
        "--no-frontend",
        action="store_true",
        help="Do not open frontend browser on startup"
    )
    args = parser.parse_args()

    # 是否自动打开前端
    if not args.no_frontend:
        threading.Timer(
            2.0,
            lambda: webbrowser.open("http://localhost:11451/")
        ).start()

    reload_flag = not getattr(sys, 'frozen', False)
    if reload_flag:
        uvicorn.run("main:app", host="0.0.0.0", port=11451, reload=True)
    else:
        uvicorn.run(app, host="0.0.0.0", port=11451, reload=False)
