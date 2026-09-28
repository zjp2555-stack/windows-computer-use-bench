# JCU-Bench v1 报告：jev-computer-use MCP vs ZCode 原生 computer use

日期：2026-09-28 凌晨。

> 更名备注：文中 MCP 当时注册名为 `jev-computer-use`，2026-09-28 定名 `decide-computer-use`
> （工具前缀 `mcp__decide-computer-use__typesafe_*`，中性命名不绑定模型/厂商），引擎本质与数据不受影响。任务集：上游 `benchmarks/GeneralFixture.exe` 8 族 × seed 0（development 分区），
每族两引擎各跑一次、族序交替先后。评分只认 fixture 独立评估器 `result.json`（协议全文见
`benchmarks/bench-jev/protocol.md`，原始数据 `benchmarks/bench-jev/results.jsonl`，21 行含作废行）。

## 一句话结论

**成功率打平（7/8 vs 7/8），但失败点完全正交**：MCP 在「开着的 Win32 窗口内的封闭控件操作」上
单步 1.5-2.9s、基本免视觉 token、能自己点掉模态对话框；原生 SDK 感知面更广（虚拟化列表的离屏项
直接在 UIA 树里）且动作即时（交互期中位数 0.6s），但**helper 遇模态 MessageBox 直接 UIA 挂死且
会话无法原地恢复**。与 2026-09-27 三方调研的「正交、混合体」结论一致，这次是实测数据支撑。

## 主表（seed 0，成功判定=评估器；裁决规则见下）

| 族 | MCP 结果 | MCP 交互秒* | native 结果 | native 交互秒* |
|---|---|---|---|---|
| form | ✅ | 14.9 | ✅ | 1.35 |
| long-list | ✅（补丁后，见 §失败剖析） | 3.03 | ✅ | 0.31 |
| menu-dialog | ✅ | 2.65 | ✅ | 0.65 |
| grid | ❌ ComboBox 脱轨 | — | ✅ | 0.64 |
| text-editor | ✅ | 2.51 | ✅ | 0.31 |
| dynamic | ✅ | 3.83 | ✅（计时被排障污染） | 39.0† |
| ocr-visual | ✅（OCR 读卡→打字） | 3.46 | ✅（视觉读卡） | 0.31 |
| recovery | ✅（含自主点对话框 OK） | 6.91 | ❌（裁决失败，见下） | — |
| **合计** | **7/8 = 87.5%**（补丁前 6/8） | 成功均值 5.3s | **7/8 = 87.5%** | 干净 6 例均值 0.59s |

\* 交互秒 = fixture 记录的「首次 UI 动作→提交」，不含引擎启动与宿主应答等待。
† native dynamic 的 39s 含我方 window_id 重绑排障，非引擎固有开销；干净固有开销约 1-2s。

## 裁决规则（对成功率的两组修正）

- **mcp long-list 首跑崩溃**（offscreen 41 选项超硅基流动 26 上限）计失败并保留记录；打补丁后
  重跑成功，主表按补丁后计（当前引擎真实能力），崩溃作为工程发现单列。
- **native recovery 裁决失败**：引擎只完成 bind/观察/点 Start；模态确认框让 helper 三类调用全部
  「响应丢失」（与本机已知 UWP UIA 挂起同类），stop() 后会话无法重启，余下步骤由外部 Win32
  PostMessage 兜底完成（评估器本身记 success）。工具性失败与 MCP 崩溃对称计入失败档。
- 另有 3 行作废：2 次用户在机器前手动点掉弹窗/关窗（按干扰作废重跑）、1 次 0 动作前台被抢
  （干扰重跑），全部留痕在 results.jsonl。

## 两个失败剖析（各自暴露的根能力差异）

1. **mcp long-list 崩溃 → 已修**：ListBox 55 项虚拟化，引擎把全部 41 个离屏控件塞进一个 Choice
   问题，超过硅基流动 SystemOne 单问题 26 项上限直接 ValueError。补丁（decide.py）：
   offscreen 问题按「目标命名优先、其余按阅读序」截断到 max_options()，**保留原始 screen.offscreen
   索引为键**（actions.press_offscreen 按它索引执行）。补丁后 diffusiongemma 1.00 直选目标
   [32]；实际链路是 offscreen 拒绝→滚动×2→点击目标→确认。192 单测全绿。
