"""高潜新增字段：沿用 TalentMatch 插件的最高学历、同段学校专业规则。

仅解析已有简历，不调用 AI 或网络；无法确定的字段使用空字符串。
"""
import json
import re


_INVALID_VALUES = {'', '-', '--', '无', '暂无', '未知', '未填写',
                   'not found', 'null', 'undefined'}
_DEGREE_RULES = [re.compile(pattern, re.I) for pattern in (
    r'博士后|postdoctoral|post-doctoral',
    r'博士|ph\.?d|doctor(?:ate|al)?|dphil',
    r'硕士|研究生|master|mba|emba|m\.sc|m\.a\b',
    r'本科|学士|bachelor|b\.sc|b\.a\b',
    r'大专|专科|associate|college diploma',
    r'高中|high school',
    r'中专|技校|secondary school',
    r'其它|其他|other',
)]
_SCHOOL_KEYS = ('school', 'School', 'schoolName', 'school_name', 'university',
                'University', 'college', 'highest_degree_school', 'latestSchool')
_MAJOR_KEYS = ('major', 'Major', 'major_name', 'field', 'Field', 'schoolSpecial',
               'speciality', 'highest_degree_field', 'latestMajor')
_DEGREE_KEYS = ('degree', 'Degree', 'degree_name', 'education', 'educationLevel',
                'highest_degree_extract')
_SCHOOL_LABEL = r'(?:学校|院校|大学名称|毕业院校|毕业学校|school|university|college)'
_MAJOR_LABEL = r'(?:专业|所学专业|major|field of study)'
_SCHOOL_LINE = re.compile(rf'^{_SCHOOL_LABEL}\s*[:：]\s*(.+)$', re.I)
_MAJOR_LINE = re.compile(rf'^{_MAJOR_LABEL}\s*[:：]\s*(.+)$', re.I)
_DEGREE_LINE = re.compile(r'^(?:学历|学位|degree)\s*[:：]\s*(.+)$', re.I)
_EDUCATION_START = re.compile(
    r'^(?:教育经历|教育背景|education(?:al)?(?: background| experience)?)$', re.I)
_EDUCATION_STOP = re.compile(
    r'^(?:工作经历|工作经验|项目经历|职业标签|技能|更多资料|期望偏好|个人简介|'
    r'资格证书|语言能力|推荐信息|推荐语|个人信息|基本信息|'
    r'experience|work experience|skills?|projects?)$', re.I)
_NOISE_LINE = re.compile(
    r'^(?:985|211|双一流|海外Top\d+|国内Top\d+|世界Top\d+|QS(?:世界)?Top\d+|'
    r'该段经历来自附件简历|ta有\d+个好友在此学校|无)$', re.I)
_DATE_LINE = re.compile(
    r'^(?:(?:时间|日期|dates?)\s*[:：]\s*)?'
    r'(?:\d{4}[-/.年]\d{1,2}|(?:19|20)\d{2}\s*(?:-|至|–|—))', re.I)


def _clean(value):
    # 不把嵌套对象、数组或数字编码变成学校/专业字符串。
    if not isinstance(value, str):
        return ''
    text = re.sub(r'\s+', ' ', value).strip().strip('*').strip()
    return '' if text.lower() in _INVALID_VALUES else text


def _value_from(record, keys):
    return next((value for key in keys if (value := _clean(record.get(key)))), '')


def _degree_rank(value):
    return next((7 - i for i, pattern in enumerate(_DEGREE_RULES)
                 if pattern.search(_clean(value))), -1)


def _structured_records(source):
    if isinstance(source, list):
        return source
    if not isinstance(source, dict):
        return []
    for key in ('Education', 'education', 'educations', 'edu', 'educationList'):
        if isinstance(source.get(key), list):
            return source[key]
    if isinstance(source.get('eduInfoContent'), dict):
        return [source['eduInfoContent']]
    return [source]


def _normalize_records(records):
    normalized = []
    for record in records:
        if not isinstance(record, dict):
            continue
        pair = {'school': _value_from(record, _SCHOOL_KEYS),
                'major': _value_from(record, _MAJOR_KEYS)}
        rank = _degree_rank(_value_from(record, _DEGREE_KEYS))
        if pair['school'] or pair['major'] or rank >= 0:
            normalized.append((rank, pair))
    return normalized


