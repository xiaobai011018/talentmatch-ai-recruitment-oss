import os
from datetime import datetime
from pathlib import Path

from backend.core.logger.logger import get_logger
from backend.core.utils.path_util import path_util

logger = get_logger(__name__)


def maybe_dump_im_session_html(session_id: str, html: str) -> None:
    """
    调试：将 IM 页 GET 到的原始 HTML 落盘。
    须在运行 main.py / uvicorn 的进程中设置环境变量 ZHILIAN_DUMP_IM_HTML=1（或 true/yes）；
    可在项目根目录 .env 中编写 ZHILIAN_DUMP_IM_HTML=1（main 会 load_dotenv）。
    文件目录：<get_save_path()>/debug_im/im_<sessionId>_<时间戳>.html
    """
    flag = os.environ.get("ZHILIAN_DUMP_IM_HTML", "").strip().lower()
    if flag not in ("1", "true", "yes"):
        return
    out_dir = Path(path_util.get_save_path()) / "debug_im"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_sid = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(session_id))[:64]
    path = out_dir / f"im_{safe_sid}_{ts}.html"
    path.write_text(html, encoding="utf-8")
    logger.info("已写入 IM 调试 HTML：%s", path.resolve())
