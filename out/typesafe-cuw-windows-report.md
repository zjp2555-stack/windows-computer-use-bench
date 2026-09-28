# kofanlabs/typesafe-computer-use-windows 调研报告

面向 jcu 项目（大模型操控 Windows 桌面）· 2026-09-26 · 已吸收独立核实员反馈并逐条复核

> **材料与核实说明**：本报告基于三路调研材料（架构实现 / 成熟度维护 / 上游生态）写成，经独立核实员逐条复核后原位修订；全部更正点由作者在会话内亲自验证。克隆位于 `C:/Users/pc/AppData/Local/Temp/tcuw-research/repo`。
> **作者亲验记录**：`git rev-list --count HEAD`=30、`git log -5`、windows.py:156-176/303-307、actions.py:139-146、decide.py:279-289/407、perception.py:26-35、`wc -l typesafe_computer_use/*.py`=3827 行/20 个 .py、`grep -c "def test_"`=178、`git tag`=v0.2.0/0.2.1/0.2.2、`grep -rin systemone` 与 `grep "middle-right|Coldplay"` 全仓均无匹配、`gh api`（releases 三 tag、jev-ultrafast 20,439★、UFO 9,845★、上游提交 68b678e/53110f5）、jcu/planner.py:36-55、loop.py:46-63、eval_data.json=12 条、WebFetch vercel.com/ai-gateway/models/jev=$0.042/1M input。
> **未能核实项**（下文已标注）：console.typesafe.ai/keys 申请入口与「docs 无官方定价页」出自调研材料、本轮未爬取复核；183 tests 通过、5.5s/2.243s 基准、$0.0002/决策 均为上游/移植 README 自述，本机未跑 pytest 与 benchmark。
> 标注「**判断**」的段落是分析结论，其余为仓库事实或已核实的外部事实。

## 1. 项目一句话定位

awlevin/typesafe-computer-use（macOS 原版，961★）的独立 Windows 移植，给 Codex/Grok 等 MCP host agent 提供「DPI 感知 PrintWindow 截屏 + 本地 Windows.Media.Ocr + UIA 控件树」感知、Jev 决策模型驱动的原生 Windows 桌面自动化循环；自由文本与最终屏幕核验交还 MCP host（README.md:17-23）。README.md:21 自述「independent KofanLabs Windows port, not an official TypeSafe product」（作者亲验行号，更正原稿的 110-113——那是署名段）。

## 2. 架构与实现拆解

**仓库事实**。Python 3.12+ 共 3,827 行 / 20 个 .py 模块（`wc -l typesafe_computer_use/*.py` 实测，含空行与注释；更正原稿「约 3,670 行/22 模块」），另有 Node MCP 服务器（mcp.mjs 81 行）与 C# WinForms 基准夹具。依赖：uiautomation 2.0.29、6 个 winrt 投影 3.2.1、typesafe-sdk 0.6.0（pyproject.toml:22-37，亲验）。四层链路：

