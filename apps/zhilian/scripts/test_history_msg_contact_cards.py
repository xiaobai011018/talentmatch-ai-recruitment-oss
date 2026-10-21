# -*- coding: utf-8 -*-
"""校验 IM 联系方式卡片进入聊天语义，但不会泄露联系方式（不调用外部 API）。"""
from pathlib import Path

from backend.core.utils.msg.history_msg import (
    CONTACT_HIDDEN_TEXT,
    candidate_sent_resume,
    get_clean_history_msg,
    get_duplicate_full_chat_history,
    redact_contact_text,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEBUG_IM_DIR = PROJECT_ROOT / "save" / "debug_im"


def _load_fixture(name: str) -> str:
    path = DEBUG_IM_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"缺少 fixture: {path}")
    return path.read_text(encoding="utf-8")


def test_wx_exchange_card_parsed_for_auto_reply():
    """马先生场景：交换微信卡片应进入 Bot 可见的历史。"""
    html = _load_fixture("im_61660ffb21c1ef68fd6252d4bd4bea18_20260615_141900.html")
    clean_msg, clean_bot, clean_candidate = get_clean_history_msg(html)

    wx_lines = [line for line in clean_msg if "交换微信" in line]
    assert wx_lines, "交换微信卡片未被解析"
    assert wx_lines[0].startswith("系统提示：候选人发起交换微信请求")
    assert CONTACT_HIDDEN_TEXT in wx_lines[0]

    assert any("您好 可以的" in line for line in clean_candidate), "候选人文本应保留"
    assert len(clean_bot) >= 1, "Bot 消息条数不应减少"


def test_phone_card_parsed():
    """电话卡片应进入历史。"""
    html = _load_fixture("im_8efd9a9c10f77d0e50e71b29884dfa04_20260615_141933.html")
    clean_msg, _, clean_candidate = get_clean_history_msg(html)

    phone_lines = [line for line in clean_msg if "分享电话" in line or "已将电话发给您" in line]
    assert phone_lines, "电话卡片未被解析"
    assert phone_lines[0].startswith("系统提示：")
    assert clean_candidate, "电话卡片应计入候选人侧互动"


def test_plain_text_session_contact_redacted():
    """崔红玉场景：纯文本会话保留语义，但手机号不能进入聊天记录。"""
    html = _load_fixture("im_5225f9b03d25eb941e12771c729b4f18_20260615_142026.html")
    clean_msg, clean_bot, clean_candidate = get_clean_history_msg(html)

    assert not any("13800000001" in line for line in clean_candidate)
    assert any(CONTACT_HIDDEN_TEXT in line for line in clean_candidate)
    assert len(clean_bot) == 2
    assert len([line for line in clean_msg if line.startswith("系统提示：候选人发起交换微信")]) == 0


def test_attachment_resume_len3_bubble_parsed_for_auto_reply():
    """周生鹏场景：附件简历多 class 气泡（无 --shadow）应进入候选人消息。"""
    html = """
    <div class="im-message">
      <div class="im-message__bubble im-message__bubble--file im-message__bubble--resume">
        <div class="im-message__bubble-inner">
          这是我的附件简历，请查收
        </div>
      </div>
    </div>
    """
    clean_msg, clean_bot, clean_candidate = get_clean_history_msg(html)
    assert clean_candidate, "附件简历应计入 clean_candidate_history"
    assert clean_candidate[0].startswith("候选人说：")
    assert "附件简历" in clean_candidate[0]
    assert not clean_bot


def test_real_attachment_card_two_class_bubble_is_candidate_resume():
    """智联当前页面的 --plain + im-attachment-card 结构应被稳定识别。"""
    html = """
    <div class="im-message">
      <div class="im-message__bubble im-message__bubble--plain">
        <div class="im-message__bubble-inner im-attachment-card">
          您好，这是我的附件简历，请查收 查看附件简历
        </div>
      </div>
    </div>
    """
    clean_msg, clean_bot, clean_candidate = get_clean_history_msg(html)
    assert candidate_sent_resume(html)
    assert clean_candidate == [
        "候选人说：您好，这是我的附件简历，请查收 查看附件简历"
    ]
    assert clean_msg == clean_candidate
    assert not clean_bot


