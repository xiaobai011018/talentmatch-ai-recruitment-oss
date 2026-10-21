import json
import unittest

from backend.utils.msg.history_msg import _build_conversation_status


def text_msg(direction, opposite_read, msg_time):
    return {
        'direction': direction,
        'oppositeRead': opposite_read,
        'msgTime': msg_time,
        'payload': json.dumps({
            'ext': {'extType': 1},
            'bodies': [{'msg': 'hello'}],
        }),
    }


class ConversationStatusTest(unittest.TestCase):
    def test_unread_when_candidate_never_replied(self):
        self.assertEqual(
            _build_conversation_status([text_msg('0', '0', 1000)]),
            '未读消息',
        )

    def test_read_no_contact_when_candidate_never_replied(self):
        self.assertEqual(
            _build_conversation_status([text_msg('0', '1', 1000)]),
            '已读不回',
        )

    def test_read_with_contact_when_candidate_never_replied(self):
        self.assertEqual(
            _build_conversation_status([text_msg('0', '1', 1000)], clean_phone='13800000000'),
            '有意向沟通',
        )

    def test_unread_with_contact_when_candidate_never_replied(self):
        self.assertEqual(
            _build_conversation_status([text_msg('0', '0', 1000)], clean_wx='wx123'),
            '有意向沟通',
        )

    def test_empty_status_when_candidate_has_replied(self):
        msg_list = [
            text_msg('1', '1', 1000),
            text_msg('0', '0', 2000),
        ]
        self.assertEqual(
            _build_conversation_status(msg_list, clean_phone='13800000000'),
            '',
        )


if __name__ == '__main__':
    unittest.main()
