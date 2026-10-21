"""
@describe:
@fileName: anyhelper.py
@time    : 2025/9/19 14:08
@author  : duke
"""
from enum import Enum

API_H5_POST = 'https://talent.example.invalid/api/add_ai_posts.php'
API_H5_AI_UPDATE_STATUS = 'https://talent.example.invalid/api/update_ai_status.php'
API_ADD_SCREENING_RESUME = 'https://talent.example.invalid/api/add_screening_resume.php'
API_GET_INCHARGE_ID_BY_POSITION_ID = 'https://talent.example.invalid/api/get_jd_by_id.php'
API_GET_SEARCH_STRATEGY = 'https://talent.example.invalid/api/get_search_strategy.php'
API_GET_POSITION_INFO = 'https://talent.example.invalid/api/get_ai_jd.php'
API_H5_AI_ADD_COUNT = 'https://talent.example.invalid/api/add_data_count.php'
API_DUPLICATE_SCREENING = 'https://talent.example.invalid/api/duplicate_screening_resume.php'
API_DUPLICATE = 'https://talent.example.invalid/api/duplicate.php'
API_UPDATE_CHAT_HISTORY = 'https://talent.example.invalid/api/update_chat_history.php'
API_UPDATE_SCREENING_RESUME = 'https://talent.example.invalid/api/update_screening_resume.php'
API_ADD_RESUME = 'https://talent.example.invalid/api/add-resume.php'
API_GET_USER_ROLE = 'https://talent.example.invalid/api/get_user_role.php'
API_UPDATE_RESUME = 'https://talent.example.invalid/api/update_resume_summary.php'
API_GET_INCHARGE_ID = 'https://talent.example.invalid/api/get_jd_by_id.php'
API_GET_HUNTER_LIST = 'https://talent.example.invalid/api/get_headhunters.php'
API_GET_POSITION_LIST = 'https://talent.example.invalid/api/get_jds.php'


class ENUM_H5_AI_STATUS(Enum):
    UNREADY = 'AI未运行'
    PREPARING = 'AI准备中'
    PAUSED = 'AI任务暂停'
    STRATEGY_GENERATING = '生成策略中'
    RESUME_READING = '读取简历中'
    RESUME_UPLOADING = '初筛上传中'
    CHATTING = '主动沟通中'
    REPLYING = '实时回复中'
    ACTIVATING = '激活人选中'
    RESUME_UPDATING_SCREENING = '推送高潜中'
    STOP = '任务已完成'