def test_online_resume_toast_is_candidate_resume():
    html = """
    <div class="im-message">
      <div class="im-message__toast">对方向您发送了<span>在线</span><span>简历</span></div>
    </div>
    """
    clean_msg, clean_bot, clean_candidate = get_clean_history_msg(html)
    expected = "系统提示：对方向您发送了在线简历"
    assert candidate_sent_resume(html)
    assert clean_msg == [expected]
    assert clean_candidate == [expected]
    assert not clean_bot


def test_resume_toolbar_outside_message_is_not_candidate_resume():
    html = """
    <div class="im-input-toolbar">
      <button>要附件简历</button>
      <button>要电话</button>
    </div>
    """
    _, _, clean_candidate = get_clean_history_msg(html)
    assert not candidate_sent_resume(html)
    assert not clean_candidate


def test_recruiter_attachment_card_is_not_candidate_resume():
    html = """
    <div class="im-message">
      <div class="im-message__bubble im-message__bubble--me im-message__bubble--plain">
        <div class="im-message__bubble-inner im-attachment-card">
          招聘方发送的附件简历
        </div>
      </div>
    </div>
    """
    _, clean_bot, clean_candidate = get_clean_history_msg(html)
    assert not candidate_sent_resume(html)
    assert clean_bot
    assert not clean_candidate


def test_len3_non_resume_bubble_still_ignored():
    """其它 len==3 未知气泡仍保持忽略，避免误解析。"""
    html = """
    <div class="im-message">
      <div class="im-message__bubble im-message__bubble--foo im-message__bubble--bar">
        <div class="im-message__bubble-inner">系统活动通知</div>
      </div>
    </div>
    """
    _, _, clean_candidate = get_clean_history_msg(html)
    assert not clean_candidate


def test_second_conversation_skip_when_only_wx_card():
    """二次会话筛选：仅发卡片无文字时，应视为候选人已互动。"""
    html = """
    <div class="im-message">
      <div class="im-message__bubble im-message__bubble--shadow">
        <div class="im-message__bubble-inner imc-wx-request">
          <div class="imc-wx-request__title--text--title">我想与你交换微信，方便沟通</div>
          <div class="imc-wx-request__title--text--con">同意后，将会看到彼此的微信号</div>
        </div>
      </div>
    </div>
    """
    _, _, clean_candidate = get_clean_history_msg(html)
    assert clean_candidate, "仅卡片场景也应计入 clean_candidate_history"


def test_plain_phone_and_wechat_redacted():
    html = """
    <div class="im-message">
      <div class="im-message__bubble">
        电话：138-0013-8000，微信号：candidate.wx-01
      </div>
    </div>
    """
    clean_msg, _, clean_candidate = get_clean_history_msg(html)
    history = "\n".join(clean_msg + clean_candidate)
    assert "138-0013-8000" not in history
    assert "candidate.wx-01" not in history
    assert history.count(CONTACT_HIDDEN_TEXT) >= 2


def test_contact_format_variants_redacted_without_touching_normal_text():
    raw_values = (
        "13800138000",
        "+86 138 0013 8000",
        "138-0013-8000",
        "微信号：candidate.wx-01",
        "VX: candidate_vx",
        "WeChat candidate-wx",
    )
    redacted = redact_contact_text("；".join(raw_values))

    for raw_value in raw_values:
        contact_value = raw_value.split()[-1].split("：")[-1]
        assert contact_value not in redacted
    assert redacted.count(CONTACT_HIDDEN_TEXT) == len(raw_values)

    normal_text = "候选人说：可以通过微信沟通，稍后发送项目资料"
    assert redact_contact_text(normal_text) == normal_text


def test_redaction_is_empty_safe_and_idempotent():
    assert redact_contact_text(None) == ""
    assert redact_contact_text("") == ""

    redacted = redact_contact_text("手机号 13800138000，微信号 wx_candidate")
    assert redact_contact_text(redacted) == redacted


