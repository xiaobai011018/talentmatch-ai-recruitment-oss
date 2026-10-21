"""仅供新增高潜上传使用，不改变候选人身份字段或 SmartKeywords。"""
import re


_INVALID_VALUES = {'', '-', '--', '无', '暂无', '未知', '未填写', 'not found', 'null', 'undefined'}
_DEGREE_RULES = [
    (7, re.compile(r'博士后|postdoctoral|post-doctoral', re.I)),
    (6, re.compile(r'博士|ph\.?d|doctor(?:ate|al)?|dphil', re.I)),
    (5, re.compile(r'硕士|研究生|master|mba|emba|m\.sc|m\.a\b', re.I)),
    (4, re.compile(r'本科|学士|bachelor|b\.sc|b\.a\b', re.I)),
    (3, re.compile(r'大专|专科|associate|college diploma', re.I)),
    (2, re.compile(r'高中|high school', re.I)),
    (1, re.compile(r'中专|中技|技校|secondary school', re.I)),
    (0, re.compile(r'初中|其它|其他|other', re.I)),
]
# 智联编码不是学历高低顺序；MBA/EMBA 与硕士同级，与插件选择规则一致。
_ZHILIAN_DEGREE_RANKS = {'1': 6, '3': 5, '10': 5, '4': 4, '5': 3, '7': 2, '12': 1, '9': 0}


def _clean_value(value):
    if not isinstance(value, str):
        return ''
    cleaned = ' '.join(value.split()).strip('*').strip()
    return '' if cleaned.lower() in _INVALID_VALUES else cleaned


def _education_rank(record):
    for key in ('educationLabel', 'educationLevel', 'education'):
        value = record.get(key)
        text = _clean_value(value)
        for rank, pattern in _DEGREE_RULES:
            if pattern.search(text):
                return rank
        # 兼容数字及字符串编码，未知编码不猜测。
        if not isinstance(value, bool) and isinstance(value, (str, int)):
            rank = _ZHILIAN_DEGREE_RANKS.get(str(value).strip())
            if rank is not None:
                return rank
    return -1


def get_highest_education_fields(education_experiences):
    """选择最高学历的同一组学校、专业；同级保留首条，无法确定时留空。

    仅一条有效经历但无学历时保留该条；多条均无可识别学历时不猜测。
    不用低学历记录补齐最高学历记录的缺失字段，也不修改输入列表。
    """
    empty = {'school': '', 'major': ''}
    if not isinstance(education_experiences, list):
        return empty

    records = []
    for record in education_experiences:
        if not isinstance(record, dict):
            continue
        school = _clean_value(record.get('schoolName'))
        major = _clean_value(record.get('major')) or _clean_value(record.get('majorName'))
        if school or major:
            records.append((_education_rank(record), {'school': school, 'major': major}))

    ranked = [record for record in records if record[0] >= 0]
    if ranked:
        return max(ranked, key=lambda record: record[0])[1]
    return records[0][1] if len(records) == 1 else empty
