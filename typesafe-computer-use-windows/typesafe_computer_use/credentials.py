"""Provider setup; reuse the locally encrypted key, never persist plaintext."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def prepare_provider():
    if os.environ.get("TYPESAFE_API_KEY"):
        return
    if os.environ.get("AI_GATEWAY_API_KEY"):
        os.environ["TYPESAFE_API_KEY"] = os.environ["AI_GATEWAY_API_KEY"]
        os.environ.setdefault("TYPESAFE_BASE_URL", "https://ai-gateway.vercel.sh/typesafe")
        os.environ.setdefault("TYPESAFE_DEFAULT_MODEL", "typesafe-ai/jev")
        return
    if sys.platform != "win32":
        return
    original = Path(__file__).resolve().parents[1]
    config = original / "config/provider.json"
    if not config.exists():
        return
    provider = json.loads(config.read_text(encoding="utf-8-sig"))["provider"]
    if provider not in ("vercel", "typesafe"):
        raise ValueError("Unknown locally configured provider")
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(original / "scripts/Read-Key.ps1"),
            "-Provider",
            provider,
        ],
        capture_output=True,
        text=True,
        timeout=10,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        raise RuntimeError("Cannot decrypt the local API key under this Windows account")
    key = result.stdout.strip()
    if len(key) < 20:
        raise RuntimeError("No valid local API key")
    os.environ["TYPESAFE_API_KEY"] = key
    if provider == "vercel":
        os.environ.setdefault("TYPESAFE_BASE_URL", "https://ai-gateway.vercel.sh/typesafe")
        os.environ.setdefault("TYPESAFE_DEFAULT_MODEL", "typesafe-ai/jev")