2. **mcp grid 脱轨**：Select Poyraz 落地（事件双发），但点 Priority 下拉后前台丢失、引擎抓到
   任务栏、自停 "nothing helps"。ComboBox 弹出层是 MCP 的感知盲区。
3. **native recovery 挂死**：与 MCP 恰好互补——MCP 引擎 2.2s 内自己点了「确定」（OCR+控件树
   都能看到对话框），原生 SDK 的 get_app_state 却对同一对话框永久挂起。

## 效率与成本画像

- **引擎内单步**：MCP capture 0.05-0.72s / OCR 0.08-0.2s / decide 0.68-1.27s / act 0.1-6.5s
  （act 大值是 accessibility 写长文本，如 text-editor 4.5s、ocr-visual 6.5s）；单步均值 1.5-2.9s。
  native 的元素动作本身亚秒级，但每次观察调用带 10-30s 的 settle 等待（dynamic/recovery 中实测 30s）。
- **整案墙钟**：MCP run.json seconds 45-111s（含 1-2 次宿主应答往返；宿主每轮思考 10-30s 是大头）；
  native 每案 2-4 个 cell + 我的轮次，量级相近但更依赖驾驶者盯着。
- **视觉 token**：本基准除 ocr-visual 外两引擎都可纯 UIA 文本完成。MCP 全程零截图进决策（决策模型
  只看文本快照）；native 只在 ocr-visual 用了一张截图。fixture 是 UIA 友好的 WinForms，这一点
  对双方都有利，不构成偏向。

## 特征互补总结（指导 jev 后续路由）

- MCP 甜点区实测成立：已开窗口 + 控件树 + 操作性指令 → 7/8 且全程自主（宿主只答填什么+终局确认）。
- MCP 两个待修点：按压校验滞后（"press did not take" 误报导致 3 次冗余点击的假象反复出现，
  建议校验窗口加宽或按事件流判定）；ComboBox 下拉层脱轨。
- native 的挂死类缺陷（模态对话框）是会话级的，无法原地恢复，比 MCP 的崩溃更伤——MCP 崩溃
  是进程级 fail-fast 且本次已修复。
- 上限观察：两者成功率同为 7/8，谁的短板先补上谁先到 8/8；真正的多样性收益在混合路由
  （简单一步→native 直操作；多步控制密集→MCP 自主跑；模态对话框→只交给 MCP）。

## 威胁效度

单 seed（development 0），N=8 族，统计功效弱；用户在机器前造成 3 次干扰（已作废重跑）；两引擎
的驾驶者同为 GLM-5.3-Flash（ native 是我直接驾驶，MCP 的宿主应答也是我），宿主延迟计入双方；
fixture UIA 暴露充分，对纯视觉路线（如 Codex CUA）不公平，不能据此外推到视觉型对手。

## 复跑

```
powershell -NoProfile -ExecutionPolicy Bypass -File benchmarks\Build.ps1
cd benchmarks\bench-jev
python start_case.py mcp form 0        # 启动 fixture 并打印 goal（mcp/native 交替）
# mcp: typesafe_run(goal, windowTitle=case.json 标题, act=true, steps=10-12) + typesafe_respond 应答
# native: agent.computerUse.getApp({pid}) → getAXState → 按 index 动作 → 复核 SUCCESS 标签
python record.py <engine> <family> 0 <outdir> key=value...   # 读 result.json 追加结果行
taskkill /F /IM GeneralFixture.exe     # 每案结束后清理
```


---

# JCU-Bench v2：三引擎 × seed 0-2（2026-09-28 晚）

v2 新增 hybrid 引擎（路由技能 + 已补丁 MCP + native，定义与预注册路由见 protocol.md「v2 扩展」节），
seed 1-2 与 seed 0 同协议。MCP 已更名 `decide`（前缀 `mcp__decide__typesafe_*`）。

## 总分（每引擎 24 案 = 8 族 × 3 seeds，成功=fixture 评估器，裁决规则同 v1）

