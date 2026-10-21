# -*- coding: utf-8 -*-
"""校验自动回复使用“我发起 + 未读”，且旧会话筛选协议保持不变。"""
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from backend.core.api.zhilian_api import get_session_detail, get_session_list, get_virtual_number
from backend.core.entity.candidate import Candidate
from backend.manger import Manger, ZhilianAuthenticationError


def _capture_payload(*args, **kwargs):
    with patch("backend.core.api.zhilian_api.requests.post") as post_mock:
        get_session_list(*args, **kwargs)
    return post_mock.call_args.kwargs["json"]


def _item(key, label):
    return {
        "key": key,
        "labelName": label,
        "selected": False,
        "deletable": False,
        "sortable": False,
    }


def test_initiated_by_me_unread_payload():
    payload = _capture_payload(
        {"cookie": "value"},
        1,
        20,
        "all",
        is_unread=True,
        initiated_by_me=True,
    )

    assert payload["withUnread"] is True
    assert payload["userIds"] == []
    assert payload["filterMore"] == [
        {
            "extra": None,
            "groupCode": "MESSAGE_TYPE",
            "groupName": "消息类型",
            "selectionType": "RADIO",
            "trackingEventType": "",
            "items": [
                _item("MESSAGE_TYPE_ALL", "不限"),
                _item("MESSAGE_TYPE_INITIATED_BY_ME", "我发起"),
                _item("MESSAGE_TYPE_INITIATED_BY_TALENT", "人才发起"),
                _item("MESSAGE_TYPE_COLLEAGUE", "同事聊天"),
                _item("MESSAGE_TYPE_MY_PUBLISHED", "我发布的职位"),
                _item("MESSAGE_TYPE_ONLY_DELIVERY", "有投递会话"),
                _item("MESSAGE_TYPE_ONLY_CHAT", "仅聊天会话"),
                _item("MESSAGE_TYPE_USER_ACTIVE_CALL", "求职者主动来电"),
            ],
            "selectedValue": "MESSAGE_TYPE_INITIATED_BY_ME",
            "selectedValues": [],
        },
        {
            "extra": None,
            "groupCode": "CONTACT",
            "groupName": "联系方式",
            "selectionType": "CHECKBOX",
            "trackingEventType": "",
            "items": [
                _item("CONTACT_ALL", "不限"),
                _item("CONTACT_WECHAT", "已获取微信"),
                _item("CONTACT_PHONE", "已获取电话"),
            ],
            "selectedValue": None,
            "selectedValues": [],
        },
        {
            "extra": None,
            "groupCode": "MESSAGE_TIME",
            "groupName": "消息时间",
            "selectionType": "RADIO",
            "trackingEventType": "",
            "items": [
                _item("MESSAGE_TIME_ALL", "不限"),
                _item("MESSAGE_TIME_TODAY", "今天"),
                _item("MESSAGE_TIME_LAST_3_DAYS", "最近3天"),
                _item("MESSAGE_TIME_LAST_7_DAYS", "最近7天"),
                _item("MESSAGE_TIME_LAST_30_DAYS", "最近30天"),
                _item("MESSAGE_TIME_OVER_30_DAYS", "超过30天"),
            ],
            "selectedValue": None,
            "selectedValues": [],
        },
    ]
    assert json.loads(payload["componentFilter"]) == {
        "filterGroups": [
            {
                "extra": None,
                "groupCode": "MESSAGE_TYPE",
                "groupName": "消息类型",
                "selectionType": "RADIO",
                "trackingEventType": "",
                "items": [_item("MESSAGE_TYPE_INITIATED_BY_ME", "我发起")],
                "selectedValues": [],
            }
        ]
    }
    assert "filterTop" not in payload
    assert "activeSessionId" not in payload


def test_initiated_by_me_single_job_payload():
    payload = _capture_payload(
        {},
        2,
        20,
        "all",
        is_unread=True,
        job_number="JOB-123",
        initiated_by_me=True,
    )

    assert payload["pageNo"] == 2
    assert payload["jobNumber"] == "JOB-123"
    assert payload["filterMore"][0]["selectedValue"] == "MESSAGE_TYPE_INITIATED_BY_ME"
    assert json.loads(payload["componentFilter"])["filterGroups"][0]["items"] == [
        _item("MESSAGE_TYPE_INITIATED_BY_ME", "我发起")
    ]