- **感知**：只截选中窗口，`PrintWindow(flag=2)` 失败直接 Abort、无桌面兜底（windows_capture.py:69-70；空白截屏也 Abort，windows.py:275-296）。OCR 为本地 Windows.Media.Ocr，恒报置信度 1.0（windows_ocr.py:56-57 注释）。UIA 走 `walk_actionable` BFS，4000 节点/1 秒时限（ax_common.py:115-188；windows.py:639-651），提取 checked/selected/expanded/value 状态（windows.py:534-596）。OCR 块与 UIA 控件按框重叠≥0.5（perception.py:23）+ 文本互含合并去重、阅读顺序编号、≤255 项（perception.py:504-575；config.py:9）。增量 OCR：256px tile 差分，仅重读变化 tile，>60% 变化转全区域、≤4 矩形（perception.py:32-35 常量 `TILE_DIFF=6.0/REOCR_FRACTION=0.6/MAX_REOCR_RECTS=4`，亲验）。
- **决策**：依赖 typesafe-sdk 0.6.0；每步一次请求带最多 4 个 Choice 问题（kind/site/item/offscreen，decide.py:363-407，407 行亲验）。confidence 只对指定目标的答案取 min——点击取 min(kind,item)（decide.py:279-289，亲验；更正原稿 363-407），低于 min_confidence 0.4 停机（runner.py:202-205；config.py:11）。发给模型的候选做确定性过滤：已选/已展开/已 acted 剔除、OCR/UIA 重复留 UIA 副本，注释明说防「双副本稀释概率」（decide.py:96-167）。
- **执行**：MCP 6 工具驱动 Python 子进程（mcp.mjs:26-73）；UIA pattern 优先，Invoke 故意 return False、强制走命中校验的坐标点击以规避 WinForms 模态死锁（windows.py:400-416）。护栏：每次输入前 `_guard` 校验前台未变 + 危险应用黑名单 powershell/cmd/keepass/bitwarden 等 10 项（windows.py:156-176，亲验）；密码字段 fail-closed、IsPassword 异常也当密码（windows.py:303-307，亲验）；打字后 Noul 验证 p<0.5 → `clear_field` 并在结果中上报「verification failed; cleared it」——**只清空、不自动重填**（actions.py:141-145，亲验；更正原稿「清空重填」）；连续 no-op≥2 判 stalled（runner.py:24,214-227）；左上角鼠标手势 + STOP 文件双逃生口（windows.py:69-76）。
- **交接与留痕**：host 文件握手 `runs/<uuid>/host/` 原子交换、1800s 超时、回复严格 schema 校验（host_writer.py:35-66）；「Jev 说完成不算数」（README.md:73）。每步落盘 4 文件 + run.json（runner.py:145-179）。密钥 DPAPI 加密、PowerShell 子进程解密（credentials.py:12-53）。
- **基准**：GeneralFixture.exe 8 个确定性 WinForms 任务族，夹具自判写 result.json，seed 尾数 0-4 dev/5-7 回归/8-9 holdout（benchmarks/GeneralFixture.cs:21-24,93-111,292-295）。仓内无汇总结果产物，文档仅给 3 个手跑案例（5.5s/5.5s/2.243s，README.md:78-87）并声明非通用提速保证。
- **决策端点来源说明**：`POST /v1/systemone`、Bearer 鉴权出自调研材料对 typesafe-sdk 0.6.0（PyPI wheel）的解包核实——**该 URL 在克隆内无法验证**（SDK 未 vendored，`grep -rin systemone` 全仓无匹配，亲验），引用时注意来源层级。

## 3. 成熟度与维护风险

**仓库事实**：30 commits（`git rev-list --count HEAD` 亲验）。其中 26 个上游 Aaron Levin 提交横跨 2026-09-15 至 09-18；**4 个 KofanLabs 提交**全部落在 2026-09-20 约 5 小时内（11:27-16:16 +0300；2b7ffa1 一次性倾倒整个移植，df0e6a9 收尾，`git log` 亲验——原稿首句歧义已更正）。GitHub API：created_at 与最后 push 同为 2026-09-20，此后 6 天零提交；1 star/3 forks/0 issues/0 PR/0 watcher。**GitHub Releases 有 v0.2.0/v0.2.1/v0.2.2 三个，均 2026-09-20 发布**（`gh api .../releases` 亲验；更正原稿「无 release」——原稿混淆了远程 release 与材料中「仅本地 tag」的旧说法，两处实际都有）。CI 真实：Windows+macOS 双平台 10 次运行全 success（ci.yaml:10-26）。测试：`grep -c "def test_"`=178（亲验）+ 2 处 parametrize ≈ 183，与 WINDOWS.md:99 自述吻合；本机未跑 pytest，183 以 CI 记录为准。文档诚实：README.md:25-37 逐组件差异对照，WINDOWS.md:89-122 明列限制（仅主显示器、PrintWindow 对 GPU 应用可能失败、任意应用未全面验证）。历史被改写：声称基于上游 cc7b5066（README.md:112-113），本地 `git cat-file` 无此对象，上游 67 commits 与本地 26 个 Levin 提交 SHA 交集为 0——`git merge upstream/main` 不可用。

