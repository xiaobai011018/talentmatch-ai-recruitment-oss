# -*- coding: utf-8 -*-
"""校验 AnyJob 上传时聊天脱敏、联系方式字段保留（不调用外部 API）。"""
from unittest.mock import Mock, patch

from backend.core.entity.candidate import Candidate
from backend.core.utils.msg.history_msg import CONTACT_HIDDEN_TEXT
from backend.manger import Manger


PHONE = "13800138000"
WECHAT = "wx_candidate"
RAW_CHAT = f"候选人说：电话 {PHONE}，微信号 {WECHAT}"


def test_high_potential_updates_contact_fields_but_redacts_chat():
    candidate = Candidate.__new__(Candidate)
    candidate.name = "测试候选人"
    candidate.position_id = "100"
    candidate.resume_id = 200
    candidate.is_duplicate_with_current_position = False

    def mark_duplicate():
        candidate.is_duplicate_with_current_position = True

    candidate.check_screening_is_duplicate_with_smart_keywords = mark_duplicate

    with (
        patch("backend.core.entity.candidate.chatBot.send", return_value="高意向") as send_mock,
        patch("backend.core.entity.candidate.update_screening_resume") as update_mock,
    ):
        result = candidate.sync_high_potential_by_smart_keywords(
            chat_history=RAW_CHAT,
            phone=PHONE,
            vx=WECHAT,
        )

    assert result is True
    prompt = send_mock.call_args.args[0]
    assert PHONE not in prompt
    assert WECHAT not in prompt

    _, update_kwargs = update_mock.call_args
    assert update_kwargs["phone"] == PHONE
    assert update_kwargs["wechat"] == WECHAT
    assert PHONE not in update_kwargs["chat_history"]
    assert WECHAT not in update_kwargs["chat_history"]
    assert CONTACT_HIDDEN_TEXT in update_kwargs["chat_history"]


def test_intent_upload_keeps_parser_contact_source_but_redacts_chat():
    candidate = Candidate.__new__(Candidate)
    candidate.name = "测试候选人"
    candidate.currentCompany = "测试公司"
    candidate.position_id = "100"
    candidate.incharge_id = "300"
    candidate.smart_keywords = "财务负责人"
    candidate.now_region = "长沙"
    candidate.fact_check_comment_label = "匹配"
    candidate.fact_check_comment = "匹配，经历符合"
    candidate.is_clients = False

    candidate.set_incharge_id_by_recommend_id = Mock()
    candidate.sync_high_potential_by_smart_keywords = Mock(return_value=False)
    candidate.check_is_duplicate_with_phone_wx = Mock()
    candidate.set_fact_check = Mock()
    candidate.get_md_text = Mock(return_value=f"### 手机号\n{PHONE}\n### 微信号\n{WECHAT}")
    candidate.check_status = Mock(return_value="沟通中")
    candidate._compute_upload_coins_cost = Mock(return_value=2)

    add_response = Mock()
    add_response.json.return_value = {"data": [400]}

    with (
        patch("backend.core.entity.candidate.chatBot.send", return_value="有意向") as send_mock,
        patch("backend.core.entity.candidate.h5_post"),
        patch("backend.core.entity.candidate.add_resume", return_value=add_response) as add_mock,
        patch("backend.core.entity.candidate.update_resume"),
    ):
        candidate.upload_resume_to_anyJob(
            phone=PHONE,
            vx=WECHAT,
            chat_history=RAW_CHAT,
            recommend_id="500",
            account_name="招聘账号",
        )

    upload_kwargs = add_mock.call_args.kwargs
    assert PHONE in upload_kwargs["resume"]
    assert WECHAT in upload_kwargs["resume"]
    assert PHONE not in upload_kwargs["chat_history"]
    assert WECHAT not in upload_kwargs["chat_history"]
    assert CONTACT_HIDDEN_TEXT in upload_kwargs["chat_history"]
    assert "智联账号:招聘账号" in upload_kwargs["chat_history"]

    prompt = send_mock.call_args.args[0]
    assert PHONE not in prompt
    assert WECHAT not in prompt
    compute_chat_history = candidate._compute_upload_coins_cost.call_args.args[0]
    assert PHONE not in compute_chat_history
    assert WECHAT not in compute_chat_history