def test_legacy_all_payload_unchanged():
    payload = _capture_payload({}, 1, 20, "all", is_unread=True)

    assert payload == {
        "pageNo": 1,
        "pageSize": 20,
        "activeSessionId": "",
        "sessionType": None,
        "filterTop": "all",
        "aiHostingStates": [],
        "isServer": False,
        "groupSelectorVal": "",
        "singleVisionDirectRecommend": None,
        "componentFilter": "",
        "includeResume": True,
        "userIds": [],
        "withUnread": True,
    }


def test_legacy_second_conversation_payload_unchanged():
    payload = _capture_payload(
        {},
        1,
        20,
        "DEFAULT_INTERESTED",
        is_unread=False,
        job_number="JOB-456",
    )

    assert payload == {
        "pageNo": 1,
        "pageSize": 20,
        "activeSessionId": "",
        "sessionType": None,
        "filterTop": "DEFAULT_INTERESTED",
        "aiHostingStates": [],
        "isServer": False,
        "groupSelectorVal": "",
        "singleVisionDirectRecommend": None,
        "componentFilter": (
            '{"filterGroups":[{"extra":null,"groupCode":"DEFAULT","groupName":"",'
            '"selectionType":"RADIO","trackingEventType":"","items":['
            '{"key":"DEFAULT_INTERESTED","labelName":"我发起对方未回复",'
            '"selected":false,"deletable":false,"sortable":true}]}]}'
        ),
        "includeResume": True,
        "jobNumber": "JOB-456",
    }


def test_get_virtual_number_payload_matches_call_button_request():
    with patch("backend.core.api.zhilian_api.requests.post") as post_mock:
        get_virtual_number({}, "JOB-1", "RESUME-1", "1")

    assert post_mock.call_args.kwargs["json"] == {
        "jobNumber": "JOB-1",
        "resumeNumber": "RESUME-1",
        "resumeLanguage": "1",
        "isCampusWidget": False,
    }


def test_get_session_detail_does_not_mark_read():
    with patch("backend.core.api.zhilian_api.requests.post") as post_mock:
        get_session_detail({}, "SESSION-1")

    assert post_mock.call_args.kwargs["json"] == {
        "sessionId": "SESSION-1",
        "isCampusWidget": False,
        "markRead": False,
        "includeResumeDetail": False,
    }


def test_auto_reply_all_jobs_enables_initiated_by_me():
    response = Mock(text='{"data":[]}')
    manager = Manger()

    with (
        patch.object(manager, "set_cookies"),
        patch.object(manager, "_collect_active_job_numbers", return_value={"JOB-123"}),
        patch("backend.manger.get_session_list", return_value=response) as get_session_list_mock,
    ):
        manager.auto_reply("ignored.json", "all")

    assert get_session_list_mock.call_args.kwargs["is_unread"] is True
    assert get_session_list_mock.call_args.kwargs["initiated_by_me"] is True


def test_auto_reply_single_job_enables_initiated_by_me():
    response = Mock(text='{"data":[]}')
    manager = Manger()

    def set_current_job(_position_id):
        manager.current_job_number = "JOB-456"
        return True

    with (
        patch.object(manager, "set_cookies"),
        patch.object(manager, "check_and_set_job", side_effect=set_current_job),
        patch("backend.manger.get_session_list", return_value=response) as get_session_list_mock,
    ):
        manager.auto_reply("ignored.json", "single", "POSITION-789")

    assert get_session_list_mock.call_args.kwargs["is_unread"] is True
    assert get_session_list_mock.call_args.kwargs["job_number"] == "JOB-456"
    assert get_session_list_mock.call_args.kwargs["initiated_by_me"] is True


def test_second_conversation_does_not_enable_initiated_by_me():
    response = Mock(text='{"data":[]}')
    manager = Manger()

    with patch("backend.manger.get_session_list", return_value=response) as get_session_list_mock:
        manager._load_second_conversation_sessions("JOB-SECOND", Mock())

    call = get_session_list_mock.call_args
    assert call.args[3] == "DEFAULT_INTERESTED"
    assert call.kwargs["is_unread"] is False
    assert call.kwargs["job_number"] == "JOB-SECOND"
    assert "initiated_by_me" not in call.kwargs


