"""动作执行器。默认 dry-run 只打印不真执行；动作白名单外的动作一律拒绝。"""

import json
from typing import Dict

from .perception.uia import Element

ALLOWED_ACTIONS = {"click", "type", "scroll", "hotkey", "done", "stop"}


def _resolve_target(action: dict, elem_map: Dict[str, Element]) -> Element:
    target = str(action.get("target") or "").lstrip("@")
    elem = elem_map.get(target)
    if elem is None:
        raise ValueError("动作目标 @" + target + " 不在当前快照中")
    return elem


def run_action(action: dict, elem_map: Dict[str, Element], dry_run: bool = True) -> bool:
    """执行一个动作，返回是否为终止动作（done/stop）。"""
    kind = str(action.get("action") or "")
    if kind not in ALLOWED_ACTIONS:
        raise ValueError("动作不在白名单: " + kind)

    if dry_run:
        print("  [dry-run] " + json.dumps(action, ensure_ascii=False))
        return kind in ("done", "stop")

    if kind == "click":
        _resolve_target(action, elem_map).ctrl.click_input()
    elif kind == "type":
        elem = _resolve_target(action, elem_map)
        elem.ctrl.set_focus()
        elem.ctrl.type_keys(str(action.get("text") or ""), with_space=True)
    elif kind == "scroll":
        import pyautogui

        pyautogui.scroll(int(action.get("amount", -300)))
    elif kind == "hotkey":
        import pyautogui

        keys = action.get("keys") or []
        if not keys:
            raise ValueError("hotkey 动作缺少 keys")
        pyautogui.hotkey(*[str(k) for k in keys])
    return kind in ("done", "stop")