def test_existing_high_potential_continues_to_formal_upload():
    candidate = Candidate.__new__(Candidate)
    candidate.name = "测试候选人"
    candidate.currentCompany = "测试公司"
    candidate.position_id = "100"
    candidate.incharge_id = "300"
    candidate.smart_keywords = "财务负责人"
    candidate.now_region = "长沙"
    candidate.fact_check_comment_label = "匹配"
    candidate.fact_check_comment = "匹配，经历符合"
    candidate.is_clients = False

    candidate.set_incharge_id_by_recommend_id = Mock()

    def sync_high_potential(**_kwargs):
        candidate.resume_id = 200
        candidate.is_duplicate = True
        candidate.is_duplicate_pass = True
        candidate.is_duplicate_with_current_position = True
        return True

    def check_formal_duplicate(_phone, _vx):
        assert candidate.resume_id is None
        assert candidate.is_duplicate_with_current_position is False

    candidate.sync_high_potential_by_smart_keywords = Mock(side_effect=sync_high_potential)
    candidate.check_is_duplicate_with_phone_wx = Mock(side_effect=check_formal_duplicate)
    candidate.set_fact_check = Mock()
    candidate.get_md_text = Mock(return_value=f"### 手机号\n{PHONE}\n### 微信号\n{WECHAT}")
    candidate.check_status = Mock(return_value="沟通中")
    candidate._compute_upload_coins_cost = Mock(return_value=2)

    add_response = Mock()
    add_response.json.return_value = {"data": [400]}

    with (
        patch("backend.core.entity.candidate.chatBot.send", return_value="有意向"),
        patch("backend.core.entity.candidate.h5_post"),
        patch("backend.core.entity.candidate.add_resume", return_value=add_response) as add_mock,
        patch("backend.core.entity.candidate.update_resume"),
    ):
        candidate.upload_resume_to_anyJob(
            phone=PHONE,
            vx=WECHAT,
            chat_history=RAW_CHAT,
            recommend_id="500",
            account_name="招聘账号",
        )

    candidate.sync_high_potential_by_smart_keywords.assert_called_once()
    candidate.check_is_duplicate_with_phone_wx.assert_called_once_with(PHONE, WECHAT)
    add_mock.assert_called_once()


def test_existing_high_potential_uses_formal_resume_id_when_formal_duplicate_exists():
    candidate = Candidate.__new__(Candidate)
    candidate.name = "测试候选人"
    candidate.position_id = "100"
    candidate.incharge_id = "300"

    candidate.set_incharge_id_by_recommend_id = Mock()

    def sync_high_potential(**_kwargs):
        candidate.resume_id = 200
        candidate.is_duplicate = True
        candidate.is_duplicate_pass = True
        candidate.is_duplicate_with_current_position = True
        return True

    def mark_formal_duplicate(_phone, _vx):
        assert candidate.resume_id is None
        assert candidate.is_duplicate_with_current_position is False
        candidate.resume_id = 400
        candidate.is_duplicate = True
        candidate.is_duplicate_with_current_position = True

    candidate.sync_high_potential_by_smart_keywords = Mock(side_effect=sync_high_potential)
    candidate.check_is_duplicate_with_phone_wx = Mock(side_effect=mark_formal_duplicate)
    candidate._get_existing_resume_chat_history = Mock(return_value="AI招聘官说：您好")

    with (
        patch("backend.core.entity.candidate.chatBot.send", return_value="有意向"),
        patch("backend.core.entity.candidate.update_chat_history") as update_chat_mock,
        patch("backend.core.entity.candidate.update_status_tag"),
        patch("backend.core.entity.candidate.add_resume") as add_mock,
    ):
        candidate.upload_resume_to_anyJob(
            phone=PHONE,
            vx=WECHAT,
            chat_history=RAW_CHAT,
            recommend_id="500",
            account_name="招聘账号",
        )

    assert update_chat_mock.call_args.args[0] == 400
    add_mock.assert_not_called()