def test_save_resume_does_not_enable_initiated_by_me():
    response = Mock(text='{"data":[]}')
    manager = Manger()

    with (
        patch.object(manager, "set_cookies"),
        patch.object(manager, "_collect_active_job_numbers", return_value={"JOB-SAVE"}),
        patch("backend.manger.get_session_list", return_value=response) as get_session_list_mock,
    ):
        manager.save_resume("ignored.json", "all", Mock(), Mock())

    call = get_session_list_mock.call_args
    assert call.args[3] == "all"
    assert call.kwargs["is_unread"] is False
    assert "initiated_by_me" not in call.kwargs


def _assert_zhilian_authentication_error(action):
    try:
        action()
    except ZhilianAuthenticationError as exc:
        assert "智联登录已失效或触发安全认证" in str(exc)
        return
    raise AssertionError("预期抛出 ZhilianAuthenticationError")


def test_save_resume_stops_when_session_list_authentication_expires():
    response = Mock(text=json.dumps({
        "code": 401,
        "data": None,
        "message": "您的账号登录已失效，请重新登录",
    }))
    manager = Manger()

    with (
        patch.object(manager, "set_cookies"),
        patch.object(manager, "_collect_active_job_numbers", return_value={"JOB-SAVE"}),
        patch("backend.manger.get_session_list", return_value=response),
    ):
        _assert_zhilian_authentication_error(
            lambda: manager.save_resume("ignored.json", "all", Mock(), Mock())
        )


def test_save_resume_stops_when_resume_authentication_expires():
    manager = Manger()
    session = {
        "name": "测试候选人",
        "jobNumber": "JOB-SAVE",
        "resumeNumber": "RESUME-SAVE",
        "resumeLanguage": "1",
        "sessionId": "SESSION-SAVE",
        "userId": "USER-SAVE",
    }
    session_response = Mock(text=json.dumps({"data": [session]}))
    empty_response = Mock(text=json.dumps({"data": []}))
    auth_response = Mock(text=json.dumps({
        "code": 401,
        "data": None,
        "message": "您的账号登录已失效，请重新登录",
    }))

    def set_current_job(_position_id):
        manager.current_job_number = "JOB-SAVE"
        return True

    def collect_sessions(_end_time, sessions, _start_time):
        manager.current_session_list.extend(sessions)

    with (
        patch.object(manager, "set_cookies"),
        patch.object(manager, "check_and_set_job", side_effect=set_current_job),
        patch.object(manager, "set_save_resume_session_list", side_effect=collect_sessions),
        patch("backend.manger.get_session_list", side_effect=[session_response, empty_response]),
        patch("backend.manger.get_incharge_id_by_position_id"),
        patch("backend.manger.get_ah_result_dict", return_value={"results": [{"incharge_id": 100}]}),
        patch("backend.manger.get_session_resume", return_value=auth_response),
        patch("backend.manger.Candidate.from_raw_resume") as candidate_mock,
    ):
        _assert_zhilian_authentication_error(
            lambda: manager.save_resume("ignored.json", "single", Mock(), Mock(), "4416")
        )

    candidate_mock.assert_not_called()


