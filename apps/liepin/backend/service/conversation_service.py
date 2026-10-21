import os
import threading
import traceback
from datetime import datetime
import time
from backend.api.anyJobApi import h5_ai_update_status
from backend.config.anyJobConfig import ENUM_H5_AI_STATUS
from backend.logger.logger import get_logger
from backend.manger import Manger
from backend.model.reply_model import reply_model
from backend.model.save_resume_data import save_resume_data
from backend.utils.filePathUtils.FilePathUtils import get_save_path, resolve_cookie_path

logger = get_logger(__name__)

class conversation_service:
    def __init__(self):
        self._running = False        # 标志当前是否正在运行
        self._stop_event = threading.Event()   # 用于强制停止当前线程
        self._thread = None          # 后台线程对象

    def start_auto_reply(self, data: reply_model):

        h5_ai_update_status(data.position_id,ENUM_H5_AI_STATUS.REPLYING)

        """启动自动回复循环任务"""
        self._stop_event.clear()
        if self._running:
            logger.warning("自动回复任务已在运行中，忽略重复启动。")
            return

        self._running = True


        def run_loop():
            logger.info("自动回复任务启动")
            while self._running and not self._stop_event.is_set():
                for cookies_file_name in data.cookies_file_name_list:
                    if not self._running:
                        break
                    try:
                        cookies_file_path = str(resolve_cookie_path(cookies_file_name))
                        manger = Manger()
                        if data.reply_mode == 'all':
                            manger.auto_reply(cookies_file_path,data.reply_mode,data.hunter_mode)
                        else:
                            manger.auto_reply(cookies_file_path,data.reply_mode,data.hunter_mode,data.position_id)
                    except Exception as e:
                        logger.exception(f"自动回复出错")
                        logger.warning(traceback.format_exc())
                        time.sleep(10)

                time.sleep(600)

                logger.info('自动回复完成一轮')

            logger.info("自动回复任务已停止。")

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()
        return

    def stop_auto_reply(self):
        """停止自动回复任务"""
        if self._running:
            logger.info("收到前端停止信号，正在停止自动回复任务...")
            self._running = False
            self._stop_event.set()   # 立即让线程结束
            if self._thread:
                self._thread.join()  # 等待线程真正退出
            return
        else:
            logger.info("没有正在运行的自动回复任务。")
        return

    def start_second_conversation(self, data:reply_model):
        for cookies_file_name in data.cookies_file_name_list:
            cookies_file_path = str(resolve_cookie_path(cookies_file_name))
            manger = Manger()
            if data.reply_mode == 'all':
                manger.second_conversation(cookies_file_path,data.reply_mode)
            else:
                manger.second_conversation(cookies_file_path,data.reply_mode,data.position_id)
            logger.info(f'{cookies_file_name}二次会话发起成功')

        return

    def start_save_resume(self, data: save_resume_data):

        st_dt = datetime.strptime(data.start_time, "%Y-%m-%d %H:%M:%S")
        en_dt = datetime.strptime(data.end_time, "%Y-%m-%d %H:%M:%S")
        en_dt = en_dt.replace(hour=23, minute=59)
        for cookies_file_name in data.cookies_file_name_list:
            cookies_file_path = str(resolve_cookie_path(cookies_file_name))
            manger = Manger()
            kwargs = {}

            # reply_mode != all 时需要 position_id
            if data.reply_mode != "all":
                kwargs["position_id"] = data.position_id

            # hunter_mode 为 ture，才传 son_position_id_list
            if data.hunter_mode:
                kwargs["son_position_id_list"] = data.son_position_id_list

            if data.fs_cookies_file_name:
                kwargs["fs_cookies_path"] = str(resolve_cookie_path(data.fs_cookies_file_name))
            if data.fs_position_name:
                kwargs["fs_position_name"] = data.fs_position_name

            manger.save_resume(
                cookies_file_path,
                data.reply_mode,
                st_dt,
                en_dt,
                hunter_mode=data.hunter_mode,
                **kwargs
            )
            logger.info('保存简历成功结束')

        return
