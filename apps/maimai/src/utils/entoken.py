"""
@describe: 脉脉反自动化签名（X-ENT-TOKEN）纯 Python 复刻
@fileName: entoken.py
@time    : 2026/8/19
@author  : duke

脉脉 v41 把招聘接口从 /api/ent/* 迁到 /sdk/jobs/anti_automation/*，
并加上了 ECDSA 反自动化签名。本模块复刻前端 crypto.subtle 的签名流程：

1. 生成 ECDSA P-256 密钥对，导出 SPKI 公钥（base64）
2. POST /sdk/jobs/security/register_pubkey 注册公钥 -> 换取 kid
3. 构造 payload {v:2, ts, exp, fp, rid, kid} -> base64url
4. 用私钥对 payload 做 ECDSA-SHA256 签名（原始 r||s）-> base64url
5. token = "<payload>.<signature>"，随请求头发送 X-ENT-TOKEN / X-ENT-FP / X-ENT-RID
"""
import base64
import hashlib
import json
import re
import threading
import time
import uuid

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from src.config.http import HTTP_TIME_OUT_MM
from src.config.maimai import (
    API_MM_REGISTER_PUBKEY,
    MM_ENTOKEN_TTL_MS,
    MM_MAIN_SCRIPT_HASH,
)

# 反自动化接口的 Referer
ENTOKEN_REFERER = 'https://maimai.cn/ent/v41/recruit/talents?tab=1'

# 从页面 <script src="...main.XXXX.bundles.js"> 提取当前前端 bundle hash
_MAIN_SCRIPT_HASH_PATTERN = re.compile(r'main\.([0-9a-z]+)\.bundles\.js')


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


class EntokenSigner:
    """负责注册公钥换取 kid，并为每个请求生成 X-ENT-TOKEN 签名。"""

    def __init__(self, uid, cookies_dict, base_headers, main_script_hash=None):
        self.uid = uid
        self.cookies_dict = cookies_dict
        self.base_headers = base_headers
        self.main_script_hash = main_script_hash or MM_MAIN_SCRIPT_HASH
        # 稳定的设备指纹（服务端不严格校验，只作设备标识）
        self.fp = hashlib.sha256(f'mm-entoken-v1|{uid}'.encode()).hexdigest()[:32]
        self._keypair = None  # (private_key, kid)
        self._lock = threading.Lock()

    def _fetch_main_script_hash(self):
        """从 talents 页动态取当前前端 bundle hash，失败回退到配置常量。"""
        try:
            headers = dict(self.base_headers)
            headers['Referer'] = ENTOKEN_REFERER
            resp = requests.get(
                ENTOKEN_REFERER,
                headers=headers,
                cookies=self.cookies_dict,
                timeout=HTTP_TIME_OUT_MM,
            )
            match = _MAIN_SCRIPT_HASH_PATTERN.search(resp.text)
            if match:
                return match.group(1)
        except Exception:
            pass
        return self.main_script_hash

    def register(self):
        """生成密钥、注册公钥、缓存 (private_key, kid)。"""
        key = ec.generate_private_key(ec.SECP256R1())
        spki = key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        headers = dict(self.base_headers)
        headers['Content-Type'] = 'application/json'
        resp = requests.post(
            API_MM_REGISTER_PUBKEY,
            headers=headers,
            cookies=self.cookies_dict,
            params={
                'u': self.uid,
                'uid': self.uid,
                'main_script_hash': self._fetch_main_script_hash(),
            },
            data=json.dumps({'pubkey': base64.b64encode(spki).decode()}),
            timeout=HTTP_TIME_OUT_MM,
        )
        data = resp.json()
        kid = data.get('kid')
        if not kid:
            raise RuntimeError(f'register_pubkey 未返回 kid: {data}')
        with self._lock:
            self._keypair = (key, kid)
        return data

    def _ensure_registered(self):
        if not self._keypair:
            self.register()

    def signed_headers(self, referer=None):
        """返回带 X-ENT-TOKEN / X-ENT-FP / X-ENT-RID 的请求头副本。"""
        self._ensure_registered()
        with self._lock:
            key, kid = self._keypair

        ts = int(time.time() * 1000)
        rid = str(uuid.uuid4())
        payload = {
            'v': 2,
            'ts': ts,
            'exp': ts + MM_ENTOKEN_TTL_MS,
            'fp': self.fp,
            'rid': rid,
            'kid': kid,
        }
        signed_str = _b64url(json.dumps(payload, separators=(',', ':')).encode())
        der_sig = key.sign(signed_str.encode(), ec.ECDSA(hashes.SHA256()))
        r_int, s_int = decode_dss_signature(der_sig)
        raw_sig = r_int.to_bytes(32, 'big') + s_int.to_bytes(32, 'big')

        headers = dict(self.base_headers)
        headers['Referer'] = referer or ENTOKEN_REFERER
        headers['Accept'] = 'application/json, text/plain, */*'
        headers['X-ENT-TOKEN'] = f'{signed_str}.{_b64url(raw_sig)}'
        headers['X-ENT-FP'] = self.fp
        headers['X-ENT-RID'] = rid
        return headers
