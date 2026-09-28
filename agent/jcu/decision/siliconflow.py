"""硅基流动 systemone 后端（diffusiongemma）。Alpha 阶段，schema 以冒烟实测为准。

请求体（据 2026-09 官方文档）：questions.<key> = {type:"choice", instructions, criteria}，
criteria 是"选项ID -> 选项描述"的对象；响应 answers.<key>.choice 返回的是选项ID。
"""

from typing import List

from ..http_util import post_json
from .base import ChoiceDecision, DecisionEngine

URL = "https://api.siliconflow.cn/v1/systemone"
DEFAULT_MODEL = "diffusiongemma"
CHOICE_LIMIT = 255  # systemone 单次 Choice 的选项上限


class SiliconFlowSystemOne(DecisionEngine):
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model

    def choose(self, state: str, question: str, options: List[str]) -> ChoiceDecision:
        if len(options) > CHOICE_LIMIT:
            raise ValueError(
                f"选项数 {len(options)} 超过上限 {CHOICE_LIMIT}，请先用 scope 分域或减少候选"
            )
        keys = [f"o{i}" for i in range(len(options))]
        criteria = dict(zip(keys, options))
        payload = {
            "model": self.model,
            "state": state,
            "questions": {
                "next_action": {
                    "type": "choice",
                    "instructions": question,
                    "criteria": criteria,
                }
            },
        }
        data = post_json(URL, {"Authorization": f"Bearer {self.api_key}"}, payload)
        answer = (data.get("answers") or {}).get("next_action") or {}
        picked = str(answer.get("choice") or "")
        # choice 返回 criteria 的键；个别实现可能直接回文本，两者都兼容
        if picked in criteria:
            label = criteria[picked]
        elif picked in options:
            label = picked
        else:
            label = ""
        # Alpha 阶段 choice 答案可能不带 confidence；缺失时按可信处理（1.0），
        # 避免主循环的置信度门控永远触发回退。冒烟时核对原始返回确认有无该字段。
        conf = answer.get("confidence")
        confidence = float(conf) if conf is not None else 1.0
        return ChoiceDecision(
            choice=label or options[0],
            confidence=confidence,
            raw=data,
        )