def _choose_highest(normalized):
    ranked = [item for item in normalized if item[0] >= 0]
    if ranked:
        # 相同学历保持源顺序，保留学历信息用于验证跨来源的同一段经历。
        return max(ranked, key=lambda item: item[0])
    if len(normalized) == 1:
        return normalized[0]
    return None


def _text_lines(text):
    # 排版空行不切断记录，Markdown 分隔线则保留为记录边界。
    return [re.sub(r'^[-#>*•]+\s*', '', line.strip()).replace('*', '').strip()
            for line in text.splitlines() if line.strip()]


def _labeled_text_records(lines):
    """完整标签格式按段组装；混合无标签文本仍交给原有解析器。"""
    records, current = [], {}
    for line in lines:
        if not line or _DATE_LINE.match(line):
            if current:
                records.append(current)
                current = {}
            continue
        if _NOISE_LINE.match(line):
            continue
        for key, pattern in (('school', _SCHOOL_LINE), ('major', _MAJOR_LINE),
                             ('degree', _DEGREE_LINE)):
            match = pattern.match(line)
            if match:
                # 新的同名字段标志下一段，不从另一段借学校或专业。
                if key in current:
                    records.append(current)
                    current = {}
                current[key] = _clean(match[1])
                break
        else:
            return None
    if current:
        records.append(current)
    return records


def _text_records(text):
    lines = _text_lines(text)
    start = next((i for i, line in enumerate(lines) if _EDUCATION_START.fullmatch(line)), None)
    if start is None:
        return []
    scoped = lines[start + 1:]
    end = next((i for i, line in enumerate(scoped) if _EDUCATION_STOP.fullmatch(line)), len(scoped))
    scoped = scoped[:end]
    labeled = _labeled_text_records(scoped)
    if labeled is not None:
        return labeled
    records = []
    for i, line in enumerate(scoped):
        if _SCHOOL_LINE.match(line) or _MAJOR_LINE.match(line):
            continue
        labeled_degree = _DEGREE_LINE.match(line)
        degree = labeled_degree[1] if labeled_degree else line
        degree_parts = re.split(r'[，,、]', degree, maxsplit=1)
        degree = degree_parts[0]
        if _degree_rank(degree) < 0:
            continue
        major = _clean(degree_parts[1]) if len(degree_parts) > 1 else ''
        school = ''
        for candidate in reversed(scoped[max(0, i - 4):i]):
            match = _SCHOOL_LINE.match(candidate)
            if match:
                school = _clean(match[1])
                break
            if not candidate or _DATE_LINE.match(candidate) or _degree_rank(candidate) >= 0:
                break
            if _NOISE_LINE.match(candidate) or _MAJOR_LINE.match(candidate):
                continue
            school = _clean(candidate)
            break
        if not school:
            for candidate in scoped[i + 1:i + 5]:
                if not candidate or _DATE_LINE.match(candidate):
                    break
                # 标签优先：专业 IMBA/MBA 和学校名称中的学历词都不是新学历。
                match = _SCHOOL_LINE.match(candidate)
                if match:
                    school = _clean(match[1])
                    break
                if _MAJOR_LINE.match(candidate):
                    continue
                if _degree_rank(candidate) >= 0:
                    break
        if not major:
            for candidate in scoped[i + 1:i + 3]:
                match = _MAJOR_LINE.match(candidate)
                if match:
                    major = _clean(match[1])
                    break
                school_match = _SCHOOL_LINE.match(candidate)
                if not school_match or _clean(school_match[1]) != school:
                    break
        if school or major:
            records.append({'school': school, 'major': major, 'degree': degree})
    return records


