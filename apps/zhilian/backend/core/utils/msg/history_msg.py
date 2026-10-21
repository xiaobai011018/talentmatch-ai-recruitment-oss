from datetime import datetime, timedelta, timezone

# 北京时间 UTC+8
CN_TZ = timezone(timedelta(hours=8))

import re

from bs4 import BeautifulSoup


CONTACT_HIDDEN_TEXT = "[联系方式已隐藏，解锁后查看]"
ONLINE_RESUME_TEXT = "对方向您发送了在线简历"
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[\s-]*)?1[3-9](?:[\s-]*\d){9}(?!\d)")
_WECHAT_PATTERN = re.compile(
    r"((?:微信号\s*[:：]?\s*|(?:微信|[Vv][Xx]|[Ww]e[Cc]hat)(?:\s*[:：]\s*|\s+)))"
    r"([A-Za-z0-9][A-Za-z0-9._-]{2,})"
)


def redact_contact_text(text) -> str:
    """隐藏聊天文本中的手机号和带明确标签的微信号。"""
    if text is None:
        return ""

    redacted = _PHONE_PATTERN.sub(CONTACT_HIDDEN_TEXT, str(text))
    return _WECHAT_PATTERN.sub(
        lambda match: f"{match.group(1)}{CONTACT_HIDDEN_TEXT}",
        redacted,
    )


def parse_message_datetime(time_text: str, now_dt: datetime = None) -> datetime:
    """
    解析目标网页的消息时间文本，支持：
    1. 2026年4月2日 下午 4:29
    2. 4月2日 下午 4:29
    3. 星期三 下午 4:29
    4. 昨天 下午 4:29
    5. 下午 4:29（默认今天）
    6. 兼容旧格式 am/pm
    """
    if now_dt is None:
        now_dt = datetime.now(CN_TZ)

    time_text = time_text.strip()

    # 1. 提取 hh:mm
    hm_match = re.search(r'(\d{1,2}):(\d{2})', time_text)
    if hm_match:
        hour = int(hm_match.group(1))
        minute = int(hm_match.group(2))
    else:
        # 连时间都没有时，才退化为当前时间
        hour = now_dt.hour
        minute = now_dt.minute

    # 2. 提取 上午/下午/am/pm，并转换为 24 小时制
    meridiem_match = re.search(r'(上午|下午|am|pm)', time_text, re.IGNORECASE)
    # 智联 IM 页 SSR 有时会用英文 am/pm + UTC 时刻渲染（如 am 12:59），
    # 需要按 UTC 解析后转换为北京时间，避免出现固定少 8 小时。
    use_utc_source = False
    if meridiem_match:
        meridiem = meridiem_match.group(1).lower()
        if meridiem in ('am', 'pm'):
            use_utc_source = True

        if meridiem in ('下午', 'pm'):
            if hour != 12:
                hour += 12
        elif meridiem in ('上午', 'am'):
            if hour == 12:
                hour = 0
    # 如果没匹配到上午/下午/am/pm，则按原始 hour 使用，不再错误套用当前时间

    # 3. 提取日期信息
    year_match = re.search(r'(\d{4})年', time_text)
    month_match = re.search(r'(\d{1,2})月', time_text)
    day_match = re.search(r'(\d{1,2})日', time_text)
    week_match = re.search(r'星期([一二三四五六日天])', time_text)

    # 3.1 年月日
    if year_match and month_match and day_match:
        year = int(year_match.group(1))
        month = int(month_match.group(1))
        day = int(day_match.group(1))
        dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc if use_utc_source else CN_TZ)
        return dt.astimezone(CN_TZ) if use_utc_source else dt

    # 3.2 月日（默认今年）
    elif month_match and day_match:
        month = int(month_match.group(1))
        day = int(day_match.group(1))
        dt = datetime(now_dt.year, month, day, hour, minute, tzinfo=timezone.utc if use_utc_source else CN_TZ)
        return dt.astimezone(CN_TZ) if use_utc_source else dt

    # 3.3 昨天
    elif '昨天' in time_text:
        base_date = now_dt.date() - timedelta(days=1)
        dt = datetime(base_date.year, base_date.month, base_date.day, hour, minute, tzinfo=timezone.utc if use_utc_source else CN_TZ)
        return dt.astimezone(CN_TZ) if use_utc_source else dt

    # 3.4 星期几（近一周内，按最近过去的那个星期几计算）
    elif week_match:
        week_map = {
            "一": 0,
            "二": 1,
            "三": 2,
            "四": 3,
            "五": 4,
            "六": 5,
            "日": 6,
            "天": 6,
        }
        target_weekday = week_map[week_match.group(1)]
        delta_days = (now_dt.weekday() - target_weekday) % 7
        base_date = now_dt - timedelta(days=delta_days)
        dt = datetime(base_date.year, base_date.month, base_date.day, hour, minute, tzinfo=timezone.utc if use_utc_source else CN_TZ)
        return dt.astimezone(CN_TZ) if use_utc_source else dt

    # 3.5 只有“上午/下午 hh:mm”，默认今天
    else:
        dt = datetime(now_dt.year, now_dt.month, now_dt.day, hour, minute, tzinfo=timezone.utc if use_utc_source else CN_TZ)
        return dt.astimezone(CN_TZ) if use_utc_source else dt


