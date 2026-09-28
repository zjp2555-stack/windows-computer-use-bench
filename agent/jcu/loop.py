"""Agent 主循环：快照 → 候选 → 决策（低置信回退 GLM）→ 执行，直到 done/stop 或步数用尽。"""

from typing import Optional

from . import executor, planner
from .config import settings
from .decision import DecisionEngine, build_decision_engine
from .llm.zhipu import ZhipuChat
from .perception import uia

MAX_FALLBACK_STREAK = 3  # 连续低置信回退达到该值即判定任务异常，停止


def run_task(task: str, title_re: str = ".*", scope: Optional[str] = None,
             process: Optional[int] = None,
             engine: Optional[DecisionEngine] = None, llm: Optional[ZhipuChat] = None) -> bool:
    """执行一个桌面任务，返回任务是否以 done 结束。

    title_re 按窗口标题定位目标；标题不可靠时可改传 process（目标进程号）。
    """
    from .config import build_llm

    engine = engine or build_decision_engine()
    llm = llm or build_llm()
    elem_map = {}
    fallback_streak = 0

    for step in range(1, settings.max_steps + 1):
        elements = uia.snapshot(title_re=title_re, scope=scope, process=process)
        elem_map = {e.eid: e for e in elements}
        lines = [e.to_line() for e in elements]

        candidates = planner.generate_candidates(llm, task, lines, k=settings.max_candidates)
        by_label = {c["label"]: c for c in candidates}
        options = list(by_label.keys())

        if len(options) == 1:
            chosen, source = candidates[0], "single-candidate"
        else:
            try:
                decision = engine.choose(
                    state=planner.build_state(task, lines),
                    question="哪个动作最符合任务目标？",
                    options=options,
                )
            except Exception as exc:
                # Alpha 后端存在瞬时故障（如 503 过载）：视同决策不可用，走 GLM 回退；
                # 属基础设施问题，不计入"任务异常"连续回退计数
                print(f"  决策后端异常（{exc}），回退 GLM 直选")
                decision = None
            if decision is not None and decision.confidence >= settings.confidence_threshold:
                chosen = by_label.get(decision.choice, candidates[0])
                source = "decision(conf=%.2f)" % decision.confidence
            else:
                conf_note = "err" if decision is None else "conf=%.2f" % decision.confidence
                label = planner.fallback_pick(llm, task, lines, options)
                chosen = by_label.get(label, candidates[0])
                source = "llm-fallback(%s)" % conf_note
                if decision is not None:
                    fallback_streak += 1
                    if fallback_streak >= MAX_FALLBACK_STREAK:
                        print(f"[step {step}] 连续 {fallback_streak} 步低置信回退，判定任务异常，停止")
                        return False

        print(f"[step {step}] {source}: {chosen.get('label')}")
        terminal = executor.run_action(chosen, elem_map, dry_run=settings.exec_dry_run)
        if terminal:
            return chosen.get("action") == "done"

    print(f"达到最大步数 {settings.max_steps}，任务未声明完成")
    return False