def _from_text(text):
    text = text.strip()
    if text.startswith(('[', '{')):
        try:
            return _normalize_records(_structured_records(json.loads(text)))
        except ValueError:
            pass
    records = _normalize_records(_text_records(text))
    if _choose_highest(records):
        return records
    # 无多段教育可排序时，仅接受明确标注的单组字段。
    fields = {}
    for key, label in (('school', _SCHOOL_LABEL), ('major', _MAJOR_LABEL)):
        values = [_clean(match) for match in re.findall(
            rf'{label}\*{{0,2}}\s*[:：]\s*([^\n|；;]+)', text, re.I)]
        values = [value for value in values if value]
        if len(values) > 1:
            return []
        fields[key] = values[0] if values else ''
    return _normalize_records([fields])


def _complete_school_only(pair, fallbacks):
    # 原始学历不可识别时不推测数字编码含义，仅接受单段完整教育的佐证。
    candidates = set()
    for records in fallbacks:
        if not records:
            continue
        if len(records) != 1:
            return pair
        rank, candidate = records[0]
        if candidate['school'] != pair['school']:
            continue
        if rank <= 0 or not candidate['major']:
            return pair
        candidates.add((rank, candidate['major']))
    # 不同来源的学历或专业冲突时保持空值。
    if len(candidates) == 1:
        return dict(pair, major=next(iter(candidates))[1])
    return pair


def extract_highest_education(*sources):
    """优先取原始来源；仅用无冲突且唯一对应的教育经历补齐缺失专业。"""
    all_records = [(_from_text(source) if isinstance(source, str)
                    else _normalize_records(_structured_records(source)))
                   for source in sources]
    for index, records in enumerate(all_records):
        selected = _choose_highest(records)
        if selected is None:
            continue
        rank, pair = selected
        if pair['major'] or not pair['school'] or rank == 0:
            return pair
        if rank < 0:
            # _choose_highest 仅在未识别学历且只有一条记录时返回该记录。
            return _complete_school_only(pair, all_records[index + 1:])

        # 学校必须完全一致、学历必须明确相同。双学位等多条对应时不猜测。
        def matching(source_records):
            return [item for item_rank, item in source_records
                    if item_rank == rank and item['school'] == pair['school']]

        if len(matching(records)) != 1:
            return pair
        majors = set()
        for fallback in all_records[index + 1:]:
            matches = matching(fallback)
            if len(matches) > 1:
                return pair
            if matches and matches[0]['major']:
                majors.add(matches[0]['major'])
        if len(majors) == 1:
            return dict(pair, major=next(iter(majors)))
        return pair
    return {'school': '', 'major': ''}


def extract_screening_education(raw_resume, uploaded_resume):
    """卡片与上传正文同源、同段；正文无教育信息时才整组回退。"""
    records = _from_text(uploaded_resume)
    has_education = bool(records) or any(
        _EDUCATION_START.fullmatch(line) or _SCHOOL_LINE.match(line)
        or _MAJOR_LINE.match(line) for line in _text_lines(uploaded_resume))
    source = 'uploaded_resume'
    if not has_education:
        records = (_from_text(raw_resume) if isinstance(raw_resume, str)
                   else _normalize_records(_structured_records(raw_resume)))
        source = 'raw_resume_fallback'
    selected = _choose_highest(records)
    pair = dict(selected[1]) if selected is not None else {'school': '', 'major': ''}
    reason = ('complete' if all(pair.values()) else 'incomplete') if selected else 'unresolved'
    return pair, {'source': source, 'reason': reason, 'record_count': len(records)}


def log_screening_education(logger, stage, pid, uid, fields, selection, response=None):
    """仅记录教育字段和响应状态；诊断失败不得改变上传流程。"""
    try:
        event = {'parser': 'uploaded-resume-v1', 'stage': stage,
                 'position_id': str(pid), 'candidate_id': str(uid),
                 **selection, 'school': fields['school'], 'major': fields['major']}
        if response is not None:
            event['http_status'] = response.status_code
            # HTTP 200 不是字段已入库的证明，单独记录明确的业务成功标志。
            event['business_success'] = None
            try:
                body = response.json()
                if isinstance(body, dict) and isinstance(body.get('success'), bool):
                    event['business_success'] = body['success']
            except (ValueError, TypeError):
                pass
        logger.write_line('高潜教育诊断 ' + json.dumps(event, ensure_ascii=False), active=True)
    except Exception:
        # 日志写入失败不应阻止人才上传或后续候选人处理。
        pass