def _run_save_resume(
    chat_html,
    phone="",
    wechat="",
    resume_extra=None,
    virtual_phone="",
    virtual_number_error=None,
    last_message_read_time=None,
    msg_receipt_time=None,
    last_sentence_send_time=1000,
):
    manager = Manger()
    session = {
        "name": "测试候选人",
        "jobNumber": "JOB-SAVE",
        "resumeNumber": "RESUME-SAVE",
        "resumeLanguage": "1",
        "sessionId": "SESSION-SAVE",
        "userId": "USER-SAVE",
    }
    session_response = Mock(text=json.dumps({"data": [session]}))
    empty_response = Mock(text=json.dumps({"data": []}))
    resume_data = {
        "user": {"phone": phone},
        "resumeSession": {"wechat": wechat},
    }
    resume_data.update(resume_extra or {})
    resume_response = Mock(text=json.dumps({"data": resume_data}))
    virtual_number_response = Mock(text=json.dumps({
        "data": {"phone": virtual_phone}
    }))
    session_detail_response = Mock(text=json.dumps({
        "data": {
            "lastSentence": json.dumps({
                "senderType": "STAFF",
                "sendTime": last_sentence_send_time,
            }),
            "lastMessageReadTime": last_message_read_time,
            "msg": {"msgReceiptTime": msg_receipt_time},
        }
    }))
    candidate = Mock()

    def set_current_job(_position_id):
        manager.current_job_number = "JOB-SAVE"
        return True

    def collect_sessions(_end_time, sessions, _start_time):
        manager.current_session_list.extend(sessions)

    def get_virtual_number_result(*_args, **_kwargs):
        if virtual_number_error:
            raise virtual_number_error
        return virtual_number_response

    with (
        patch.object(manager, "set_cookies"),
        patch.object(manager, "check_and_set_job", side_effect=set_current_job),
        patch.object(manager, "set_save_resume_session_list", side_effect=collect_sessions),
        patch.object(manager, "extract_phone_from_resume_remark", return_value=""),
        patch("backend.manger.get_session_list", side_effect=[session_response, empty_response]),
        patch("backend.manger.get_incharge_id_by_position_id"),
        patch("backend.manger.get_ah_result_dict", return_value={"results": [{"incharge_id": 100}]}),
        patch("backend.manger.get_session_resume", return_value=resume_response),
        patch(
            "backend.manger.get_virtual_number",
            side_effect=get_virtual_number_result,
        ) as get_virtual_number_mock,
        patch("backend.manger.get_session_html", return_value=Mock(text=chat_html)),
        patch("backend.manger.get_session_detail", return_value=session_detail_response),
        patch("backend.manger.Candidate.from_raw_resume", return_value=candidate),
        patch("backend.manger.set_msg_read") as set_msg_read_mock,
    ):
        manager.save_resume("ignored.json", "single", Mock(), Mock(), "4416")

    candidate.get_virtual_number_call_count = get_virtual_number_mock.call_count
    return candidate, set_msg_read_mock


def _session_for_filter(unread_count=1):
    return {
        "name": "测试候选人",
        "jobTitle": "HRD4416",
        "jobNumber": "JOB-SAVE",
        "sessionId": "SESSION-SAVE",
        "unreadCount": unread_count,
        "communicateTime": int(datetime.now().timestamp() * 1000),
    }


def test_save_resume_unread_filter_only_releases_confirmed_resume_message():
    cases = (
        (
            '<div class="im-message"><div class="im-message__bubble">普通未读回复</div></div>',
            False,
        ),
        (
            '<div class="im-message"><div class="im-message__toast">'
            '对方向您发送了在线简历</div></div>',
            True,
        ),
        (
            '<div class="im-message"><div class="im-message__bubble im-message__bubble--plain">'
            '<div class="im-message__bubble-inner im-attachment-card">'
            '您好，这是我的附件简历，请查收</div></div></div>',
            True,
        ),
    )

    for chat_html, should_release in cases:
        manager = Manger()
        now = datetime.now()
        with patch("backend.manger.get_session_html", return_value=Mock(text=chat_html)):
            manager.set_save_resume_session_list(
                now + timedelta(minutes=1),
                [_session_for_filter()],
                now - timedelta(minutes=1),
            )
        assert bool(manager.current_session_list) is should_release


def test_save_resume_read_session_keeps_original_filter_without_html_probe():
    manager = Manger()
    now = datetime.now()
    with patch("backend.manger.get_session_html") as get_html_mock:
        manager.set_save_resume_session_list(
            now + timedelta(minutes=1),
            [_session_for_filter(unread_count=0)],
            now - timedelta(minutes=1),
        )
    assert len(manager.current_session_list) == 1
    get_html_mock.assert_not_called()