def test_high_potential_to_formal_is_idempotent_on_repeat():
    candidate = Candidate.__new__(Candidate)
    candidate.name = "测试候选人"
    candidate.currentCompany = "测试公司"
    candidate.position_id = "100"
    candidate.incharge_id = "300"
    candidate.smart_keywords = "财务负责人"
    candidate.now_region = "长沙"
    candidate.fact_check_comment_label = "匹配"
    candidate.fact_check_comment = "匹配，经历符合"
    candidate.is_clients = False

    candidate.set_incharge_id_by_recommend_id = Mock()

    def sync_high_potential(**_kwargs):
        candidate.resume_id = 200
        candidate.is_duplicate = True
        candidate.is_duplicate_pass = True
        candidate.is_duplicate_with_current_position = True
        return True

    formal_check_count = 0

    def check_formal_duplicate(_phone, _vx):
        nonlocal formal_check_count
        formal_check_count += 1
        assert candidate.resume_id is None
        assert candidate.is_duplicate_with_current_position is False
        if formal_check_count == 2:
            candidate.resume_id = 400
            candidate.is_duplicate = True
            candidate.is_duplicate_with_current_position = True

    candidate.sync_high_potential_by_smart_keywords = Mock(side_effect=sync_high_potential)
    candidate.check_is_duplicate_with_phone_wx = Mock(side_effect=check_formal_duplicate)
    candidate.set_fact_check = Mock()
    candidate.get_md_text = Mock(return_value=f"### 手机号\n{PHONE}\n### 微信号\n{WECHAT}")
    candidate.check_status = Mock(return_value="沟通中")
    candidate._compute_upload_coins_cost = Mock(return_value=2)
    candidate._get_existing_resume_chat_history = Mock(return_value="AI招聘官说：您好")

    add_response = Mock()
    add_response.json.return_value = {"data": [400]}

    with (
        patch("backend.core.entity.candidate.chatBot.send", return_value="有意向"),
        patch("backend.core.entity.candidate.h5_post"),
        patch("backend.core.entity.candidate.add_resume", return_value=add_response) as add_mock,
        patch("backend.core.entity.candidate.update_resume") as update_resume_mock,
        patch("backend.core.entity.candidate.update_chat_history") as update_chat_mock,
        patch("backend.core.entity.candidate.update_status_tag"),
    ):
        for _ in range(2):
            candidate.upload_resume_to_anyJob(
                phone=PHONE,
                vx=WECHAT,
                chat_history=RAW_CHAT,
                recommend_id="500",
                account_name="招聘账号",
            )

    assert candidate.sync_high_potential_by_smart_keywords.call_count == 2
    assert candidate.check_is_duplicate_with_phone_wx.call_count == 2
    add_mock.assert_called_once()
    update_resume_mock.assert_called_once_with(
        resume_id=400,
        other_expected_locations="长沙",
    )
    update_chat_mock.assert_called_once()
    assert update_chat_mock.call_args.args[0] == 400


def test_duplicate_intent_update_redacts_old_and_new_chat():
    candidate = Candidate.__new__(Candidate)
    candidate.name = "测试候选人"
    candidate.position_id = "100"
    candidate.resume_id = 200

    candidate.set_incharge_id_by_recommend_id = Mock()
    candidate.sync_high_potential_by_smart_keywords = Mock(return_value=False)

    def mark_duplicate(phone, vx):
        candidate.is_duplicate_with_current_position = True

    candidate.check_is_duplicate_with_phone_wx = mark_duplicate
    candidate._get_existing_resume_chat_history = Mock(
        return_value=f"候选人说：手机号 {PHONE}\nAI招聘官说：收到"
    )

    with (
        patch("backend.core.entity.candidate.update_chat_history") as update_chat_mock,
        patch("backend.core.entity.candidate.update_status_tag"),
        patch("backend.core.entity.candidate.chatBot.send", return_value="有意向") as send_mock,
        patch("backend.core.entity.candidate.add_resume") as add_mock,
    ):
        candidate.upload_resume_to_anyJob(
            phone=PHONE,
            vx=WECHAT,
            chat_history=f"AI招聘官说：收到\n候选人说：微信号 {WECHAT}",
            recommend_id="500",
            account_name="招聘账号",
        )

    merged_history = update_chat_mock.call_args.args[1]
    assert PHONE not in merged_history
    assert WECHAT not in merged_history
    assert merged_history.count(CONTACT_HIDDEN_TEXT) == 2
    assert PHONE not in send_mock.call_args.args[0]
    assert WECHAT not in send_mock.call_args.args[0]
    add_mock.assert_not_called()


def test_redacted_contact_still_stops_repeated_contact_request():
    manager = Manger()
    assert manager.candidate_has_shared_contact(
        [f"候选人说：电话 {CONTACT_HIDDEN_TEXT}"]
    )
    assert manager.candidate_has_shared_contact(
        ["系统提示：候选人发起交换微信请求（[联系方式已隐藏]）"]
    )
    assert not manager.candidate_has_shared_contact(
        ["候选人说：可以通过微信沟通，稍后发送资料"]
    )


def main() -> None:
    test_high_potential_updates_contact_fields_but_redacts_chat()
    test_intent_upload_keeps_parser_contact_source_but_redacts_chat()
    test_existing_high_potential_continues_to_formal_upload()
    test_existing_high_potential_uses_formal_resume_id_when_formal_duplicate_exists()
    test_high_potential_to_formal_is_idempotent_on_repeat()
    test_duplicate_intent_update_redacts_old_and_new_chat()
    test_redacted_contact_still_stops_repeated_contact_request()
    print("contact privacy upload: all assertions passed")


if __name__ == "__main__":
    main()
