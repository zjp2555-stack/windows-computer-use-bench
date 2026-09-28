# JCU-Bench v1：jev-computer-use MCP vs ZCode 原生 computer use

> 注：MCP 注册名沿革（2026-09-28，用户指示，中性命名不绑定任何模型/厂商）：
> `jev-computer-use` → `decide` → 最终定名 **`decide-computer-use`**（工具前缀 `mcp__decide-computer-use__typesafe_*`）。
> 本文件与 v1/v2 报告中的历史记录保留当时名称；数据不受影响。

日期：2026-09-27 夜。任务集：上游 `benchmarks/GeneralFixture.exe` 全部 8 族（form / long-list /
menu-dialog / grid / text-editor / dynamic / ocr-visual / recovery），seed 0（development 分区）。

## v2 扩展（2026-09-28）：三引擎 × 后续 seed

- 引擎增加 **hybrid**：宿主按 `.zcode/skills/hybrid-computer-use/SKILL.md` 路由规则实测执行，
  允许使用全部已学教训（window_id 固定、快速应答等）。「改进后的混合 computer use」= 路由技能 +
  已打补丁的 MCP + 操作经验。
- hybrid 预注册路由策略（跑前写下，防事后挑路线）：
  1. 宿主启动并置前 fixture（与另两引擎相同）；
  2. 至多一次 native getAXState 预观察分类：预期/出现模态框路径 → 整窗流程交 MCP；
     目标仅存在于 OCR 文本（ax 树无该控件）→ 交 MCP（免视觉 token）；
     全部所需控件单树可见且 ≤6 个简单动作 → native 批量执行（1-2 cell）；
  3. 失败即换路由：native 出现响应丢失征兆 → 本案剩余步骤交 MCP；MCP none/nothing-helps →
     宿主/native 接手该步；每案换路由至多一次（环境干扰除外）。
- 预注册各族预期路由：form/long-list/menu-dialog/grid/text-editor/dynamic → native 批量
  （dynamic 用 window_id 固定主窗）；ocr-visual → MCP（OCR 文本路径）；recovery → MCP（模态框）。
  实际执行时仍须逐案观察验证路由条件，不符则按策略改道并记录。
- seed 计划：development 分区 1-4（0 已跑），视会话余量递进；同族三引擎按
  (族序号 + seed) mod 3 轮转先后以平衡热身效应；干扰作废行照旧保留并标注。
- v2 判分口径不变：只认 fixture 评估器 result.json；工具性失败（挂死/崩溃/脱轨）计失败档，
  环境干扰作废不计入引擎成败但保留记录。


## 引擎定义

- **mcp**：`mcp__jev-computer-use__typesafe_run`（vendored typesafe 移植版）。
  diffusiongemma（硅基流动 SystemOne）决策 + ZCode 宿主即 writer（CLICKER_HOST_DIR 路径）。
  参数：act=true, steps=12, delay=0.4, minConfidence=0.4, windowTitle=case.json 中的标题。
- **native**：ZCode 内置 computer use（agent.computerUse SDK），由主代理直接驾驶
  （getApp → getAXState → 按 index click/setValue/pressKey → 复核）。

## 评分标准（协议沿用上游 benchmarks/README.md）

1. **主指标 SR（成功率）**：只认 fixture 独立评估器 `result.json` 的 `success:true`，
   引擎自报的 goal_achieved 不作为判分依据。
2. **交互耗时**：`result.json.interactionSeconds`（fixture 侧记录：首次 UI 动作 → 完成），跨引擎可比。
3. **UI 动作数**：`result.json.actions`（fixture 记录的实际 UI 突变次数）。
4. **引擎开销**：MCP 看 run.json（steps_taken / seconds / timing 分解 capture-ocr-ax-decide-act /
   宿主应答轮数）；native 看本次会话 node_repl cell 数与动作数。
5. **稳定性**：validationErrors、abort、重试次数、外部干扰，全部如实记录，失败/中断计入分母不剔除。

## 公平性协议

- 每次运行全新 fixture 进程 + 全新输出目录，绝不复用。
- 同族两引擎交替先后（族序号偶数 native 先，奇数 mcp 先）以平衡热身效应。
- MCP 引擎收到的 goal 一字不改来自 case.json；native 同样读 case.json 的 goal 执行。
- 成功只认 result.json + 最终状态标签复核（"SUCCESS — independently verified"）。
- 分区纪律：seed 0-4 development，5-7 regression，8-9 holdout；本次只用 development seed 0。

## 已知边界（解读分数时必须带上）

- MCP 动作空间封闭（click/scroll/type/enter/escape/wait/offscreen/use_browser/done/none），
  无组合热键、无拖拽、无开应用——8 族全部在其空间内，属其设计甜点区；
- long-list 55 项超过感知预算（SILIFLOW_MAX_OPTIONS=24），检验 offscreen 通道；
- ComboBox DropDownList 弹出层是否可被 MCP 感知，未验证，属基准要回答的问题。