def test_save_resume_sets_unread_tag_when_candidate_did_not_reply():
    candidate, set_msg_read_mock = _run_save_resume("""
        <div class="im-message">
          <div class="im-message__bubble im-message__bubble--me">您好，方便聊一聊吗？</div>
        </div>
        <div class="im-message">
          <div class="im-message__bubble im-message__bubble--me im-message__bubble--shadow">
            <div class="im-message__bubble-inner imc-wx-request">我想与您交换微信，方便沟通</div>
          </div>
        </div>
    """)

    candidate.sync_high_potential_by_smart_keywords.assert_called_once_with(
        chat_history=(
            "AI招聘官说：您好，方便聊一聊吗？\n"
            "AI招聘官说：我想与您交换微信，方便沟通"
        ),
        rule_tag="未读消息",
    )
    candidate.upload_resume_to_anyJob.assert_not_called()
    set_msg_read_mock.assert_called_once()


def test_save_resume_sets_read_no_reply_tag_from_receipt_time():
    candidate, _ = _run_save_resume(
        """
        <div class="im-message">
          <div class="im-message__bubble im-message__bubble--me">您好，方便聊一聊吗？</div>
        </div>
        """,
        last_message_read_time=1001,
        last_sentence_send_time=1000,
    )

    candidate.sync_high_potential_by_smart_keywords.assert_called_once_with(
        chat_history="AI招聘官说：您好，方便聊一聊吗？",
        rule_tag="已读不回",
    )


def test_save_resume_uses_latest_receipt_time():
    candidate, _ = _run_save_resume(
        """
        <div class="im-message">
          <div class="im-message__bubble im-message__bubble--me">您好，方便聊一聊吗？</div>
        </div>
        """,
        last_message_read_time=900,
        msg_receipt_time=1000,
        last_sentence_send_time=1000,
    )

    assert (
        candidate.sync_high_potential_by_smart_keywords.call_args.kwargs["rule_tag"]
        == "已读不回"
    )


def test_save_resume_keeps_unread_when_receipt_predates_latest_message():
    candidate, _ = _run_save_resume(
        """
        <div class="im-message">
          <div class="im-message__bubble im-message__bubble--me">这是最新一条消息</div>
        </div>
        """,
        last_message_read_time=999,
        msg_receipt_time=998,
        last_sentence_send_time=1000,
    )

    assert (
        candidate.sync_high_potential_by_smart_keywords.call_args.kwargs["rule_tag"]
        == "未读消息"
    )


def test_conversation_rule_tag_priorities_do_not_fetch_read_state():
    manager = Manger()
    session = {"sessionId": "SESSION-1"}

    with patch("backend.manger.get_session_detail") as detail_mock:
        assert manager.get_conversation_rule_tag(
            session,
            [],
            phone="13800138000",
        ) == "有意向沟通"
        assert manager.get_conversation_rule_tag(
            session,
            [],
            wechat="candidate_wechat",
        ) == "有意向沟通"
        assert manager.get_conversation_rule_tag(
            session,
            [],
            resume_shared=True,
        ) == "有意向沟通"
        assert manager.get_conversation_rule_tag(
            session,
            ["候选人说：薪资太低了"],
        ) == ""

    detail_mock.assert_not_called()


def test_save_resume_syncs_all_tag_inputs_when_candidate_replied_with_text():
    candidate_messages = (
        "工作地点不考虑",
        "薪资太低了",
        "这个岗位不匹配",
        "不感兴趣",
        "可以进一步沟通",
        "已经入职，不看机会",
    )

    for candidate_message in candidate_messages:
        candidate, _ = _run_save_resume(f"""
            <div class="im-message">
              <div class="im-message__bubble im-message__bubble--me">您好，方便聊一聊吗？</div>
            </div>
            <div class="im-message">
              <div class="im-message__bubble">{candidate_message}</div>
            </div>
        """)

        candidate.sync_high_potential_by_smart_keywords.assert_called_once()
        chat_history = candidate.sync_high_potential_by_smart_keywords.call_args.kwargs["chat_history"]
        assert "AI招聘官说：您好，方便聊一聊吗？" in chat_history
        assert f"候选人说：{candidate_message}" in chat_history
        assert candidate.sync_high_potential_by_smart_keywords.call_args.kwargs["rule_tag"] == ""
        candidate.upload_resume_to_anyJob.assert_not_called()


