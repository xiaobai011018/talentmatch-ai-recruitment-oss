#!/usr/bin/env python3
"""Capture Maimai XHR/fetch diagnostics without storing credentials or response bodies."""

from __future__ import annotations

import argparse
import base64
import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service


TARGET_PATHS = (
    '/api/ent/talent/basic',
    '/contact/comment_list/',
)
CAPTURE_RESOURCE_TYPES = {'XHR', 'Fetch'}
MAX_CAPTURED_REQUESTS = 500
ERROR_KEYS = (
    'result', 'code', 'error_code', 'status', 'message', 'msg', 'reason', 'error', 'detail',
)
PHONE_PATTERN = re.compile(r'(?<!\d)(?:\+?86[\s-]*)?1[3-9](?:[\s-]*\d){9}(?!\d)')
WECHAT_PATTERN = re.compile(
    r'((?:微信号\s*[:：]?\s*|(?:微信|[Vv][Xx]|[Ww]e[Cc]hat)(?:\s*[:：]\s*|\s+)))'
    r'([A-Za-z0-9][A-Za-z0-9._-]{2,})'
)
SECRET_PATTERN = re.compile(
    r'(?i)((?:trackable_token|access_token|csrf(?:_token)?|csrftoken|cookie|session)'
    r'\s*[:=]\s*)[^,\s;&]+'
)
LONG_ID_PATTERN = re.compile(r'(?<!\d)(\d{6,})(?!\d)')
CONTACT_UID_PATTERN = re.compile(r'(/contact/comment_list/)(\d+)')


def safe_text(value, limit=300):
    if isinstance(value, (dict, list, tuple, set)):
        return f'<{type(value).__name__}>'
    text = str(value)
    text = PHONE_PATTERN.sub('[REDACTED_PHONE]', text)
    text = WECHAT_PATTERN.sub(lambda match: f'{match.group(1)}[REDACTED_WECHAT]', text)
    text = SECRET_PATTERN.sub(r'\1[REDACTED]', text)
    text = LONG_ID_PATTERN.sub(lambda match: f'***{match.group(1)[-4:]}', text)
    return text.replace('\r', ' ').replace('\n', ' ')[:limit]


def sanitize_url(url):
    parsed = urlsplit(url)
    path = CONTACT_UID_PATTERN.sub(
        lambda match: f'{match.group(1)}***{match.group(2)[-4:]}',
        parsed.path,
    )
    return {
        'origin_and_path': f'{parsed.scheme}://{parsed.netloc}{path}',
        'query_parameter_names': sorted({key for key, _ in parse_qsl(parsed.query)}),
    }


def summarize_body(body, base64_encoded=False):
    if base64_encoded:
        try:
            body = base64.b64decode(body).decode('utf-8', errors='replace')
        except Exception:
            return {'body_length': 0, 'payload_type': 'unreadable_base64'}

    summary = {'body_length': len(body or '')}
    try:
        payload = json.loads(body)
    except Exception:
        summary['payload_type'] = 'non_json'
        return summary

    summary['payload_type'] = type(payload).__name__
    if not isinstance(payload, dict):
        return summary

    summary['top_level_keys'] = sorted(map(str, payload.keys()))
    summary['has_data'] = 'data' in payload
    summary['data_type'] = type(payload.get('data')).__name__ if 'data' in payload else None
    summary['data_present'] = bool(payload.get('data'))
    summary['error_fields'] = {
        key: safe_text(payload[key])
        for key in ERROR_KEYS
        if payload.get(key) is not None
    }
    return summary


def is_target_url(url):
    return any(path in url for path in TARGET_PATHS)


def is_maimai_url(url):
    hostname = (urlsplit(url).hostname or '').lower()
    return hostname == 'maimai.cn' or hostname.endswith('.maimai.cn')


def selenium_cookie(cookie):
    result = {
        'name': cookie['name'],
        'value': cookie['value'],
        'path': cookie.get('path') or '/',
    }
    domain = cookie.get('domain')
    if domain:
        result['domain'] = domain
    if cookie.get('secure') is not None:
        result['secure'] = bool(cookie['secure'])
    if cookie.get('httpOnly') is not None:
        result['httpOnly'] = bool(cookie['httpOnly'])

    expiry = cookie.get('expirationDate', cookie.get('expiry'))
    if isinstance(expiry, (int, float)) and expiry > time.time():
        result['expiry'] = int(expiry)

    same_site = str(cookie.get('sameSite') or '').lower()
    same_site_map = {
        'strict': 'Strict',
        'lax': 'Lax',
        'none': 'None',
        'no_restriction': 'None',
    }
    if same_site in same_site_map:
        result['sameSite'] = same_site_map[same_site]
    return result