| 引擎 | 成功率 | 交互秒（成功案均值） | 失败点 |
|---|---|---|---|
| **hybrid** | **16/16 = 100%**（seed1 8/8，seed2 8/8） | **1.7s** | 无 |
| mcp（decide） | 23/24 = 95.8%（7/8, 8/8, 8/8） | ~5.4s | 仅 seed0 grid（ComboBox 脱轨，seed 1-2 同族通过——判定为偶发非系统性） |
| native | 21/24 = 87.5%（三个 seed 全是 7/8） | 0.3-0.8s（干净案亚秒级） | recovery 三连败：模态 MessageBox 让 helper 确定性挂死（**N=3，每次全新 helper 复现**） |

## 关键结论

1. **混合路由完胜且零失败**：hybrid 用 native 的速度（1.7s vs mcp 5.4s）拿到 mcp 的覆盖面（模态框只交 MCP）。
   路由分布（16 案）：native-batch 12（form/long-list/menu-dialog/grid/text-editor/dynamic 各 2）、
   mcp-ocr 2（ocr-visual）、mcp-modal 2（recovery）。路由表一次都没有判错过。
2. **native 的模态挂死是确定性缺陷**：seed 0/1/2 三次、每次都是刚启动的全新 helper 进程，点开
   MessageBox 后 get_app_state 必然「响应丢失」。修复路径明确（modality-aware capture 或对话框窗口
   直绑绕过），但在修之前 recovery 族对 native 就是 0%。
3. **mcp 的 ComboBox 失败 seed 1-2 未复现**（连过 2 次）——v1 的 grid 脱轨更像偶发前台竞争而非
   系统性盲区；但 mcp 的「校验滞后误报 + 成功后漫游」（成功后继续空点烧完步数）每个 seed 都在，
   是效率问题不是成败问题。
4. **mcp 全程零视觉 token**（24 案只靠 OCR 文本 + UIA）；native 的 ocr-visual 每案需要 1 张截图进视觉。

## 分族明细（✓=评估器 success）

| 族 | mcp 0/1/2 | native 0/1/2 | hybrid 1/2 |
|---|---|---|---|
| form | ✓✓✓ | ✓✓✓ | ✓✓ |
| long-list | ✓(补丁)✓✓ | ✓✓✓ | ✓✓ |
| menu-dialog | ✓✓✓ | ✓✓✓ | ✓✓ |
| grid | ✗✓✓ | ✓✓✓ | ✓✓ |
| text-editor | ✓✓✓ | ✓✓✓ | ✓✓ |
| dynamic | ✓✓✓ | ✓✓✓ | ✓✓ |
| ocr-visual | ✓✓✓ | ✓✓✓ | ✓✓(MCP) |
| recovery | ✓✓✓ | ✗✗✗ | ✓✓(MCP) |

## v2 过程事件（全部留痕 results.jsonl）

- native recovery 三次挂死均按 bounded-attempt 协议处置（不再调 stop() 杀会话；杀 fixture 让挂起调用
  随窗口消亡，helper 自愈，**会话无需重启**——这是 v1 教训的修正，三次挂死后 native 腿继续跑完了全部
  其余各族）。
- mcp ocr-visual seed2 首跑被用户活动抢前台（0 动作，interference 作废重跑成功）。
- hybrid menu-dialog seed2 命中一次已知的 WinForms「点击后 capture 误绑按钮 HWND」怪癖，按既定
  教训 list_windows 重固定主窗核实，无额外代价（evaluator success）。

## 效度边界

- hybrid 的 N=16（v2 新引擎无 seed0 数据，不回填——v1 期间尚无路由技能，回填会造成幸存者偏差）；
  mcp/native 的 N=24。
- 三引擎的驾驶员/宿主同为 GLM-5.3：native 与 hybrid 由主代理驾驶（含全部 v1/v2 教训），mcp 决策是
  diffusiongemma、宿主应答也是主代理——hybrid 的分数包含「学过的教训」成分，这正是"改进后的混合
  computer use"的定义，但意味着不能解读为纯架构优势。
- 同一 fixture 全 UIA 友好（WinForms），对纯视觉路线仍不公平；模态框缺陷是否 WinForms-MessageBox
  特有未测（WPF/QQ NT 等待真实任务验证）。
