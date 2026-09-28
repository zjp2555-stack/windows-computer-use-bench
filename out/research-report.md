# Jev 用于 Computer Use 项目可行性调研报告

**日期**：2026-09-24　**依据**：三路调研（模型考据、项目扫描、行业基准）+ 逐条独立事实核查。

## 一、结论先行（可行性与置信度）

**以「Jev 作为操控模型」独立承担 computer use 任务，当前（2026-09）不可行。置信度：高。**

三条架构级硬限制（均经官方文档原文独立抽查核实）：

1. **无图像输入通道**：官方明文 "Images, audio, and video are not supported (yet)"，截图驱动路线被直接排除，且为架构限制而非工程可绕过；
2. **输出不含坐标、不生成自然语言或动作序列**：输出仅为 Choice/Score/Noul 类型化决策，无法产出 click(x,y)/type/scroll 式操作，连表单自由文本都无法生成；
3. **Choice 单次上限 255 个选项**，官方定位 System One 单步决策、自述不擅间接推理，长时程规划（OSWorld 2.0 任务平均超 250 步）须由外部循环或宿主 LLM 承担。

实测方 Browserbase 直接结论："Will Jev build production grade computer use agents? No."、"Jev is a piece of the pie but not a standalone solution"。

**有条件的替代路径**：若问题改为「computer use 项目中能否引入 Jev 作决策组件」，答案为**有条件可行**——社区已跑通「OCR/UIA 文本快照 → Jev 单步选动作 → 专用代码执行」组合架构（Callstack 移动 QA、kofanlabs Windows 表单、Browserbase Stagehand 三例），但均为 demo/fixture 级，无生产级部署。

**置信度说明**：核心否定性事实来自官方文档直读并经独立抽查核实；仅 OSWorld/ScreenSpot-Pro 榜单 JS 动态部分未完全读取，不影响架构级结论。官方留了 "(yet)" 口子，一旦开放图像输入，结论需整体重评。

## 二、Jev 模型是什么

- **身份**：TypeSafe AI（前 OpenAI 研究员 Diogo Almeida 创办，部分英文报道拼作 Diego）2026-09-15 发布的首个 "System One"（系统一）决策模型，09-21 开放注册，目前 early access。
- **定位**：软件内嵌的高速分类/决策（工单路由、内容审核、风险分类），自称比 LLM 快 193.6 倍、便宜 444.6 倍、零幻觉；**不是**对话/生成模型，不聊天、不写代码、不生成自然语言。官方 Doom demo 明确基于结构化状态而非图像。
- **可用性**：仅官方闭源 API：`POST https://api.typesafe.ai/v1/systemone`，Bearer 认证，密钥从 console.typesafe.ai/keys 获取；无官方开放权重。HuggingFace 有第三方 "Jev 形" 复现，中文社区"0.4B/2.37GB 本地运行"即指此类复现/克隆，**非官方本体**。
- **规格**：输入为文本 state + 结构化 questions（noul/choice/score）；输出为带概率与置信度的类型化决策、score、noul 0–1；模型 ID jev-latest（当前 jev-1.13.0），参数量未公布；定价 $0.042/M 输入 tokens（$42/十亿，输出免费）；训练方法 RLCD，非自回归架构。上下文 64k tokens（state+最长问题预算 32k）与速率 250k tokens/s、1200 req/min 均为**第三方规格页数据，未见官方原文**。
- **能力边界自述**（jev-1.13，2026-09-17）：擅长常识/语义判断，计数/数学/日期/间接推理不可靠，不生成文本；全文无视觉/GUI 能力描述。
- **语言**：以英文为主训练，官方自述 CJK 准确度较低。

## 三、相关项目盘点

**直接以 Jev 做 GUI 操作的项目（仅三例，均实验级）：**

1. **Callstack agent-device + jevil**（移动 QA，iOS/Android 等）：Jev 读 agent-device 的文本可访问性快照（如 `@e4 [button] "Add to cart"`），用 choice() 选动作 ID，agent-device 执行，循环至 pass/fail；配套 CLI 仓库 callstackincubator/jevil。README 警告大屏幕可能超 255 选项需 `--scope`，文字输入须预置。官方自称 demo / proof of concept。
2. **Browserbase Stagehand**（浏览器自动化）：Act 循环中 Jev 做指令→动作分类与候选元素选择，执行仍由 Stagehand 完成，中位延迟 1.97s→0.46s（约 4.3 倍）。结论 "Jev is not very good as a standalone agent"、"even the best demos aren't ready to be deployed to production"。独立核查发现其 Jev 支持 PR 当时标注 experimental 且尚未合并。
3. **kofanlabs**（Windows）：OCR + UI Automation 把窗口转文本控件 → Jev 选 operation+target → 专用代码执行；fixture 级表单填写 5.5 秒；实测 PrintWindow 对 GPU 渲染窗口可能失败。**注：独立核查时中英文检索均未定位到该项目，此例无法独立核实。**

**生态接入**：LangChain 官方集成 langchain-typesafe（TypeSafeClassifier 封装三类原语为 Runnable，可配 ModelRouterMiddleware 做路由），适合把 Jev 嵌入 agent 循环做决策子步骤。