class NetworkCapture:
    def __init__(self, driver):
        self.driver = driver
        self.requests = {}
        self.browser_errors = []

    def poll(self):
        for entry in self.driver.get_log('performance'):
            try:
                message = json.loads(entry['message'])['message']
                self._handle(message)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        self._poll_browser_errors()

    def _poll_browser_errors(self):
        try:
            entries = self.driver.get_log('browser')
        except WebDriverException:
            return
        for entry in entries:
            level = str(entry.get('level') or '').upper()
            if level not in {'SEVERE', 'WARNING'}:
                continue
            self.browser_errors.append({
                'level': level,
                'source': safe_text(entry.get('source') or 'unknown', limit=80),
                'message': safe_text(entry.get('message') or '', limit=500),
            })

    def _handle(self, message):
        method = message.get('method')
        params = message.get('params') or {}
        request_id = params.get('requestId')

        if method == 'Network.requestWillBeSent':
            request = params.get('request') or {}
            url = request.get('url') or ''
            resource_type = params.get('type')
            if (
                not is_maimai_url(url)
                or resource_type not in CAPTURE_RESOURCE_TYPES
                or (
                    request_id not in self.requests
                    and len(self.requests) >= MAX_CAPTURED_REQUESTS
                )
            ):
                return
            self.requests[request_id] = {
                'request': {
                    **sanitize_url(url),
                    'method': request.get('method'),
                    'resource_type': resource_type,
                    'matches_legacy_resume_path': is_target_url(url),
                    'header_names': sorted(map(str, (request.get('headers') or {}).keys())),
                },
                'response': None,
            }
            return

        if method == 'Network.responseReceived':
            response = params.get('response') or {}
            url = response.get('url') or ''
            resource_type = params.get('type')
            if (
                request_id not in self.requests
                and is_maimai_url(url)
                and resource_type in CAPTURE_RESOURCE_TYPES
                and len(self.requests) < MAX_CAPTURED_REQUESTS
            ):
                self.requests[request_id] = {
                    'request': {
                        **sanitize_url(url),
                        'method': None,
                        'resource_type': resource_type,
                        'matches_legacy_resume_path': is_target_url(url),
                        'header_names': [],
                    },
                    'response': None,
                }
            if request_id in self.requests:
                self.requests[request_id]['response'] = {
                    'http_status': response.get('status'),
                    'mime_type': response.get('mimeType'),
                    'header_names': sorted(map(str, (response.get('headers') or {}).keys())),
                }
            return

        if method == 'Network.loadingFinished' and request_id in self.requests:
            try:
                body_result = self.driver.execute_cdp_cmd(
                    'Network.getResponseBody', {'requestId': request_id})
                body_summary = summarize_body(
                    body_result.get('body', ''),
                    base64_encoded=bool(body_result.get('base64Encoded')),
                )
            except WebDriverException as exc:
                body_summary = {
                    'payload_type': 'unavailable',
                    'error_type': type(exc).__name__,
                }
            response = self.requests[request_id].setdefault('response', {})
            response['body_summary'] = body_summary

    def report(self):
        try:
            current_url = sanitize_url(self.driver.current_url)
            window_count = len(self.driver.window_handles)
        except WebDriverException:
            current_url = None
            window_count = None
        return {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'privacy': {
                'cookie_values_saved': False,
                'header_values_saved': False,
                'query_values_saved': False,
                'response_bodies_saved': False,
            },
            'page_state': {
                'current_url': current_url,
                'window_count': window_count,
            },
            'browser_errors': self.browser_errors,
            'captured_requests': list(self.requests.values()),
        }


def load_cookies(path):
    payload = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError('Cookie 文件必须是 JSON 数组')
    return payload


def build_driver():
    options = webdriver.ChromeOptions()
    options.set_capability('goog:loggingPrefs', {
        'performance': 'ALL',
        'browser': 'ALL',
    })
    return webdriver.Chrome(service=Service(), options=options)


def inject_cookies(driver, cookies):
    driver.get('https://maimai.cn/')
    imported = 0
    skipped = 0
    for cookie in cookies:
        try:
            driver.add_cookie(selenium_cookie(cookie))
            imported += 1
        except (KeyError, WebDriverException):
            skipped += 1
    return imported, skipped


def parse_args():
    parser = argparse.ArgumentParser(description='脱敏捕获脉脉简历相关网络请求')
    parser.add_argument('--cookie-file', type=Path, required=True, help='Chrome Cookie JSON 文件')
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('tmp/maimai-network-diagnostic.json'),
        help='脱敏报告输出路径',
    )
    parser.add_argument(
        '--start-url',
        default='https://maimai.cn/chat?fr=ent&in_iframe=1&scene=talent_bank',
        help='Cookie 导入后打开的脉脉页面',
    )
    parser.add_argument('--timeout', type=int, default=300, help='最长捕获秒数')
    return parser.parse_args()


def main():
    args = parse_args()
    cookies = load_cookies(args.cookie_file)
    driver = build_driver()
    capture = NetworkCapture(driver)
    stop_event = threading.Event()
    report = None

    try:
        driver.execute_cdp_cmd('Network.enable', {})
        imported, skipped = inject_cookies(driver, cookies)
        driver.get(args.start_url)
        capture.poll()

        print(f'已导入 {imported} 条 Cookie，跳过 {skipped} 条。')
        print('请在 Chrome 中打开候选人简历；操作完成后回到终端按 Enter。')

        def wait_for_enter():
            try:
                input()
            finally:
                stop_event.set()

        threading.Thread(target=wait_for_enter, daemon=True).start()
        deadline = time.time() + max(1, args.timeout)
        while not stop_event.is_set() and time.time() < deadline:
            capture.poll()
            time.sleep(0.5)
        capture.poll()
        report = capture.report()
    finally:
        driver.quit()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'已捕获 {len(report["captured_requests"])} 条脉脉 XHR/Fetch 请求。')
    print(f'浏览器警告/错误 {len(report["browser_errors"])} 条。')
    print(f'脱敏报告：{args.output.resolve()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