def test_save_resume_syncs_tag_when_candidate_sent_contact_card():
    contact_cards = (
        ("imc-wx-request", "我已同意交换微信", "系统提示：候选人发起交换微信请求"),
        ("imc-contact-request", "我已同意分享电话", "系统提示：候选人已分享电话"),
    )

    for card_class, card_text, expected_history in contact_cards:
        candidate, _ = _run_save_resume(f"""
            <div class="im-message">
              <div class="im-message__bubble im-message__bubble--shadow">
                <div class="im-message__bubble-inner {card_class}">{card_text}</div>
              </div>
            </div>
        """)

        candidate.sync_high_potential_by_smart_keywords.assert_called_once()
        chat_history = candidate.sync_high_potential_by_smart_keywords.call_args.kwargs["chat_history"]
        assert expected_history in chat_history


def test_save_resume_syncs_tag_when_candidate_sent_resume_attachment():
    candidate, _ = _run_save_resume("""
        <div class="im-message">
          <div class="im-message__bubble im-message__bubble--file im-message__bubble--resume">
            <div class="im-message__bubble-inner">这是我的附件简历，请查收</div>
          </div>
        </div>
    """)

    candidate.sync_high_potential_by_smart_keywords.assert_called_once()
    chat_history = candidate.sync_high_potential_by_smart_keywords.call_args.kwargs["chat_history"]
    assert "候选人说：这是我的附件简历，请查收" in chat_history
    assert candidate.sync_high_potential_by_smart_keywords.call_args.kwargs["rule_tag"] == "有意向沟通"


def test_save_resume_uses_call_button_phone_after_online_resume():
    candidate, set_msg_read_mock = _run_save_resume(
        """
        <div class="im-message">
          <div class="im-message__toast">对方向您发送了在线简历</div>
        </div>
        """,
        resume_extra={
            "interactivePhoneButton": "CALL_NOW",
            "viewPhoneButton": "NORMAL_PHONE",
        },
        virtual_phone="13800138000",
    )

    candidate.sync_high_potential_by_smart_keywords.assert_not_called()
    candidate.upload_resume_to_anyJob.assert_called_once()
    assert candidate.upload_resume_to_anyJob.call_args.args[:2] == ("13800138000", "")
    assert candidate.upload_resume_to_anyJob.call_args.kwargs["rule_tag"] == "有意向沟通"
    assert candidate.get_virtual_number_call_count == 1
    set_msg_read_mock.assert_called_once()


def test_save_resume_uses_call_button_phone_after_attachment_resume():
    candidate, _ = _run_save_resume(
        """
        <div class="im-message">
          <div class="im-message__bubble im-message__bubble--plain">
            <div class="im-message__bubble-inner im-attachment-card">
              您好，这是我的附件简历，请查收
            </div>
          </div>
        </div>
        """,
        resume_extra={
            "interactivePhoneButton": "CALL_NOW",
            "viewPhoneButton": "UNLOCKED_PHONE",
        },
        virtual_phone="13900139000",
    )

    candidate.upload_resume_to_anyJob.assert_called_once()
    assert candidate.upload_resume_to_anyJob.call_args.args[:2] == ("13900139000", "")
    assert candidate.upload_resume_to_anyJob.call_args.kwargs["rule_tag"] == "有意向沟通"
    assert candidate.get_virtual_number_call_count == 1


def test_save_resume_does_not_call_phone_endpoint_without_call_now():
    candidate, _ = _run_save_resume(
        """
        <div class="im-message">
          <div class="im-message__toast">对方向您发送了在线简历</div>
        </div>
        """,
        resume_extra={
            "interactivePhoneButton": "CALL_FOR",
            "viewPhoneButton": "NORMAL_PHONE",
        },
        virtual_phone="13800138000",
    )

    candidate.upload_resume_to_anyJob.assert_not_called()
    candidate.sync_high_potential_by_smart_keywords.assert_called_once()
    assert candidate.sync_high_potential_by_smart_keywords.call_args.kwargs["rule_tag"] == "有意向沟通"
    assert candidate.get_virtual_number_call_count == 0


def test_save_resume_does_not_call_phone_endpoint_without_resume_signal():
    candidate, _ = _run_save_resume(
        """
        <div class="im-message">
          <div class="im-message__bubble">可以进一步沟通</div>
        </div>
        """,
        resume_extra={
            "interactivePhoneButton": "CALL_NOW",
            "viewPhoneButton": "NORMAL_PHONE",
        },
        virtual_phone="13800138000",
    )

    candidate.upload_resume_to_anyJob.assert_not_called()
    candidate.sync_high_potential_by_smart_keywords.assert_called_once()
    assert candidate.get_virtual_number_call_count == 0


