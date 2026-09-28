"""决策原语的统一接口：组合架构中 Jev 风格模型只负责"从候选中选一个"。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class ChoiceDecision:
    """一次 Choice 决策的结果。

    choice 为所选选项原文；confidence 低于配置阈值时主循环回退 GLM 直选；
    raw 保留后端原始返回，便于排查 Alpha 阶段的 schema 差异。
    """

    choice: str = ""
    confidence: float = 0.0
    raw: dict = field(default_factory=dict)


class DecisionEngine(ABC):
    """所有 systemone 类后端共有的单步选择接口。"""

    @abstractmethod
    def choose(self, state: str, question: str, options: List[str]) -> ChoiceDecision:
        """从 options（≤255 项、互不重复）中选一个并给出置信度。"""
        raise NotImplementedError