def _format_contact_card_line(bubble_el):
    """
    智联 IM 的交换微信/分享电话等卡片使用 im-message__bubble--shadow，
    原逻辑因 len(class)==2 且无 --me 被静默丢弃。
    """
    inner = bubble_el.find(class_='im-message__bubble-inner')
    if not inner:
        text = redact_contact_text(bubble_el.get_text(' ', strip=True))
        return f'系统提示：{text}' if text else None

    inner_classes = inner.get('class', [])
    text = inner.get_text(' ', strip=True)
    if not text:
        return None

    if 'imc-wx-request' in inner_classes:
        return f'系统提示：候选人发起交换微信请求（{CONTACT_HIDDEN_TEXT}）'
    if 'imc-contact-request' in inner_classes:
        return f'系统提示：候选人已分享电话（{CONTACT_HIDDEN_TEXT}）'
    return f'系统提示：{redact_contact_text(text)}'


def _append_contact_card_line(bubble_el, clean_msg_history, clean_candidate_history):
    line = _format_contact_card_line(bubble_el)
    if line:
        clean_msg_history.append(line)
        clean_candidate_history.append(line)


def _is_attachment_resume_bubble_text(text: str) -> bool:
    """附件简历卡片常见文案含「附件」或「简历」，用于收窄 len(class)==3 的解析范围。"""
    if not text:
        return False
    return '附件' in text or '简历' in text


def _is_online_resume_text(text: str) -> bool:
    """智联会把“在线简历”拆成多个 DOM 节点，比较前先移除节点间空白。"""
    return ONLINE_RESUME_TEXT in re.sub(r'\s+', '', text or '')


def _append_attachment_resume_line(bubble_el, clean_msg_history, clean_candidate_history):
    text = redact_contact_text(bubble_el.get_text(' ', strip=True))
    if not _is_attachment_resume_bubble_text(text):
        return
    line = f'候选人说：{text}'
    clean_msg_history.append(line)
    clean_candidate_history.append(line)


def _is_candidate_attachment_resume_bubble(bubble_el) -> bool:
    """只识别候选人侧的附件简历卡片，避免把招聘方卡片或普通工具按钮误判为投递。"""
    class_names = bubble_el.get('class', [])
    if 'im-message__bubble--me' in class_names:
        return False

    inner = bubble_el.find(class_='im-attachment-card')
    if inner:
        return True

    # 兼容智联旧版/实验版的三 class 附件简历气泡。
    return len(class_names) == 3 and _is_attachment_resume_bubble_text(
        bubble_el.get_text(' ', strip=True)
    )


def candidate_sent_resume(html_str) -> bool:
    """判断聊天区内是否存在候选人发送在线简历或附件简历的可靠信号。"""
    soup = BeautifulSoup(html_str or '', 'lxml')
    for msg_el in soup.find_all(class_='im-message'):
        toast_el = msg_el.find(class_='im-message__toast')
        if toast_el and _is_online_resume_text(toast_el.get_text(' ', strip=True)):
            return True

        bubble_el = msg_el.find(class_='im-message__bubble')
        if bubble_el and _is_candidate_attachment_resume_bubble(bubble_el):
            return True
    return False


def get_clean_history_msg(html_str):
    clean_bot_history = []
    clean_candidate_history = []
    clean_msg_history = []
    soup = BeautifulSoup(html_str, 'lxml')
    now_dt = datetime.now(CN_TZ)

    msg_el_list = soup.find_all(class_='im-message')

    for msg_el in msg_el_list:
        time_el = msg_el.find(class_='im-message__time')
        if time_el:
            time_text = time_el.text.strip()
            dt = parse_message_datetime(time_text, now_dt)
            clean_msg_history.append(dt.strftime("%m月%d日 %H:%M"))

        sys_el = msg_el.find(class_='im-message__toast')
        if sys_el:
            system_text = redact_contact_text(sys_el.text.strip())
            system_line = f'系统提示：{system_text}'
            clean_msg_history.append(system_line)
            if _is_online_resume_text(system_text):
                clean_candidate_history.append(system_line)

        msg_buble_el = msg_el.find(class_='im-message__bubble')
        if msg_buble_el:
            class_name = msg_buble_el.get('class', [])

            if 'im-message__bubble--me' in class_name:
                text = redact_contact_text(msg_buble_el.get_text(' ', strip=True))
                if text:
                    clean_msg_history.append(f'AI招聘官说：{text}')
                    clean_bot_history.append(f'AI招聘官说：{text}')
            elif 'im-message__bubble--shadow' in class_name:
                _append_contact_card_line(msg_buble_el, clean_msg_history, clean_candidate_history)
            elif _is_candidate_attachment_resume_bubble(msg_buble_el):
                _append_attachment_resume_line(msg_buble_el, clean_msg_history, clean_candidate_history)
            elif len(class_name) == 1:
                text = redact_contact_text(msg_buble_el.get_text(' ', strip=True))
                if text:
                    clean_msg_history.append(f"候选人说：{text}")
                    clean_candidate_history.append(f"候选人说：{text}")

    return clean_msg_history, clean_bot_history, clean_candidate_history


def get_duplicate_full_chat_history(old_his: str, new_his: str) -> str:
    """
    合并旧聊天记录和新聊天记录，避免重复。
    修正原逻辑中“最后一行被挪到末尾导致顺序错乱”的问题。
    """
    old_his_lines = redact_contact_text(old_his).splitlines() if old_his else []
    new_his_lines = redact_contact_text(new_his).splitlines() if new_his else []

    if not old_his_lines:
        return '\n'.join(new_his_lines)
    if not new_his_lines:
        return '\n'.join(old_his_lines)

    # 找到 new_his 中第一条 old_his 没有的行，从那里开始拼接
    for index, line in enumerate(new_his_lines):
        if line not in old_his_lines:
            return '\n'.join(old_his_lines + new_his_lines[index:])

    # 如果 new_his 全部都已经包含在 old_his 中，则直接返回 old_his
    return '\n'.join(old_his_lines)
