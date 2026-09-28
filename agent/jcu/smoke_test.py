"""M0 冒烟测试：各调用一次 GLM 与 systemone 决策接口，确认鉴权与实际返回 schema。

用法：cd agent && python -m jcu.smoke_test
"""

import json
import time

from .config import _require, build_llm, settings
from .decision import build_decision_engine


def main() -> None:
    llm = build_llm()
    t0 = time.perf_counter()
    reply = llm.chat("你是冒烟测试助手。", "请只回复两个字：OK")
    print(f"[GLM {settings.zhipu_model}] {time.perf_counter() - t0:.2f}s -> {reply!r}")

    engine = build_decision_engine()
    t0 = time.perf_counter()
    decision = engine.choose(
        state="屏幕上有一个对话框，按钮：保存 / 不保存 / 取消。用户想放弃未保存的修改。",
        question="应点击哪个按钮？",
        options=["保存", "不保存", "取消"],
    )
    print(
        f"[{type(engine).__name__} {time.perf_counter() - t0:.2f}s] "
        f"choice={decision.choice!r} confidence={decision.confidence}"
    )
    print("原始返回（核对 Alpha schema 是否与文档一致）：")
    print(json.dumps(decision.raw, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _ = _require  # 密钥缺失时由各构建函数给出明确报错
    main()
