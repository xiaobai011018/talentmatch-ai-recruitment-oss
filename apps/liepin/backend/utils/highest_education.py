"""高潜新增使用的教育字段；不改变 Candidate 既有的查重字段。"""

import json
import re


_INVALID_VALUES = {
    '', '-', '--', '无', '暂无', '未知', '未填写', 'not found', 'null', 'undefined',
}
# 与 TalentMatch 插件 highestEducation.js 的学历优先级一致；不猜测数字编码。
_DEGREE_RULES = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r'博士后|postdoctoral|post-doctoral',
        r'博士|ph\.?d|doctor(?:ate|al)?|dphil',
        r'硕士|研究生|master|mba|emba|m\.sc|m\.a\b',
        r'本科|学士|bachelor|b\.sc|b\.a\b',
        r'大专|专科|associate|college diploma',
        r'高中|high school',
        r'中专|技校|secondary school',
        r'其它|其他|other',
    )
]


def _clean_value(value):
    if not isinstance(value, str):
        return ''
    cleaned = re.sub(r'\s+', ' ', value).strip().strip('*').strip()
    return '' if cleaned.lower() in _INVALID_VALUES else cleaned


def _degree_rank(value):
    for index, pattern in enumerate(_DEGREE_RULES):
        if pattern.search(_clean_value(value)):
            return len(_DEGREE_RULES) - index - 1
    return -1


def extract_highest_education(raw_resume):
    """从 Helper rawResume 的猎聘教育经历中独立提取 school/major。

    优先使用可识别的最高学历，同级保持原顺序；只有一条有效经历时允许
    学历未知。两字段不跨经历拼接。缺失/异常数据返回空字段，不影响上传。
    不从工作经历、候选人查重字段或 AI 清洗文本中推断教育信息。
    """
    empty = {'school': '', 'major': ''}
    if isinstance(raw_resume, str):
        try:
            raw_resume = json.loads(raw_resume)
        except (ValueError, RecursionError):
            return empty
    if not isinstance(raw_resume, dict):
        return empty
    base = raw_resume.get('base')
    if not isinstance(base, dict):
        return empty

    records = base.get('eduExpFormList')
    if not isinstance(records, list) or not records:
        records = base.get('eduExperiences')
    if not isinstance(records, list):
        return empty

    normalized = []
    for record in records:
        if not isinstance(record, dict):
            continue
        school = _clean_value(record.get('redSchool'))
        major = _clean_value(record.get('redSpecial'))
        if school or major:
            normalized.append((
                _degree_rank(record.get('redDegreeName')),
                {'school': school, 'major': major},
            ))

    ranked = [record for record in normalized if record[0] >= 0]
    if ranked:
        return max(ranked, key=lambda record: record[0])[1]
    if len(normalized) == 1:
        return normalized[0][1]
    return empty
