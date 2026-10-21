import sys, threading, webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles
from backend.router import conversation_router, all_auto_router, search_condition_router
from backend.utils.filePathUtils.FilePathUtils import get_frontend_path

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
        return Path(sys._MEIPASS) / "frontend" / "dist"

    # PyInstaller (onedir)
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / "frontend" / "dist"

    # 开发环境
    return get_frontend_path() / "dist"

dist_dir = get_dist_path()
index_file = dist_dir / "index.html"

app.include_router(search_condition_router.router, prefix="/api/search_condition", tags=["search_condition"])

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
            lambda: webbrowser.open("http://127.0.0.1:11100/")
        ).start()

    reload_flag = not getattr(sys, 'frozen', False)
    if reload_flag:
        uvicorn.run("main:app", host="0.0.0.0", port=11100, reload=True)
    else:
        uvicorn.run(app, host="0.0.0.0", port=11100, reload=False)