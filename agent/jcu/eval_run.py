"""M1 决策质量 A/B：systemone(diffusiongemma) vs GLM 直选，比准确率与延迟。

用法：cd agent && python -m jcu.eval_run
这是方案的 go/no-go 关口：若 diffusiongemma 准确率显著低于 GLM，
则决策原语只保留低价值高频场景，或切官方 Jev 后端再测。
"""

import json
import time
from pathlib import Path
from typing import Callable, List

from .config import build_llm
from .decision import DecisionEngine, build_decision_engine

DATA_PATH = Path(__file__).parent / "eval_data.json"


def glm_pick(llm, item: dict) -> str:
    prompt = (
        f"界面状态：{item['state']}\n问题：{item['question']}\n"
        "候选：\n" + "\n".join(f"- {o}" for o in item["options"])
        + "\n最合适的选项是（只输出该选项原文）："
    )
    text = llm.chat("你是选择器。只输出一个选项的原文，不要任何其他文字。", prompt)
    pick = text.strip().strip("。\"'“”")
    return pick if pick in item["options"] else "<invalid>"


def run_engine(name: str, decide: Callable[[dict], str], items: List[dict]) -> None:
    correct, latencies = 0, []
    for item in items:
        t0 = time.perf_counter()
        try:
            got = decide(item)
        except Exception as exc:  # 单条失败不中断评测，记为错误
            got = f"<error: {exc}>"
        latencies.append(time.perf_counter() - t0)
        if got == item["answer"]:
            correct += 1
        else:
            print(f"  [{name}] {item['id']} 误选 {got!r}（应为 {item['answer']!r}）")
    avg_ms = sum(latencies) / len(latencies) * 1000
    print(f"{name}: 准确率 {correct}/{len(items)}，平均延迟 {avg_ms:.0f}ms")


def main() -> None:
    items = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    zh = [it for it in items if it.get("lang") == "zh"]
    engine: DecisionEngine = build_decision_engine()
    llm = build_llm()

    print(f"评测集：{len(items)} 条（中文 {len(zh)} 条 / 英文 {len(items) - len(zh)} 条）")
    run_engine(type(engine).__name__,
               lambda it: engine.choose(state=it["state"], question=it["question"],
                                        options=it["options"]).choice,
               items)
    run_engine("GLM直选", lambda it: glm_pick(llm, it), items)
    run_engine(type(engine).__name__ + "-中文子集",
               lambda it: engine.choose(state=it["state"], question=it["question"],
                                        options=it["options"]).choice,
               zh)


if __name__ == "__main__":
    main()
