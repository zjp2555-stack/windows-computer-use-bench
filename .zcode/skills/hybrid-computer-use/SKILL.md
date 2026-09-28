---
name: hybrid-computer-use
description: 本工作区做原生 Windows computer use 时的混合路由规则——何时用 ZCode 内置 computer use（native）、何时交给 decide-computer-use MCP（typesafe 移植版，中性命名，曾用名 jev-computer-use，2026-09-28 更名）、如何双向交接与独立复核。依据 JCU-Bench v1 实测（2026-09-28，out/benchmark-report.md）。
---

# 混合路由：native × MCP 各守甜点区

## 接到桌面任务后的路由步骤

**第 1 步：按"第一个动作"给任务分类（不是按最终目的）。**

- 需要启动应用 / 改系统状态 / 跨应用搬运 → **宿主直接做**（shell 启动优于截图循环）。MCP 动作空间没有启动原语，永远不接这类（既有契约）。
- 纯视觉判断（看像素、读图、布局猜测）→ **native**（getScreenshot 进视觉）。
- 其余"已开窗口内的 GUI 操作" → 按第 2 步分派表。

**第 2 步：窗口内操作分派表（实测依据见文末）。**

| 任务特征 | 引擎 | 实测依据 |
|---|---|---|
| 单步点/填/滚动（1-2 个动作） | native | 元素动作亚秒级；MCP 单步 1.5-2.9s 且有编排开销 |
| 虚拟化长列表选离屏项 | native | UIA 树直接含离屏项（bounds 全 0 也有 AXPress），一次点中 |
| ComboBox / DropDownList 设值 | native `setValue` | MCP 实测点开下拉后前台丢失、抓到任务栏自停 |
| 模态对话框（MessageBox/确认框） | **只许 MCP** | native helper 对模态 UIA 挂死且会话不可恢复；MCP 实测 2.2s 自主点掉「确定」 |
| 多步控制密集流程（≥3 控件：表单/菜单+标签+提交） | MCP | 自主链路跑完，宿主只需答 1-2 次（填什么+终局确认） |
| 需要滚动定位后再确认的多步 | MCP | offscreen 拒绝→滚动→点击目标→提交的恢复链路实测有效 |
| 读屏上画的文字（验证码/卡片段）且不想进视觉 token | MCP | compose_text 宿主包带 all_screen_text（OCR 全屏文本） |
| 中文打字 | MCP 优先 | accessibility 写入，无 IME 组合串干扰 |
| 拖拽 / 组合热键 / 剪贴板 paste / 坐标点击（canvas、ax=0） | native | MCP 动作集封闭（click/scroll/type/enter/escape/wait/offscreen/use_browser/done/none） |
| Electron 应用（ZCode、QQ NT 等 UIA 树近空） | native 截图视觉，或 MCP OCR + 谨慎 | 两边 UIA 都弱，宁可宿主逐步驾驶 |

**第 3 步：按引擎各自的执行姿势跑，并以独立证据复核。**

- native：bind(pid) → getAXState → 按 index 动作 → 重新观察确认（成败以重观察/控件值/文件系统为准，不以"动作被接受"为准）。
- MCP：宿主先把目标窗口打开并置前 → `typesafe_run(goal, windowTitle, act=true, steps=10-12)` → needs_host 尽快应答（宿主思考 10-30s 是其最大中止风险源）→ 终局 `achieved` 只按屏幕实证给。

## 硬规则

1. **native 侧：动作后若预期弹模态框（MessageBox、确认框、另存为等），禁止继续 getAXState/getScreenshot**——helper 会 UIA 挂死且 stop() 后会话无法原地恢复（JCU-Bench recovery 实测）。立即转 MCP 或宿主非 UIA 手段处理。
2. **MCP 返回 none / nothing helps / low confidence：不盲试重跑。** 多半是窗口没备好或该步超出动作空间；宿主备场后给更窄的 goal，或宿主接手该步。
3. **判定 MCP 成败只认独立证据**（重观察、控件值、文件/评估器）。引擎自报 "accessibility press did not take" 是已知校验滞后误报（事件流常显示动作已落地），别当真、也别只凭它判败。
4. MCP 目标里含 ComboBox/下拉层时预期脱轨，直接改走 native。
5. 同一引擎同一路由失败一次后换路由重试，除环境干扰（用户抢焦点/关窗）外不要原地重试超过 1 次；环境干扰作废重跑要在记录里标注。

## 双向交接

- **native→MCP**：宿主 ShellExecute 启动并等 1-2s → `typesafe_windows` 取唯一标题 → `typesafe_run` 传"含最终提交动作与成功标志"的完整操作性 goal（不要拆成一次一击）→ 逐个应答 needs_host → `typesafe_wait` 到终态。goal 里写清"完成后屏幕上应出现什么"。
- **MCP→native**：run 结束（含 stalled/aborted/error）后，宿主先用 native 重观察核实屏幕实况（不信引擎的历史），再决定：残余控件 native 树里可见 → native 直操作；仍适合 MCP 的收尾 → 起一个更窄的新 goal。
- **成本直觉**：MCP 决策 ~1s/步（硅基流动 Alpha 免费额度）且不烧视觉 token，适合大批量机械步骤以省宿主上下文；native 每次观察进我的上下文，但换来即时的动作与更宽的原语。

## 依据

JCU-Bench v1（GeneralFixture 8 族 × seed 0 × 双引擎，独立评估器判分）：成功率 MCP 7/8 vs native 7/8（补丁前 MCP 6/8），失败点正交。报告 `out/benchmark-report.md`，数据 `typesafe-computer-use-windows/benchmarks/bench-jev/`。MCP offscreen 超限崩溃已修（decide.py，目标命名优先截断，保留原始索引键）。
