"""官方 TypeSafe Jev 后端（api.typesafe.ai）。与硅基流动同形实现；切换此后端时先跑冒烟核对 schema。"""

from typing import List

from ..http_util import post_json
from .base import ChoiceDecision, DecisionEngine
from .siliconflow import CHOICE_LIMIT

URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"


class TypesafeJev(DecisionEngine):
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model

    def choose(self, state: str, question: str, options: List[str]) -> ChoiceDecision:
        if len(options) > CHOICE_LIMIT:
            raise ValueError(
                f"选项数 {len(options)} 超过上限 {CHOICE_LIMIT}，请先分域或减少候选"
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
        if picked in criteria:
            label = criteria[picked]
        elif picked in options:
            label = picked
        else:
            label = ""
        conf = answer.get("confidence")
        confidence = float(conf) if conf is not None else 1.0
        return ChoiceDecision(
            choice=label or options[0],
            confidence=confidence,
            raw=data,
        )
