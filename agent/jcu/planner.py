"""候选生成（宿主 LLM 职责之一）：读任务与快照，产出下一步动作候选。

Jev 类模型不能生成自由文本，所以所有 text（要输入的内容）都由 GLM 在候选里预置好，
决策模型只做选择——这是组合架构的关键分工。
"""

import json
from typing import List

from .llm.zhipu import ZhipuChat

SYSTEM_PROMPT = (
    "你是 Windows 桌面任务的下一步动作规划器。给定任务与界面元素快照"
    '（每行形如 @e3 [Button] "确定"），生成 3-10 个互不相同的下一步动作候选，'
    "覆盖最可能推进任务的动作，并保留必要的保守选项（done/stop）。"
    '每个候选是 JSON 对象：{"action":"click|type|scroll|hotkey|done|stop",'
    '"target":"@eID","text":"要输入的文本","label":"不超过15字的动作描述"}；'
    "click/type 必须带 target（取快照中存在的 @eID）；type 必须带 text；"
    "done 表示任务已完成，stop 表示无法继续。只输出 JSON 数组，不要任何其他文字。"
)

MAX_SNAPSHOT_LINES = 200  # 喂给 GLM 的快照行数上限


def build_state(task: str, lines: List[str]) -> str:
    return "任务：" + task + "\n\n界面元素快照：\n" + "\n".join(lines[:MAX_SNAPSHOT_LINES])


def _extract_json_array(text: str) -> list:
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        raise ValueError(f"LLM 未返回 JSON 数组: {text[:200]}")
    return json.loads(text[start:end + 1])


def generate_candidates(llm: ZhipuChat, task: str, lines: List[str],
                        k: int = 12, max_retries: int = 2) -> List[dict]:
    last_error: Exception = ValueError("未重试")
    for _ in range(max_retries):
        try:
            text = llm.chat(SYSTEM_PROMPT, build_state(task, lines))
            candidates, seen = [], set()
            for cand in _extract_json_array(text)[:k]:
                label = str(cand.get("label") or cand.get("action") or "")[:30]
                if not label or label in seen:
                    continue
                seen.add(label)
                cand["label"] = label
                candidates.append(cand)
            if candidates:
                return candidates
            last_error = ValueError("候选为空")
        except Exception as exc:  # JSON 解析失败等，重试一次
            last_error = exc
    raise RuntimeError(f"候选生成失败: {last_error}")


def fallback_pick(llm: ZhipuChat, task: str, lines: List[str], options: List[str]) -> str:
    """低置信回退：让 GLM 直接从候选里选一个，返回选项原文。"""
    prompt = (
        build_state(task, lines)
        + "\n\n候选动作：\n"
        + "\n".join(f"- {opt}" for opt in options)
        + "\n\n最符合任务目标的动作是（只输出该选项原文）："
    )
    text = llm.chat("你是动作选择器。只输出一个选项的原文，不要任何其他文字。", prompt)
    pick = text.strip().strip("。\"'“”")
    return pick if pick in options else options[0]
