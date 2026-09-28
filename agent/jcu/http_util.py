"""对外 HTTP 工具：仅允许 http/https，且拒绝指向环回/内网/保留地址的目标。

唯一例外：HTTP_ALLOW_FAKE_IP=true 时放行 198.18.0.0/15——本机代理
（Clash/mihomo 等）开启 fake-ip DNS 模式时，所有域名都会解析进该段，
由代理隧道转发到真实主机，并非真正的内网地址。
"""

import ipaddress
import os
import socket
from urllib.parse import urlparse

import requests

_TIMEOUT_S = 60
_FAKE_IP_RANGE = ipaddress.ip_network("198.18.0.0/15")


def _allow_fake_ip() -> bool:
    return os.getenv("HTTP_ALLOW_FAKE_IP", "false").strip().lower() == "true"


def _assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"仅允许 http/https 协议: {url}")
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"无法解析主机: {host}") from exc
    allow_fake = _allow_fake_ip()
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if allow_fake and addr.version == 4 and addr in _FAKE_IP_RANGE:
            continue
        if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local:
            raise ValueError(f"拒绝访问环回/内网/保留地址: {host} ({addr})")


def post_json(url: str, headers: dict, payload: dict) -> dict:
    _assert_public_http_url(url)
    resp = requests.post(url, headers=headers, json=payload, timeout=_TIMEOUT_S)
    if resp.status_code >= 400:
        # 带上响应体再抛错，否则 4xx 的具体原因（如参数校验信息）会被吞掉
        raise RuntimeError(f"HTTP {resp.status_code} {url}: {resp.text[:500]}")
    return resp.json()
