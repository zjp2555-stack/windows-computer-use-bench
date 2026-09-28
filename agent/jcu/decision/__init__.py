from .base import ChoiceDecision, DecisionEngine
from .siliconflow import SiliconFlowSystemOne
from .typesafe import TypesafeJev

__all__ = ["ChoiceDecision", "DecisionEngine", "SiliconFlowSystemOne", "TypesafeJev", "build_decision_engine"]


def build_decision_engine() -> DecisionEngine:
    """按 DECISION_BACKEND 构造决策原语后端，密钥缺失时给出明确报错。"""
    from ..config import _require, settings

    if settings.decision_backend == "typesafe":
        return TypesafeJev(_require("TYPESAFE_API_KEY"))
    return SiliconFlowSystemOne(_require("SILICONFLOW_API_KEY"))
