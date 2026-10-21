"""
@describe:
@fileName: lp.py
@time    : 2025/12/3 上午10:14
@author  : duke
"""
import re

API_LP_SEARCH_RESUMES = 'https://api-h.liepin.com/api/com.liepin.searchfront4r.h.search-resumes'
API_LP_HOME = 'https://h.liepin.com/certification/home'
API_LP_SEARCH_SESSION = 'https://api-h.liepin.com/api/com.liepin.im.h.contact.filter-contacts-v1'
API_LP_SEARCH_JOB = 'https://api-h.liepin.com/api/com.liepin.im.h.contact.get-filter-tags-v1'
API_LP_GET_CHAT_HIS = "https://api-h.liepin.com/api/com.liepin.im.h.chat.chat-list"
API_LP_READ_MSG = 'https://api-h.liepin.com/api/com.liepin.im.h.chat.readed-msg'
API_LP_SEND_MSG = 'https://api-h.liepin.com/api/com.liepin.im.h.chat.send-push'
API_LP_GET_RESUME_DETAIL = 'https://api-h.liepin.com/api/com.liepin.rresume.userh.pc.resume-view'
API_LP_GET_RESUME_WORK_EXP = 'https://api-h.liepin.com/api/com.liepin.rresume.userh.pc.old.get-work-exps'
API_LP_SEARCH_SESSION_PAGE = 'https://api-h.liepin.com/api/com.liepin.im.h.contact.get-contact-list'
API_LP_SEND_WX_OR_PHONE_MSG = 'https://api-h.liepin.com/api/com.liepin.im.h.askfor.send-askfor-request'
API_LP_GET_PHONE_NUM = 'https://api-h.liepin.com/api/com.liepin.im.h.askfor.get-exchange-data'
API_LP_GET_ACCOUNT_INFO = 'https://api-h.liepin.com/api/com.liepin.userh.get-user-base-info'
API_LP_GET_ENCODE_PHONE_NUM = 'https://api-h.liepin.com/api/com.liepin.im.common.click-sensitive-card'
API_LP_CREATE_CHAT = 'https://api-h.liepin.com/api/com.liepin.im.h.chat.to-chat'
API_LP_SAVE_RESUME_NOTE = 'https://api-h.liepin.com/api/com.liepin.rresume.detail.comment-save-old'
API_LP_GET_RESUME_NOTE_LIST = 'https://api-h.liepin.com/api/com.liepin.rresume.detail.get-comment-list-old'

PATTERN_LP_HOME_JS = re.compile(r'//concat\.lietou-static\.com/fe-h2-pc/v6/js/polyfill-vendors\..*?\.js')
PATTERN_LP_CLIENT_ID = re.compile(r'__FE_CLIENT_ID="(\d+)"')

TEMP_LP_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    # "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
    # "Content-Length": ,
    "Content-Type": "application/x-www-form-urlencoded",
    "Host": "api-h.liepin.com",
    "Origin": "https://h.liepin.com",
    "Referer": "https://h.liepin.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "X-Client-Type": "web",
    "X-Fscp-Bi-Stat": '{"location":"https://h.liepin.com/search/getConditionItem"}',
    "X-Fscp-Fe-Version": "",
    # "X-Fscp-Std-Info": '{"client_id": ""}',
    # "X-Fscp-Trace-Id": str(uuid.uuid4()),
    "X-Fscp-Version": "1.1",
    "X-Requested-With": "XMLHttpRequest",
    # "X-XSRF-TOKEN": cookies_name_val_dict['XSRF-TOKEN'],
    "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"'
}

TEMP_LP_SEARCH_PARAMS_INPUT_VO = {"nowDqs": "",
                                  "wantDqs": "",
                                  "onlyLatestWorkExp": "",
                                  "workYearsLow": "",
                                  "workYearsHigh": "",
                                  "graduate": False,
                                  "eduLevels": [],
                                  "eduLevelTz": False,
                                  "studyAbroad": False,
                                  "industrys": "",
                                  "nowJobTitles": "",
                                  "wantIndustry": "",
                                  "wantJobTitles": "",
                                  "userHope": "",
                                  "modifytimeType": "",
                                  "workAbroad": False,
                                  "managerial": False,
                                  "languageSkills": [],
                                  "languageContent": "",
                                  "wantSalaryLow": "",
                                  "wantSalaryHigh": "",
                                  "nowSalaryLow": "",
                                  "nowSalaryHigh": "",
                                  "sex": "",
                                  "nowCompKind": "",
                                  "resLanguage": "",
                                  "ageLow": "",
                                  "ageHigh": "",
                                  "filterViewed": False,
                                  "filterChat": False,
                                  "filterDownload": False,
                                  "resumetype": "0",
                                  "sortType": "0",
                                  "skId": "",
                                  "fkId": "",
                                  "searchType": "0",
                                  # "curPage": 0,
                                  "pageSize": "",
                                  "keyword": "",
                                  "anyKeyword": "0",
                                  "jobName": "",
                                  "jobPeriod": "0",
                                  "compName": "",
                                  "compPeriod": "0",
                                  "school": "",
                                  "major": "",
                                  "version": "",
                                  "schoolKindList": [],
                                  "eduLevelTzCode": "",
                                  "activeStatus": "",
                                  "pushId": "",
                                  "csId": "",
                                  "jobStability": ""}

# TEMP_PAYLOAD_LP_SEARCH_RESUMES = {
#     'searchParamsInputVo': {"nowDqs": "",
#                             "wantDqs": "",
#                             "onlyLatestWorkExp": "",
#                             "workYearsLow": "",
#                             "workYearsHigh": "",
#                             "graduate": False,
#                             "eduLevels": [],
#                             "eduLevelTz": False,
#                             "studyAbroad": False,
#                             "industrys": "",
#                             "nowJobTitles": "",
#                             "wantIndustry": "",
#                             "wantJobTitles": "",
#                             "userHope": "",
#                             "modifytimeType": "",
#                             "workAbroad": False,
#                             "managerial": False,
#                             "languageSkills": [],
#                             "languageContent": "",
#                             "wantSalaryLow": "",
#                             "wantSalaryHigh": "",
#                             "nowSalaryLow": "",
#                             "nowSalaryHigh": "",
#                             "sex": "",
#                             "nowCompKind": "",
#                             "resLanguage": "",
#                             "ageLow": "",
#                             "ageHigh": "",
#                             "filterViewed": False,
#                             "filterChat": False,
#                             "filterDownload": False,
#                             "resumetype": "0",
#                             "sortType": "0",
#                             "skId": "",
#                             "fkId": "",
#                             "searchType": "0",
#                             # "curPage": 0,
#                             "pageSize": "",
#                             "keyword": "",
#                             "anyKeyword": "0",
#                             "jobName": "",
#                             "jobPeriod": "0",
#                             "compName": "",
#                             "compPeriod": "0",
#                             "school": "",
#                             "major": "",
#                             "version": "",
#                             "schoolKindList": [],
#                             "eduLevelTzCode": "",
#                             "activeStatus": "",
#                             "pushId": "",
#                             "csId": "",
#                             "jobStability": ""},
#     # 'logForm': {"ckId": str(uuid.uuid4()), "skId": '', "fkId": '', "searchScene": "refresh"},
#     'version': 'V5'
# }

TEMP_LP_HEADERS_HOME = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "zh-CN,zh;q=0.9",
    "sec-ch-ua": "\"Chromium\";v=\"142\", \"Google Chrome\";v=\"142\", \"Not_A Brand\";v=\"99\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1"
}