def test_save_resume_call_button_failure_falls_back_without_aborting():
    candidate, set_msg_read_mock = _run_save_resume(
        """
        <div class="im-message">
          <div class="im-message__toast">对方向您发送了在线简历</div>
        </div>
        """,
        resume_extra={
            "interactivePhoneButton": "CALL_NOW",
            "viewPhoneButton": "NORMAL_PHONE",
        },
        virtual_number_error=RuntimeError("mock getVirtualNumber failure"),
    )

    candidate.upload_resume_to_anyJob.assert_not_called()
    candidate.sync_high_potential_by_smart_keywords.assert_called_once()
    assert candidate.sync_high_potential_by_smart_keywords.call_args.kwargs["rule_tag"] == "有意向沟通"
    assert candidate.get_virtual_number_call_count == 1
    set_msg_read_mock.assert_called_once()


def test_save_resume_does_not_swallow_authentication_error_from_call_button():
    _assert_zhilian_authentication_error(
        lambda: _run_save_resume(
            """
            <div class="im-message">
              <div class="im-message__toast">对方向您发送了在线简历</div>
            </div>
            """,
            resume_extra={
                "interactivePhoneButton": "CALL_NOW",
                "viewPhoneButton": "NORMAL_PHONE",
            },
            virtual_number_error=ZhilianAuthenticationError("智联登录已失效或触发安全认证"),
        )
    )


def test_extract_available_phone_accepts_unlocked_phone_but_rejects_masked_phone():
    manager = Manger()
    assert manager.extract_available_phone({
        "user": {"phone": "138****8000", "unlockedPhone": "138 0013 8000"},
        "resumeSession": {},
    }) == "13800138000"
    assert manager.extract_available_phone({
        "user": {"phone": "138****8000", "unlockedPhone": "138****8000"},
        "resumeSession": {},
    }) == ""


def test_save_resume_with_contact_still_uses_formal_upload_path():
    contact_fields = (
        ("13800138000", ""),
        ("", "candidate_wechat"),
    )

    for phone, wechat in contact_fields:
        candidate, set_msg_read_mock = _run_save_resume("""
            <div class="im-message">
              <div class="im-message__bubble im-message__bubble--me">您好，方便聊一聊吗？</div>
            </div>
        """, phone=phone, wechat=wechat)

        candidate.sync_high_potential_by_smart_keywords.assert_not_called()
        candidate.upload_resume_to_anyJob.assert_called_once()
        assert candidate.upload_resume_to_anyJob.call_args.args[:2] == (phone, wechat)
        assert candidate.upload_resume_to_anyJob.call_args.kwargs["rule_tag"] == "有意向沟通"
        assert candidate.get_virtual_number_call_count == 0
        set_msg_read_mock.assert_called_once()


def _candidate_for_chat_tag_test():
    candidate = Candidate(
        name="测试候选人",
        currentCompany="测试公司",
        currentPosition="测试岗位",
        schoolName="测试大学",
        major="测试专业",
        rawResume="{}",
        salary="",
        position_id="4416",
        incharge_id="100",
        now_region="",
    )
    candidate.is_duplicate_with_current_position = True
    candidate.resume_id = 123
    return candidate


def test_rule_tag_skips_chat_tag_model():
    candidate = _candidate_for_chat_tag_test()

    with (
        patch.object(candidate, "check_screening_is_duplicate_with_smart_keywords"),
        patch("backend.core.entity.candidate.chatBot.send") as chat_bot_mock,
        patch("backend.core.entity.candidate.update_screening_resume") as update_mock,
    ):
        assert candidate.sync_high_potential_by_smart_keywords(
            chat_history="AI招聘官说：您好",
            rule_tag="未读消息",
        )

    chat_bot_mock.assert_not_called()
    update_mock.assert_called_once_with(
        123,
        chat_history="AI招聘官说：您好",
        chat_tags="未读消息",
    )


