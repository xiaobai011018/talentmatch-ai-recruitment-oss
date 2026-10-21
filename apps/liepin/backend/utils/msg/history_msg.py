import datetime
import json

import backend.api.lp as lp


def _get_lp_api(cookies, lp_api=None):
    return lp_api or lp.UserProxy(cookies)


def _collect_chat_messages(lp_api, oppositeImId, maxMessageId=None):
    msg_list = []
    while True:
        res = lp_api.get_chat_his(oppositeImId, maxMessageId)
        current_msg_list = res.json().get('data', {}).get('list', [])
        if not current_msg_list:
            break
        msg_list.extend(current_msg_list)
        maxMessageId = msg_list[-1].get('msgId')
        if not maxMessageId:
            break
    return msg_list


def _extract_clean_histories(msg_list):
    clean_bot_history = []
    clean_candidate_history = []
    clean_msg_history = []

    for msg_dict in msg_list:
        payload = json.loads(msg_dict['payload'])
        if payload['ext']['extType'] >= 200:
            continue
        ts = msg_dict['msgTime'] / 1000
        dt = datetime.datetime.fromtimestamp(ts)
        time_str = dt.strftime("%m月%d日 %H:%M")
        if msg_dict['direction'] == '0':
            if payload.get('bodies', {})[0].get('msg', {}):
                clean_msg_history.append(f"{time_str}\nAI招聘官：{payload['bodies'][0]['msg']}")
                clean_bot_history.append(f"{time_str}\nAI招聘官：{payload['bodies'][0]['msg']}")
        if msg_dict['direction'] == '1':
            if payload.get('bodies', {})[0].get('msg', {}):
                clean_msg_history.append(f"{time_str}\n候选人：{payload['bodies'][0]['msg']}")
                clean_candidate_history.append(f"{time_str}\n候选人：{payload['bodies'][0]['msg']}")

    clean_msg_history.reverse()
    clean_bot_history.reverse()
    clean_candidate_history.reverse()
    return clean_msg_history, clean_bot_history, clean_candidate_history


def _extract_contact_info(lp_api, msg_list, oppositeImId):
    clean_phone = ''
    clean_wx = ''

    for msg_dict in msg_list:
        payload = json.loads(msg_dict['payload'])
        if payload['ext']['extType'] != 207:
            continue
        extBody = payload.get('ext', {}).get('extBody', {})
        bizData = extBody.get('bizData', {})
        if bizData.get('title2'):
            clean_wx = bizData.get('title2')
        if bizData.get('codedTel'):
            codedTel = bizData.get('codedTel')
            res = lp_api.get_phone_number(oppositeImId, codedTel)
            clean_phone = json.loads(res.text)['data']['phone']
        if bizData.get('encodeNum') and bizData.get("title") != "微信号":
            encodeNum = bizData.get('encodeNum')
            res = lp_api.get_encode_number(oppositeImId, encodeNum)
            clean_phone = json.loads(res.text)['data']['result']
        if bizData.get('encodeNum') and bizData.get("title") == "微信号":
            encodeNum = bizData.get('encodeNum')
            res = lp_api.get_encode_number(oppositeImId, encodeNum)
            clean_wx = json.loads(res.text)['data']['result']

    return clean_phone, clean_wx


def _build_conversation_status(msg_list, clean_phone='', clean_wx=''):
    clean_msg_list = []
    is_candidate_reply = False

    for msg_dict in msg_list:
        payload = json.loads(msg_dict['payload'])
        if payload['ext']['extType'] >= 200:
            continue
        if msg_dict['direction'] in ('0', '1'):
            clean_msg_list.append(msg_dict)
        if msg_dict['direction'] == '1':
            is_candidate_reply = True

    clean_msg_list.sort(key=lambda x: x['msgTime'])
    if not clean_msg_list:
        return ''
    if is_candidate_reply:
        return ''

    last_msg = clean_msg_list[-1]
    if last_msg.get("direction", '') == '0' and (clean_phone or clean_wx):
        return "有意向沟通"
    if last_msg.get("direction", '') == '0' and last_msg.get("oppositeRead", '') == '0':
        return "未读消息"
    if last_msg.get("direction", '') == '0' and last_msg.get("oppositeRead", '') == '1':
        return "已读不回"
    return ''


def get_chat_context(cookies, oppositeImId, maxMessageId=None, lp_api=None, msg_list=None):
    lp_api = _get_lp_api(cookies, lp_api)
    msg_list = msg_list or _collect_chat_messages(lp_api, oppositeImId, maxMessageId)
    clean_msg, clean_bot_msg, clean_candidate_msg = _extract_clean_histories(msg_list)
    clean_phone, clean_wx = _extract_contact_info(lp_api, msg_list, oppositeImId)
    conversation_status = _build_conversation_status(msg_list, clean_phone, clean_wx)
    return {
        'msg_list': msg_list,
        'clean_msg': clean_msg,
        'clean_bot_msg': clean_bot_msg,
        'clean_candidate_msg': clean_candidate_msg,
        'clean_phone': clean_phone,
        'clean_wx': clean_wx,
        'conversation_status': conversation_status,
    }


def get_clean_history_msg(cookies, oppositeImId, maxMessageId=None, lp_api=None, msg_list=None):
    chat_context = get_chat_context(cookies, oppositeImId, maxMessageId=maxMessageId, lp_api=lp_api, msg_list=msg_list)
    return chat_context['clean_msg'], chat_context['clean_bot_msg'], chat_context['clean_candidate_msg']


def get_wx_and_phone(cookies, oppositeImId, maxMessageId=None, lp_api=None, msg_list=None):
    chat_context = get_chat_context(cookies, oppositeImId, maxMessageId=maxMessageId, lp_api=lp_api, msg_list=msg_list)
    return chat_context['clean_phone'], chat_context['clean_wx']


def check_conversation_status(cookies, oppositeImId, maxMessageId=None, lp_api=None, msg_list=None):
    chat_context = get_chat_context(cookies, oppositeImId, maxMessageId=maxMessageId, lp_api=lp_api, msg_list=msg_list)
    return chat_context['conversation_status']


# Manual demo removed from repository import; use synthetic fixtures for local testing.





