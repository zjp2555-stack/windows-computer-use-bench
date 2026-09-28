# Jev 风格组合架构 Computer Use 实施方案

**日期**：2026-09-24
**前置结论**（见 `out/research-report.md`）：Jev 不能独立承担截图式 computer use（无图像输入、无坐标输出、不生成文本）；唯一现实路径是「界面文本快照 → Jev 风格单步决策 → 专用代码执行」组合架构，本方案即实施该架构。

## 一、目标与范围

**目标**：在 Windows 上搭建组合架构的桌面 computer use agent（demo → 内部工具级），并量化"决策原语"环节相对纯 LLM 决策的延迟/成本收益。

**范围内**：控件暴露良好的标准桌面应用（表单、设置界面、记事本、资源管理器、常规 Win32/UWP 应用）；单步任务与 ≤15 步的多步任务；中文与英文界面。

**范围外**：视觉密集任务（图表、画布、GPU 渲染窗口——UIA/OCR 均不可靠）；生产级部署；浏览器内自动化（后续可参考 Stagehand 思路扩展）。

## 二、总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent 主循环（≤15 步）                   │
│                                                             │
│  ① 感知                     ② 规划（宿主 LLM：智谱 GLM）     │
│  pywinauto UIA 树    ──▶    读任务+快照，生成 3~10 个        │
│  → 编号文本快照              下一步动作候选（含自由文本）      │
│  @e3 [Button] "确定"              │                         │
│                                   ▼                         │
│  ④ 执行                     ③ 决策（Jev 风格原语）           │
│  pywinauto 键鼠操作   ◀──    systemone Choice 从候选中       │
│  （默认 dry-run）             选一个，带 confidence          │
│         │                    confidence < 阈值              │
│         │                    → 回退 GLM 直选                 │
│         ▼                                                 │
│    动作 done/stop 或步数用尽 → 结束                           │
└─────────────────────────────────────────────────────────────┘
```

分工要点：**感知、规划、执行、文本生成全部由传统组件/GLM 承担，决策原语只做一件事——在高频单步"从候选中选一个"上提速降本**（参考实测：Stagehand Act 延迟 1.97s→0.46s）。

## 三、技术选型与理由

| 环节 | 选型 | 理由 |
|------|------|------|
| 决策原语 | 硅基流动 `POST /v1/systemone`，模型 `diffusiongemma`（Alpha，2026-10-08 前免费） | 国内直连、当前免费、接口形态与 TypeSafe/Jev 对口；官方 Jev 适配器同步预留，可一键切换 |
| 宿主 LLM | 智谱开放平台 GLM（OpenAI 兼容 `chat/completions`） | 已选定；负责候选生成、自由文本产出、低置信回退决策 |
| 感知 | pywinauto（UIA backend） | Windows 自带无障碍树，无需截图，正好绕开 Jev 无图像输入的限制 |
| 执行 | pywinauto `click_input`/`type_keys` + pyautogui（滚动/热键） | 成熟稳定，dry-run 易实现 |
| 语言 | Python 3.10+ | pywinauto/pyautogui 生态最全 |

## 四、关键设计

1. **决策适配器（双后端）**：`DecisionEngine` 接口只有 `choose(state, question, options) -> (choice, confidence)`；`siliconflow` 与 `typesafe` 两个实现按 `DECISION_BACKEND` 切换。注意字段命名差异（官方 `noul`，硅基流动 `noui`；Alpha schema 可能调整，以冒烟实测为准）。
2. **255 选项上限**：三层缓解——快照元素数封顶（`max_elements=200`）、候选数上限（默认 12）、复杂界面按 `scope` 关键字分域后再决策。
3. **置信度门控回退**：`confidence < 0.6`（可配）时改由 GLM 直选；连续回退视为任务异常，停止并报告。
4. **安全边界**：执行器默认 `dry-run`（只打印动作不真执行）；动作白名单（click/type/scroll/hotkey/done/stop）；步数上限；正式执行前先在记事本等无害应用上验证。
5. **CJK 风险前置**：评测集专门含中文条目，M1 就量化 diffusiongemma 中文决策质量（中文平台托管的复现，可能优于官方 Jev 的 CJK 表现，但必须实测）。

## 五、API 与配置清单

需要两个密钥（放 `agent/.env`，从 `.env.example` 复制）：

| 变量 | 用途 | 获取方式 |
|------|------|---------|
| `SILICONFLOW_API_KEY` | systemone 决策原语（diffusiongemma） | siliconflow.cn 控制台 |
| `ZHIPU_API_KEY` | GLM 宿主 LLM | open.bigmodel.cn 控制台 |

> 注意：ZCode 的 GLM 编程套餐凭据不能用于脚本直连，需在智谱开放平台单独创建 API key；`ZHIPU_MODEL` 填账号可用模型（如 glm-4.6 或 glm-5.x）。

其余配置：`DECISION_BACKEND`、`CONFIDENCE_THRESHOLD`、`EXEC_DRY_RUN`、`MAX_CANDIDATES`、`MAX_STEPS`（均有默认值）。

## 六、里程碑

| 阶段 | 内容 | 完成标准 |
|------|------|---------|
| **M0 冒烟验证** | 两条 API 各打一次，确认鉴权、配额、实际返回 schema（Alpha 可能与文档有出入） | `python -m jcu.smoke_test` 两段输出均有效，记录 schema 差异 |
| **M1 决策质量 A/B** | 12+ 条决策评测集（中英混合），diffusiongemma vs GLM 直选，比准确率/延迟/成本 | 评测脚本产出对比表；这是 go/no-go 关口：若 diffusiongemma 准确率显著低于 GLM，仅保留其低价值高频场景 |
| **M2 感知与执行链路** | UIA 快照（编号元素表）+ 执行器 dry-run | 记事本/计算器/设置 3 个应用快照完整可用，dry-run 动作序列正确 |
| **M3 单步闭环** | 真实执行单步任务（先关 dry-run 白名单应用） | 10 个单步任务 ≥8 成功 |
| **M4 多步任务循环** | ≤15 步任务，含置信度回退与停止条件 | 5 个多步任务 ≥3 完成，回退率、步数、延迟有记录 |
| **M5 中文专项 + 压力** | 中文界面快照、>255 控件分域、长循环稳定性 | 中文子集成功率不低于英文子集 10 个百分点以内；分域策略验证通过 |

## 七、评估方案

- **指标**：任务成功率、单步决策延迟（decision 路径 vs llm-fallback 路径 vs 纯 GLM 基线）、token 成本估算、低置信回退率。
- **基线**：同一快照与执行器下，决策环节也交给 GLM 的纯 LLM agent。
- **任务集**：M1 用静态决策题（`jcu/eval_data.json`）；M3 起用真实桌面任务清单（记事本输入保存、设置页开关、计算器多步运算等）。

## 八、风险与对策

| 风险 | 对策 |
|------|------|
| 硅基流动 Alpha 停用/收费（2026-10-08 后） | 适配器双后端，切官方 Jev 或其他 System One 复现只改配置 |
| diffusiongemma 决策质量未知 | M1 为 go/no-go 关口，先量化再深入 |
| CJK 准确度 | M1/M5 中文子集专项；低置信门控兜底 |
| GPU 渲染窗口 UIA 抓不到 | 明确不在范围；遇此类窗口记为"不可用"并跳过 |
| 误操作风险 | 默认 dry-run；先无害应用；动作白名单 + 步数上限 |
| 官方 Jev 未来开放图像输入 | 触发整体架构重评（快照→截图驱动） |

## 九、目录结构

```
agent/
  .env.example          # 密钥与开关模板
  requirements.txt
  README.md             # 上手步骤
  jcu/
    config.py           # 环境变量配置
    http_util.py        # 带 host 校验的 HTTP 工具
    decision/           # 决策原语适配器（siliconflow / typesafe）
    llm/zhipu.py        # GLM 宿主 LLM 客户端
    perception/uia.py   # UIA 文本快照
    planner.py          # 候选生成（GLM）
    executor.py         # 动作执行（默认 dry-run）
    loop.py             # Agent 主循环
    smoke_test.py       # M0 冒烟
    eval_run.py         # M1 A/B 评测
    eval_data.json      # 评测题集
```