**判断——1 star/30 commits 意味着什么**：无第三方复现或评审，README 全部能力与性能声明均为自述且仓内无汇总产物可独立核对；bus factor=1。**判断——维护风险：高**，风险类型是「单点维护 + 被上游取代」而非代码质量：上游（961★、活跃至 09-23）已于 09-22 合并自己的实验性 Windows 后端（PR #11，25 files/+1568/−331），移植仓的存在理由正被上游吸收，历史改写又堵死同步通道。CI/测试/文档质量客观是好的，但不解决弃坑与被取代的结构性风险。**敏感度说明**：本节结论不依赖 183 tests 或 5.5s 案例——即使这两个数字不实，维护风险评级与第 6 节建议不变。

## 4. 上游数据、决策渠道与同类方案

**仓库事实（上游与渠道）**：上游 2026-09-16 创建、961★/67 commits，README:23 自述 Beta；其 README 自述 $0.0002/决策、延迟 0.13-0.38s（**未实测**），移植 README 声明这些数字 "do not describe this port"。决策原语三条渠道：① TypeSafe 官方 key——申请入口 console.typesafe.ai/keys 与「docs 无官方定价页」**出自调研材料、本轮未爬取复核**，$0.042/M input 为第三方口径；② Vercel AI Gateway 有 typesafe-ai/jev，**本轮 WebFetch 实测 $0.042/1M input、无输出价**（providers: typesafe-ai+digitalocean；更正原稿 $0.04/1M）；③ 硅基流动官方文档确认 diffusiongemma/Kev-4b/SemIf 2026-10-08 前限时免费、「可能调整或停用」，typesafe_sdk 换 base_url 直接兼容。

**仓库事实（同类）**：同走「结构化决策+文本快照」路线的还有 **browser-use/jev-ultrafast**——`gh api` 实测 **20,439★**，README 第 11 行自述「TypeSafe's Jev picks an operation and an element. A small LLM writes text only when the operation is `TYPE_TEXT`」（原稿漏列且排他说法有误，已更正）；Callstack jevil（grabbou/jevil，Jev+agent-device QA agent，核实员核实）。组织级近亲 Microsoft UFO（`gh api` 实测 9,845★，Windows 上 UIA 文本树一等观测、决策器仍是通用 LLM）。截图/视觉派仍是主流（Anthropic computer use、OpenAI Operator/CUA、UI-TARS、OmniParser）。**剔除记录**：原调研所列 Stagehand-Jev 在 browserbase org 下查无独立仓（核实员核查、作者未复跑，按未能核实剔除）；jev-bot 实为股票/加密交易 bot、非 computer-use 同类，剔除。

**判断**：量级换算——按上游自述 $0.0002/决策 ≈ 5k tokens × $0.042/M（两条官方口径自洽）：一个 100 步任务约 $0.02，日均 1,000 步约 $6/月；硅基流动免费期内为 $0（10-08 后费率未公布）。免费期内我们的决策原语成本为零，优于两条美元渠道，差距在个人项目量级不构成切换压力，切换决策应由第 6 节 A/B 的质量数据而非成本驱动。

## 5. 对 jcu 项目的逐点借鉴

**移植仓现有、可直接取材（按杠杆排序，标注工作量/风险）**：
1. **item criteria 直接用 UIA 控件表**（含 role/state/区域，decide.py:384-397），跳过 GLM 候选生成一跳（对照 jcu/planner.py:36-55，亲验）——砍每步一次 LLM 调用并消除候选遗漏。**判断：杠杆最大**；需 jcu 快照补 state/区域字段，中等工作量。
2. 控件状态提取 + 已选/已展开过滤（windows.py:534-596；decide.py:96-98），直接防死循环；小工作量、低风险。
3. 输入读回验证：fill_field 后读回比对才算成功（actions.py:80-95）；Noul 验证失败清空并上报、**不自动重填**（actions.py:141-145，亲验）——我们 executor.py:32-34 的 type_keys 无验证；借鉴时注意补一个「重试一次」策略，上游没有。
4. 护栏全家桶：前台守卫、密码 fail-closed、危险应用黑名单、no-op 检测（对照 jcu/loop.py:11 只有 fallback_streak）；逐项独立、可增量加，小工作量。
5. 最小轨迹落盘（step-payload/answers/run.json，含 probabilities）——我们 loop.py:65-66 只有 print；小工作量。
6. GeneralFixture 式独立验证器夹具（result.json 由被测应用自判、seed 分区含 holdout，GeneralFixture.cs:93-111）可作 M3+ 任务集模板；注意校验器独立于 agent 引擎、但不独立于夹具程序本身。

