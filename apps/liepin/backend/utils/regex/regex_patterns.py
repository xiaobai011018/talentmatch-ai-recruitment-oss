"""
----------------------------------------------------
 File Name:        regex
 Author:           hoges
 Created Date:     2025/9/22
 Last Modified:    2025/9/22
 Python Version:   
----------------------------------------------------
"""
import re

class ResumePatterns:
    RECOMMENDATION_PATTERN = re.compile(r"\*\*推荐语\*\*[:：]?\s*([\s\S]*?)(?:\n---|\n##|$)")
    SALARY_PATTERN = re.compile(r"\*\*期待薪资\*\*[:：]?\s*(.+)")
    LOCATION_PATTERN = re.compile(r"\*\*居住地\*\*[:：]?\s*(.+)")
    TAGS_PATTERN = re.compile(r"\*\*优势标签\*\*[:：]?\s*(.+)")

class clean_chat_word:
    SKIP_CHAT = [
        '我想与您电话沟通职位',
        '当前沟通',
        '上午',
        '下午',
        '晚上',
        '对方向您发送了在线简历',
        '撤回了一条消息',
        '修改',
        '复制微信号',
        '微信号：'
    ]

class position_patterns:
    GET_POSITION_ID_BY_WEB_ELEMENT_PATTERN = re.compile(r"^\D*(\d+)\D*$")
class session_img_patterns:
    GET_SESSION_IMG_PATTERN = re.compile(r'/([^/]+)\.(?:jpg|jpeg|png|webp)')
