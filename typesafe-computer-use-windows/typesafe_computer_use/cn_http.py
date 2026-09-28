"""Outbound JSON POST for the domestic model APIs, with an SSRF guard.

Standard library only, so the decision and writer backends carry no extra
dependency. Only http/https targets that resolve to public addresses are
allowed; loopback, private, reserved, and link-local hosts are refused.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

_FAKE_IP_RANGE = ipaddress.ip_network("198.18.0.0/15")
_RETRY_STATUS = {429, 500, 502, 503, 504}


def _allow_fake_ip() -> bool:
    """Clash/mihomo fake-ip DNS resolves every domain into 198.18.0.0/15; opt in with HTTP_ALLOW_FAKE_IP=true."""
    return os.getenv("HTTP_ALLOW_FAKE_IP", "false").strip().lower() == "true"


def _assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"only http/https is allowed: {url}")
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"cannot resolve host: {host}") from exc
    allow_fake = _allow_fake_ip()
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if allow_fake and addr.version == 4 and addr in _FAKE_IP_RANGE:
            continue
        if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local:
            raise ValueError(f"refusing loopback/private/reserved address: {host} ({addr})")


def post_json(url: str, headers: dict, payload: dict, timeout: float = 60.0, retries: int = 2) -> dict:
    """POST payload as JSON and return the decoded response. 429/5xx and connection errors retry with backoff."""
    _assert_public_http_url(url)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    attempt = 0
    while True:
        request = urllib.request.Request(url, data=body, headers={**headers, "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            # keep the response body in the error: the 4xx reason (a schema complaint, say) is otherwise lost
            error = RuntimeError(f"HTTP {exc.code} {url}: {detail}")
            if exc.code not in _RETRY_STATUS or attempt >= retries:
                raise error from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = RuntimeError(f"request to {url} failed: {exc}")
            if attempt >= retries:
                raise error from None
        attempt += 1
        time.sleep(min(0.5 * 2**attempt, 5.0))