**可作组合底座的框架**（Jev 至多替换其中决策子步骤，不能当操控模型）：Browser Use（v1.44+ 改用 LiteLLM，支持 250+ provider）、Agent-S（截图驱动双模型架构，grounding 模型可换 UI-TARS-1.5-7B）、UI-TARS-desktop（Claude 3.7 规划 + UI-TARS 视觉接地）、CogAgent-9B（开源 GUI agent，图像→动作/坐标；**GLM-PC 产品形态未单独核实**）、OpenAdapt（记录回放式自动化）、Anthropic computer use tool（schema 内置于 Claude，自选模型需自建 agent loop 与键鼠执行）。其中 agent-device 已验证可与 Jev 组合，是 Jev「看界面」的唯一现实方式（**文本而非截图**）。

## 四、行业做法与能力要求

- **能力支柱**（据 OSWorld 2.0/WAA 官方页与 ScreenSpot-Pro 论文）：截图 grounding（ScreenSpot-Pro 2025 年发布时最高约 18.9%，2026 年前沿约 85-92%）、动作空间（click(x,y)/type/scroll/hotkey 或结构化控件操作）、多步规划（OSWorld 2.0 共 108 个长时程任务、平均超 250 步、上限 500 步）。
- **输入两派**：纯截图（Operator/Claude computer use）vs 截图+无障碍树混合（Set-of-Marks）；WAA 官方页指出 UIA 树+OmniParser 配置显著更好。
- **2026-09 榜单快照**（**聚合站/搜索摘要，非官方直读**）：OSWorld 2.0/Verified 上 GPT-6 Astra 72.6%、Claude Opus 5 70.6%；官网直读严格 binary 口径仅 Claude Opus 4.8 20.6% 最优——口径差异极大；人类参考约 72-75%。
- **代表模型**：闭源 GPT-6 Astra、Claude Opus 5；开源 UI-TARS、Agent-S、Qwen-VL 系、CogAgent、UGround。
- **新趋势**：System One 单步快决策 + System Two LLM 规划，与社区用 Jev 的方式吻合。
- **对操控模型的四项本质要求**：视觉-语言对齐、坐标输出、超长程规划与错误恢复、跨应用状态追踪——全部超出 Jev 当前公开能力范围。
- **Jev 无公开 computer use 基准成绩**：OSWorld 2.0/WindowsAgentArena/ScreenSpot-Pro 官网均无 Jev/TypeSafe 条目（**榜单表格 JS 动态加载，仅读到静态文本，无法 100% 排除**）；官方博客明言不放标准基准表格，仅内部 4-workflow 基准 67.8%（DataCamp 报道，非 computer use）。

## 五、关键事实核查表

| # | 主张 | 核实状态 | 核查要点 |
|---|------|---------|---------|
| 1 | 仅接受文本/结构化输入，图像、音频、视频 not supported (yet) | ✅ 已证实 | 官方 state.md 原文逐字核实；flaviocopes.com 等多第三方交叉一致；无相反证据 |
| 2 | 输出仅为 Choice/Score/Noul 类型化决策，不含坐标、不生成自然语言/动作序列 | ✅ 已证实 | 官方 primitives 各页 + llms.txt 全站索引（70+ 页无 GUI/坐标/grounding 页面）。细微修正：Noul 无单独 confidence 字段（0-1 值本身即概率），原措辞轻微不精确，不影响结论 |
| 3 | Browserbase 直接结论：用 Jev 建不成生产级 computer use agent，只是拼图一块 | ✅ 已证实 | 四句引文经 webReader 无缓存抓取全文逐字确认，WebFetch 二次独立抓取一致 |
| 4 | 组合路线仅达 demo/fixture 级，无生产级部署 | ✅ 已证实 | Callstack 自称 proof of concept；Stagehand PR 标 experimental 且未合并；主动寻找生产级反例（中英文）失败。"唯一"的全称表述无法穷举证明；kofanlabs 一例无法独立核实 |
| 5 | Choice 上限 255 选项；不能生成任意字符串，自由文本须预置候选 | ✅ 已证实 | 官方博客 "cardinality up to 255" + choice 原语页 + Callstack 原文交叉核实。jevil README 的 --scope 细节因重名干扰未能独立定位，不影响主张 |
| 6 | 英文为主训练，官方自述 CJK 准确度较低 | ✅ 已证实 | 官方 state.md Note 与 models 页 Language support 双入口独立核实；36氪/搜狐/知乎第三方佐证 |

六条主张全部独立查证证实，未见翻转性证据。

## 六、风险与未覆盖项

**风险**：① CJK 准确度较低且本机为中文环境，中文界面 OCR 文本喂入效果需额外实测；② 替代路线丢像素级信息，视觉密集任务（图表、画布、布局）做不了，且 OCR/UIA 依赖应用暴露控件，kofanlabs 实测 GPU 渲染窗口抓屏失败、真实网站未充分验证；③ 长时程规划须由外部循环或宿主 LLM 承担；④ 复杂界面须先分域（--scope）；⑤ 无第三方背书，效果只能自建任务实测并做 A/B（Jev vs 前沿模型单步决策质量与成本）；⑥ 官方 "(yet)" 口子意味着若开放图像输入，整个评估需重做。

**未覆盖项**：本调研未运行任何本地代码或基准（early access 仅 API，无官方 SDK/权重），全部结论基于网页读取与搜索；OSWorld/ScreenSpot-Pro 榜单 JS 动态部分未完全读取；kofanlabs 项目独立核查未检索到；GLM-PC 产品形态未单独核实（仅核实同源 CogAgent）；未找到 Jev 在 OSWorld 等基准的成绩、Jev 的 OpenAI 兼容 chat API、以及上述三例之外用 Jev 做 GUI 的项目；中文搜索因服务限流（429）部分未完成，事实核查以英文检索为主（官方文档+第三方全文+多来源摘要已构成独立佐证）。