**仅上游 HEAD 有、移植仓没有**：同名元素行上下文消歧（"'Buy' (middle-right; in the row of 'Coldplay', 'Oct 2')"）——由 fork 点之后的 68b678e/53110f5（2026-09-20，提交信息亲验）引入；移植仓 `grep "middle-right|Coldplay"` 无匹配（亲验）。中文界面大量同名按钮（确定/取消）会受益于此，但**到移植仓取材会落空**；应跟踪上游 Windows 后端转正后再借鉴。

**可复用模块**：决策适配器——`client.system_one` 全仓仅 2 个调用点（decide.py:407 多问题决策、decide.py:428 verify_typed 的 Noul，亲验），Choice 线格式与硅基流动 schema 同形；写约 100-150 行适配器 + 改 decide.py:8、runner.py:77-79、credentials 三处即可切换。**三个未验证点须冒烟实测**：硅基流动是否支持一次多 questions、Noul 有无等价物（可用 2 选项 Choice 模拟）、每题是否都回 confidence/probabilities。host 握手协议仅在做 MCP 形态时才需要，暂缓。

**避开的坑**：① PrintWindow 对 GPU/canvas 应用截黑只 Abort 不兜底（windows_capture.py:70；WINDOWS.md:107-108）——中文环境复刻感知层的首要适配风险，应设计兜底而非照抄；② OCR 中文质量取决于系统中文语言包（windows_ocr.py:15-21）；③ DPAPI 密钥解密经 PowerShell stdout 明文回传（credentials.py:29-49）；④ credentials.py:22 用 parents[1] 定位 provider.json，依赖 editable 安装，wheel 布局会错位；⑤ 上游低置信直接停机（runner.py:202-205）——我们已有 GLM 回退（jcu/loop.py:46-63，亲验），不要照抄倒退。我们有而它没有：SSRF host 校验（jcu/http_util.py:23-39）、决策后端抽象双实现、决策异常自动回退 GLM、低置信回退。

## 6. 结论与建议

**判断：只参考设计、定向借鉴；不直接用、不做整体二开。** 理由：① 供应链不匹配——它强制 TypeSafe Jev 或 Vercel key（credentials.py:27 亲验），我们走硅基流动免费 Alpha + 智谱 GLM，双后端已预留（jcu/config.py:21,30）；② 成熟度不足——单日停更快照、1 star、基于改写历史的上游旧点，当代码基座等于绑定死链；③ 形态不同——MCP host 外挂 vs 我们进程内 loop（jcu/loop.py），且零中文环境验证。

**A/B 触发点（2026-10-08 硅基流动 Alpha 到期前执行）**，样本与指标具体化（建议阈值为**判断**）：用 jcu/eval_data.json（实测 12 条）做 siliconflow vs typesafe 双后端对比；指标 = ①决策正确率（沿用 jcu/eval_run.py:30-44 的 got==answer 口径，n=12）、②单次决策延迟、③每题成本。建议判停：候选后端正确率不低于硅基流动基线（≥11/12）且延迟同量级，才在免费期结束、需要计费时切换；任何一题因 answers 缺 confidence/probabilities 导致解码失败，记为兼容性风险并优先修适配器而非切后端。第二个触发点：若需 MCP 形态对外集成，先看上游 experimental windows.py（PR #11）是否转正，而非依赖 kofanlabs 停更快照。在那之前，本项目对我们的价值是一份高质量的「Windows 落地设计参考 + 待冒烟的适配器规格」。