def test_all_chat_message_sources_are_redacted():
    html = """
    <div class="im-message">
      <div class="im-message__toast">系统记录电话 13800138000</div>
      <div class="im-message__bubble im-message__bubble--me">
        我的微信号：recruiter_wx
      </div>
    </div>
    <div class="im-message">
      <div class="im-message__bubble im-message__bubble--file im-message__bubble--resume">
        附件简历，电话 +86 139 0013 8000
      </div>
    </div>
    """
    clean_msg, clean_bot, clean_candidate = get_clean_history_msg(html)
    history = "\n".join(clean_msg + clean_bot + clean_candidate)
    assert "13800138000" not in history
    assert "recruiter_wx" not in history
    assert "139 0013 8000" not in history
    assert history.count(CONTACT_HIDDEN_TEXT) >= 3


def test_contact_card_keeps_business_marker_without_contact():
    html = """
    <div class="im-message">
      <div class="im-message__bubble im-message__bubble--shadow">
        <div class="im-message__bubble-inner imc-contact-request">
          我已同意分享电话，手机号：13800138000
        </div>
      </div>
    </div>
    """
    clean_msg, _, clean_candidate = get_clean_history_msg(html)
    assert clean_msg == [f"系统提示：候选人已分享电话（{CONTACT_HIDDEN_TEXT}）"]
    assert clean_candidate == clean_msg
    assert "13800138000" not in clean_msg[0]


def test_wechat_card_keeps_business_marker_without_contact():
    html = """
    <div class="im-message">
      <div class="im-message__bubble im-message__bubble--shadow">
        <div class="im-message__bubble-inner imc-wx-request">
          我已同意交换微信，微信号：candidate_wx
        </div>
      </div>
    </div>
    """
    clean_msg, _, clean_candidate = get_clean_history_msg(html)
    assert clean_msg == [f"系统提示：候选人发起交换微信请求（{CONTACT_HIDDEN_TEXT}）"]
    assert clean_candidate == clean_msg
    assert "candidate_wx" not in clean_msg[0]


def test_old_history_is_redacted_during_merge():
    merged = get_duplicate_full_chat_history(
        "候选人说：手机号 13800138000\nAI招聘官说：收到",
        "AI招聘官说：收到\n候选人说：微信号 wx_candidate",
    )
    assert merged == "\n".join((
        f"候选人说：手机号 {CONTACT_HIDDEN_TEXT}",
        "AI招聘官说：收到",
        f"候选人说：微信号 {CONTACT_HIDDEN_TEXT}",
    ))


def test_merge_keeps_old_history_when_new_history_is_duplicate():
    old_history = "候选人说：您好\nAI招聘官说：收到"
    assert get_duplicate_full_chat_history(old_history, old_history) == old_history


def main() -> None:
    test_attachment_resume_len3_bubble_parsed_for_auto_reply()
    test_real_attachment_card_two_class_bubble_is_candidate_resume()
    test_online_resume_toast_is_candidate_resume()
    test_resume_toolbar_outside_message_is_not_candidate_resume()
    test_recruiter_attachment_card_is_not_candidate_resume()
    test_len3_non_resume_bubble_still_ignored()
    test_second_conversation_skip_when_only_wx_card()
    test_plain_phone_and_wechat_redacted()
    test_contact_format_variants_redacted_without_touching_normal_text()
    test_redaction_is_empty_safe_and_idempotent()
    test_all_chat_message_sources_are_redacted()
    test_contact_card_keeps_business_marker_without_contact()
    test_wechat_card_keeps_business_marker_without_contact()
    test_old_history_is_redacted_during_merge()
    test_merge_keeps_old_history_when_new_history_is_duplicate()
    for name, fn in (
        ("wx_exchange", test_wx_exchange_card_parsed_for_auto_reply),
        ("phone_card", test_phone_card_parsed),
        ("plain_text", test_plain_text_session_contact_redacted),
    ):
        try:
            fn()
        except FileNotFoundError as exc:
            print(f"skip {name}: {exc}")
    print("history_msg contact cards: all assertions passed")


if __name__ == "__main__":
    main()
