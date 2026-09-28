# ruff: noqa: RUF001 - the Chinese punctuation in the probe strings is intentional
"""Smoke test the domestic backends with real API calls: SiliconFlow decision (single / batch / Noul-mapped) and the GLM writer.

Run from the repo root:  .venv/Scripts/python.exe smoke_cn_backends.py
Reads SILICONFLOW_API_KEY / ZHIPU_API_KEY from .env; prints answers only, never keys.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from typesafe_computer_use.config import load_dotenv
from typesafe_computer_use.decision_backends import SiliconFlowClient
from typesafe_computer_use.zhipu_writer import ZhipuWriter

load_dotenv(Path(__file__).parent / ".env")


def show(label: str, response) -> None:
    fallback = f"  (fallback: {response.fallback_reason})" if response.fallback_reason else ""
    print(f"[{label}] fallback={bool(response.fallback_reason)}{fallback}")
    print(
        f"  raw answers: {json.dumps((response.raw.get('answers') if isinstance(response.raw, dict) else response.raw) or {}, ensure_ascii=False)[:300]}"
    )
    for key, answer in response.answers.items():
        extra = f" noul={answer.noul}" if answer.noul is not None else ""
        print(f"  {key}: choice={answer.choice!r} confidence={answer.confidence}{extra}")


def main() -> int:
    ok = True

    print("== 1. SiliconFlow single choice (string state, dict question) ==")
    client = SiliconFlowClient(api_key=__import__("os").environ.get("SILICONFLOW_API_KEY", ""))
    response = client.system_one(
        state="任务：关闭当前的记事本窗口。界面：一个记事本窗口，右上角有关闭按钮。",
        questions={
            "next_action": {
                "type": "choice",
                "instructions": "哪个动作最符合任务目标？",
                "criteria": {"o0": "点击右上角的关闭按钮", "o1": "按 Alt+F4 关闭窗口", "o2": "最小化窗口"},
            }
        },
    )
    show("single", response)
    ok &= response.answers["next_action"].choice in {"o0", "o1", "o2"}

    print("== 2. SiliconFlow multi-question batch (dict state, like decide.py sends) ==")
    state = {
        "goal": "关闭当前的记事本窗口",
        "frontmost_app": "记事本",
        "screen_items_in_reading_order": [{"i": 1, "text": "关闭", "role": "button"}],
    }
    response = client.system_one(
        state=state,
        questions={
            "kind": {
                "type": "choice",
                "instructions": "Which kind of action makes the most progress toward the goal right now?",
                "criteria": {"click_item": "Click one of the on-screen items.", "none": "Nothing helps."},
            },
            "item": {
                "type": "choice",
                "instructions": "If clicking an on-screen item is the right move, which item?",
                "criteria": {"1": "the 关闭 button"},
            },
        },
    )
    show("batch", response)
    ok &= "kind" in response.answers and "item" in response.answers

    print("== 3. SiliconFlow Noul question (mapped to a true/false Choice) ==")
    from typesafe_sdk import Noul

    response = client.system_one(
        state={
            "goal": "在记事本里输入 hello world",
            "field": "edit: 文本编辑区",
            "text_typed": "hello world",
            "field_value_now": "hello world",
            "field_still_focused": True,
        },
        questions={"ok": Noul(instructions="Did the typing succeed: does the field now contain the typed text?")},
    )
    show("noul", response)
    noul = response.answers["ok"].noul
    ok &= noul is not None and 0.0 <= noul <= 1.0

    print("== 4. GLM writer structured call (compose_text shape) ==")
    writer = ZhipuWriter()
    reply = writer.structured(
        system=(
            "You fill in one text field on a user's screen. Decide the exact string to type. "
            "Never invent credentials, passwords, or personal data."
        ),
        packet={"goal": "在记事本里输入 hello world", "focused_field": "edit: 无标题 文本编辑区", "text_near_field": []},
        properties={"fill": {"type": "boolean"}, "text": {"type": "string"}, "reason": {"type": "string"}},
    )
    print(f"  reply: {json.dumps(reply, ensure_ascii=False)[:300]}")
    ok &= isinstance(reply.get("fill"), bool) and "text" in reply

    print(f"\nSMOKE {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
