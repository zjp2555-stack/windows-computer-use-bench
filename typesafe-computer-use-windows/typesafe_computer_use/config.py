"""Tunables, the site catalog, and environment loading."""

from __future__ import annotations

import os
from pathlib import Path

MIN_OCR_CONFIDENCE = 0.3
MAX_OPTIONS = 255  # TypeSafe Choice ceiling
ABORT_CORNER_PX = 4
DEFAULT_MIN_CONFIDENCE = 0.4
DEFAULT_STEPS = 100
DEFAULT_DELAY = 2.0
DEFAULT_DECISION_BACKEND = "siliconflow"  # siliconflow (diffusiongemma) | typesafe; see decision_backends
DEFAULT_WRITER_MODEL = "glm-4.6"
DEFAULT_ANSWER_MODEL = "glm-4.6v"  # runs once per run, on a screenshot: worth a vision reader
DEFAULT_BROWSER = "Google Chrome"

# Sites the classifier can pick by name. Anything else goes through the writer.
SITES: dict[str, str] = {
    "github": "https://github.com/",
    "gmail": "https://mail.google.com/",
    "google_calendar": "https://calendar.google.com/",
    "launchdarkly": "https://app.launchdarkly.com/",
    "linear": "https://linear.app/",
    "notion": "https://www.notion.so/",
    "slack": "https://app.slack.com/",
    "typesafe_console": "https://console.typesafe.ai/",
}


def load_dotenv(path: Path) -> None:
    """Set KEY=VALUE lines from a .env file into the environment unless already set."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def browser() -> str:
    return os.environ.get("CLICKER_BROWSER", DEFAULT_BROWSER)


def decision_backend() -> str:
    return os.environ.get("DECISION_BACKEND", DEFAULT_DECISION_BACKEND).strip().lower()


SILIFLOW_MAX_OPTIONS = 24  # SiliconFlow accepts at most 26 criteria per Choice (27+ rejected, smoke-bisected); keep headroom


def max_options() -> int:
    """The perception budget: a TypeSafe Choice takes 255; SiliconFlow takes far fewer."""
    if decision_backend() == "siliconflow":
        return int(os.environ.get("SILIFLOW_MAX_OPTIONS", SILIFLOW_MAX_OPTIONS))
    return MAX_OPTIONS


def writer_model() -> str:
    return os.environ.get("CLICKER_WRITER_MODEL", DEFAULT_WRITER_MODEL)


def answer_model() -> str:
    return os.environ.get("CLICKER_ANSWER_MODEL", DEFAULT_ANSWER_MODEL)


def email() -> str | None:
    return os.environ.get("CLICKER_EMAIL") or None