def test_empty_rule_tag_uses_chat_tag_model():
    candidate = _candidate_for_chat_tag_test()

    with (
        patch.object(candidate, "check_screening_is_duplicate_with_smart_keywords"),
        patch(
            "backend.core.entity.candidate.chatBot.send",
            return_value="薪资不符合",
        ) as chat_bot_mock,
        patch("backend.core.entity.candidate.update_screening_resume") as update_mock,
    ):
        assert candidate.sync_high_potential_by_smart_keywords(
            chat_history="候选人说：薪资太低了",
            rule_tag="",
        )

    chat_bot_mock.assert_called_once()
    update_mock.assert_called_once_with(
        123,
        chat_history="候选人说：薪资太低了",
        chat_tags="薪资不符合",
    )


def test_formal_upload_forwards_rule_tag_to_screening_sync():
    candidate = _candidate_for_chat_tag_test()

    def mark_formal_duplicate(*_args):
        candidate.is_duplicate_with_current_position = True
        candidate.resume_id = 456

    with (
        patch.object(candidate, "set_incharge_id_by_recommend_id"),
        patch.object(
            candidate,
            "sync_high_potential_by_smart_keywords",
            return_value=False,
        ) as sync_mock,
        patch.object(
            candidate,
            "check_is_duplicate_with_phone_wx",
            side_effect=mark_formal_duplicate,
        ),
        patch.object(candidate, "_merge_existing_chat_history", return_value="合并后的聊天记录"),
        patch("backend.core.entity.candidate.update_chat_history"),
        patch("backend.core.entity.candidate.chatBot.send", return_value="104"),
        patch("backend.core.entity.candidate.update_status_tag"),
    ):
        candidate.upload_resume_to_anyJob(
            "13800138000",
            "",
            "候选人说：这是我的简历",
            "500",
            "测试账号",
            rule_tag="有意向沟通",
        )

    sync_mock.assert_called_once_with(
        chat_history="候选人说：这是我的简历",
        phone="13800138000",
        vx="",
        rule_tag="有意向沟通",
    )


def main():
    test_initiated_by_me_unread_payload()
    test_initiated_by_me_single_job_payload()
    test_legacy_all_payload_unchanged()
    test_legacy_second_conversation_payload_unchanged()
    test_get_virtual_number_payload_matches_call_button_request()
    test_get_session_detail_does_not_mark_read()
    test_auto_reply_all_jobs_enables_initiated_by_me()
    test_auto_reply_single_job_enables_initiated_by_me()
    test_second_conversation_does_not_enable_initiated_by_me()
    test_save_resume_does_not_enable_initiated_by_me()
    test_save_resume_stops_when_session_list_authentication_expires()
    test_save_resume_stops_when_resume_authentication_expires()
    test_save_resume_unread_filter_only_releases_confirmed_resume_message()
    test_save_resume_read_session_keeps_original_filter_without_html_probe()
    test_save_resume_sets_unread_tag_when_candidate_did_not_reply()
    test_save_resume_sets_read_no_reply_tag_from_receipt_time()
    test_save_resume_uses_latest_receipt_time()
    test_save_resume_keeps_unread_when_receipt_predates_latest_message()
    test_conversation_rule_tag_priorities_do_not_fetch_read_state()
    test_save_resume_syncs_all_tag_inputs_when_candidate_replied_with_text()
    test_save_resume_syncs_tag_when_candidate_sent_contact_card()
    test_save_resume_syncs_tag_when_candidate_sent_resume_attachment()
    test_save_resume_uses_call_button_phone_after_online_resume()
    test_save_resume_uses_call_button_phone_after_attachment_resume()
    test_save_resume_does_not_call_phone_endpoint_without_call_now()
    test_save_resume_does_not_call_phone_endpoint_without_resume_signal()
    test_save_resume_call_button_failure_falls_back_without_aborting()
    test_save_resume_does_not_swallow_authentication_error_from_call_button()
    test_extract_available_phone_accepts_unlocked_phone_but_rejects_masked_phone()
    test_save_resume_with_contact_still_uses_formal_upload_path()
    test_rule_tag_skips_chat_tag_model()
    test_empty_rule_tag_uses_chat_tag_model()
    test_formal_upload_forwards_rule_tag_to_screening_sync()
    print("auto reply session filter: all assertions passed")


if __name__ == "__main__":
    main()
