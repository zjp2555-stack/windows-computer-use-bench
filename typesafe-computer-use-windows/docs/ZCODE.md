# 本地改造说明（ZCode 接入版）

本仓库是 kofanlabs/typesafe-computer-use-windows（awlevin/typesafe-computer-use 的 Windows 移植）的 vendored 副本，
为配合 jev 项目做了两类改造：**决策模型可插拔 + 国产化**、**ZCode MCP 接入**。上游 git 历史被改写过（非 fork），
无法直接 merge 上游，本文件记录全部本地改动，便于人工比对升级。

## 决策模型可插拔

- **新增 `typesafe_computer_use/decision_backends.py`**
  - `build_decision_client()`：按环境变量 `DECISION_BACKEND`（默认 `siliconflow`）构造决策客户端，
    以装饰器 `@register_backend("名字")` 注册；未来加新后端（如 ZCode 官方决策模型）只需新增一个类 + 一行注册，
    循环与 decide 层零改动。
  - `SiliconFlowClient`：硅基流动 SystemOne（`POST /v1/systemone`，模型默认 `diffusiongemma`，
    env `SILICONFLOW_MODEL` / `SILICONFLOW_BASE_URL` / `SILICONFLOW_TIMEOUT` 可覆盖）。
    与 typesafe-sdk 同款鸭子接口 `system_one(state=, questions=) -> .answers`。
    - Alpha 容错：choice 答案缺 `confidence` 按 1.0 处理（避免置信度门控误停）；choice 回键或回原文都兼容。
    - **dict state 自动序列化为 JSON 字符串**（冒烟实测该端点 state 只收文本；上游 decide.py 传 dict）。
    - **单选项 Choice 本地短路**：端点拒收只有一个 criterion 的 Choice（HTTP 400 20015），而单选项本无决策可言，
      客户端直接以 confidence=1.0 返回唯一项，不发起请求。
    - Noul 原语在硅基流动不可用（实测 choice 可用）：Noul 问题自动降级为 true/false 双选项 Choice，
      答案映射回 `.noul` 浮点（冒烟通过）。
    - **多 questions 批量请求可用**（冒烟实测 kind+item 同请求返回正常）；批量失败或缺 key 自动降级为
      逐问题请求合并，`fallback_reason` 记录原因。
    - **单次 Choice 的 criteria 上限 26 个**（二分实测：26 通过、27 拒收，与描述长度无关）。
      `config.max_options()` 据此把硅基流动后端的感知预算从上游的 255 降到 24，
      环境变量 `SILIFLOW_MAX_OPTIONS` 可覆盖；客户端对超限请求直接报错不发请求。
    - 429/5xx/连接错误指数退避重试（见 `cn_http.py`）。
  - `typesafe` 后端：直接包装上游 TypeSafeClient，保留 A/B 对比能力（env `TYPESAFE_API_KEY` 等）。
- **新增 `typesafe_computer_use/cn_http.py`**：标准库 JSON POST 工具，带 SSRF 防护
  （拒绝环回/内网/保留地址；本机 Clash fake-ip 场景用 `HTTP_ALLOW_FAKE_IP=true` 放行 198.18.0.0/15）。
- **`runner.py`**：`TypeSafeClient` 构造点（原 :77-79）换成 `build_decision_client(timeout=20)`；
  writer 失败捕获从 `anthropic.APIError` 换成 `writer.WriterError`。
- **`cli.py`**：`_prepare()` 按后端校验密钥（siliconflow 要求 `SILICONFLOW_API_KEY`，不再强制 TYPESAFE_API_KEY）。
- **`config.py`**：新增 `DEFAULT_DECISION_BACKEND`/`decision_backend()`。

## writer 国产化（GLM）

- **新增 `typesafe_computer_use/zhipu_writer.py`**：智谱开放平台 GLM 后端，实现与 HostWriter 相同的
  `structured(system, packet, properties, image)` 接口，`compose_text`/`compose_url`/`compose_answer` 无改动复用。
  纯文本走 `ZHIPU_MODEL`（默认 glm-4.6）；带截图的最终作答走 `ZHIPU_VISION_MODEL`（默认 glm-4.6v）。
  MCP 宿主模式下（`CLICKER_HOST_DIR` 存在）自由文本仍由宿主应答，不调任何 API。
- **`writer.py`**：删除 Anthropic 客户端与 `messages.create` 回退路径；`make_writer()` 优先级：
  MCP HostWriter → ZhipuWriter（`ZHIPU_API_KEY`）→ None（明确提示）。
- **`actions.py`**：`Context.writer` 类型更新，移除 anthropic 导入。
- **`config.py`**：writer/answer 默认模型改为 `glm-4.6` / `glm-4.6v`（env `CLICKER_WRITER_MODEL`/`CLICKER_ANSWER_MODEL` 可覆盖）。
- **`pyproject.toml` / `requirements-windows-verified.txt`**：移除 `anthropic` 依赖；typesafe-sdk 保留（题目类型 + typesafe 后端）。
- **`tests/test_answer.py`**：writer 相关用例改打到 GLM 后端（mock `zhipu_writer.post_json`），覆盖不变。

## MCP（适配 ZCode 等 stdio 宿主）

- **`mcp.mjs`**：Python 解释器支持 `CLICKER_PYTHON` 环境变量覆盖（默认仍为 `.venv/Scripts/python.exe`）。
- **`typesafe_windows` 改用 Win32 EnumWindows（ctypes）**：本机 UWP shell 控件会让 UIA 的根控件属性读取
  无限挂起（Name/IsOffscreen 卡死，尝试过 SetGlobalSearchTimeout 无效），UIA 枚举不可靠；
  EnumWindows 毫秒级返回，顶层窗口标题与 UIA 一致。`execFile` 超时同步放宽到 60s。
- **`windows.py activate_title` 同因改写**：按标题找窗口改为 Win32 枚举（`_visible_top_windows`）+ 原有 `_focus_window` 激活，
  语义不变（标题必须唯一命中，否则 Abort）。
- 工具不变：`typesafe_status` / `typesafe_windows` / `typesafe_run` / `typesafe_respond` / `typesafe_wait` / `typesafe_stop`。
- **`test_mcp_stdio.mjs`**：模拟 ZCode 宿主的 stdio 协议级测试（握手→列工具→列窗口→干跑→轮询终态→停止），
  `node test_mcp_stdio.mjs` 可复跑，2026-09-27 全过（干跑 4.0s 到终态）。
- **`run_task.mjs`**：真实任务的宿主驱动器，`node run_task.mjs "<goal>" --window-title T --act` ——
  发起 run、自动应答全部宿主请求（自由文本按目标回、最终作答按 packet 里的动作+OCR 判断）、轮询到终态。

## 路由契约与决策语义修复（2026-09-27，用户实测反馈驱动）

用户实测发现「打开记事本」类目标失效：OCR 看不到相关文本时 diffusiongemma 满置信度误选 `use_browser`。
根因是**动作空间没有「启动应用」原语**——这类目标根本不该进决策循环。修复两层：

1. **criteria 语义修正**（decide.py fixed_actions）：`none` 改为明确的「此路不通」出口（目标需要别的应用/
   系统动作/可见控件之外的任何事 → 选 none，宿主接手；绝不拿 use_browser 顶替）；`use_browser` 收窄为
   仅当目标本身关于网页内容。实测探针：「打开记事本」（屏上无关）→ none 0.9996（use_browser 0.0）；
   「去 bilibili」→ use_browser 0.998，正当目标不受影响。
2. **宿主路由契约**（SKILL.md「Route tasks before calling the runtime」）：宿主先用自家工具准备环境
   （启动应用一条命令胜过截图循环），只把「已开窗口内的纯 GUI 操控」交给 typesafe_run；
   `nothing helps`/`low confidence` 不盲试重跑，先检查应用是否打开、状态是否就绪；
   无障碍致盲的 GPU 渲染应用（QQ NT：UIA 树空、OCR 带空格噪声）保持脑在宿主、逐步视觉验证、
   确定性执行，不放 autonomous 循环（真实应用里点错就是真动作）。

**QQ 实战记录**：QQ NT 整窗画在 DirectComposition 上，PrintWindow 抓到均匀灰图（边缘均值 0.54，
正常界面 6.6+），UIA 树近乎空（--force-renderer-accessibility 与 SPI_SETSCREENREADER 均无效，
子窗口仅一个 Intermediate D3D Window）。已实现 **windows_capture 前台屏幕 DC 回退**：PrintWindow 结果
边缘强度低于阈值且目标为前台窗口时，重抓屏幕 DC 并在 stdout 声明（后台窗口绝不抓屏，非静默）。
QQ 自主循环实测会误点真实联系人——按路由契约改为宿主逐步驾驶；未发送任何消息。

## 本机注意事项与性能实测（2026-09-27）

**启动目标应用的弹窗问题**：`notepad.exe` 在 System32 的实体是 Win11 启动跳板（通过协议拉起 Store 版记事本）。
强杀记事本后立刻重启，会撞上 Store 包协议注册的短暂窗口期，Windows 弹一次「选择打开方式」。
规避：用绝对路径启动（`C:\Windows\System32\notepad.exe`）、强杀后等 1-2 秒再启动；用户选过一次后系统会记住。
另记录：本机 `python.exe`/`python3.exe` 的应用执行别名是商店重定向器（AppInstallerPythonRedirector），脚本一律用 venv 绝对路径。

**启动耗时实测**（venv Python，暖机后）：
- 纯 import（cli 全链）：**0.79s**（uiautomation 0.08s、typesafe-sdk 0.25s，均非瓶颈）；
- MCP 干跑端到端（node 握手 + python 拉起 + 截屏 + diffusiongemma 决策）：**4.0s**；
- 真实打字任务（2 步决策 + 打字 + 校验 + 作答）：**约 5s**，其中决策 API ~0.9s/次、
  verify_typed API ~1s 属硅基流动服务端延迟，本地无法再压。
- 感知层面的「慢」主要来自对话式编排（后台任务+轮询+多轮命令）；短任务已改前台直跑。
  若日后需要亚秒级启动，可做常驻 Python worker（MCP server 与 CLI 进程长连），当前无必要。

## 真实执行验证（2026-09-27，--act）

任务「在记事本里输入 hello world」端到端真机跑通，全程约 5 秒：

1. **step 1**：截屏 → UIA 树 8 个交互控件 + OCR 23 项 → 检测到焦点字段 `AXTextArea:'文本编辑器'` →
   diffusiongemma 选 `type_text`（conf 1.00）→ 宿主请求打字内容 → MCP 宿主应答 "hello world" →
   经 UIA accessibility 写入 → **verify_typed（硅基流动 Noul 映射）= 1.00**；
2. **step 2**：再次截屏（OCR 可见 hello world）→ diffusiongemma 选 `done`（conf 1.00）；
3. **作答**：宿主请求最终作答 → 按 packet 判 achieved=true → run.json 终态 `done`。

截屏（step-002-raw.png）人工复核：记事本正文确为 "hello world"（11 字符）。打字走 UIA accessibility
而非键盘注入，中文 IME 不构成干扰。宿主应答共 2 次（自由文本 + 最终作答），typesafe_respond 链路实测通过。

## ZCode 注册（工作区级）

`<工作区根>/.zcode/config.json`：

```json
{
  "mcp": {
    "servers": {
      "jev-computer-use": {
        "type": "stdio",
        "command": "C:\\Program Files\\nodejs\\node.exe",
        "args": ["C:\\Users\\pc\\Desktop\\工作项目\\jev\\typesafe-computer-use-windows\\mcp.mjs"],
        "timeoutMs": 600000
      }
    }
  }
}
```

重启 ZCode 会话后生效，工具名形如 `mcp__jev-computer-use__typesafe_run`。

## 凭据

- 仓库根 `.env`（不入库）：`DECISION_BACKEND=siliconflow`、`SILICONFLOW_API_KEY`、`ZHIPU_API_KEY` 等，
  与 `agent/.env` 同源。模板见 `.env.example`。
- 上游的 DPAPI 密钥脚本（`scripts/Set-Key.ps1` 等）仍服务 typesafe 后端，未改动。

## 冒烟实测结论（2026-09-27，真实 API）

仓库根 `smoke_cn_backends.py` 可复跑（`.venv/Scripts/python.exe smoke_cn_backends.py`）：

1. 硅基流动单 choice：正常，返回 probabilities + confidence。
2. 多 questions 批量：可用（kind+item 同请求）。
3. Noul → true/false Choice 映射：可用，`.noul` 正确回读。
4. GLM writer（glm-4.6 文本 / glm-4.6v 视觉）：结构化 JSON 回复正常，视觉模型正确读图。
5. 端到端干跑（ZCode 窗口，act=false）：PrintWindow 截屏 0.08s → 本地 OCR 中文 0.67s →
   diffusiongemma 批量决策 1.69s → 干跑安全停止，单步合计 2.64s。

## 默认浏览器与 activate 修复（2026-09-27，用户实测反馈驱动）

- **默认浏览器改 Edge**：仓库根 `.env` 增加 `CLICKER_BROWSER=Microsoft Edge`（机器级配置，走
  `config.browser()` 既有覆盖机制，代码默认值 `DEFAULT_BROWSER="Google Chrome"` 保持上游原样）。
  `windows.py _name()` 已把 `msedge.exe` 映射为 `Microsoft Edge`，`activate`/`open_url` 按此匹配。
- **修复 `windows.py activate()` 两处缺陷**（此前 use_browser 在本机 100% 失败的根因）：
  1. 原实现走 `auto.GetRootControl().GetChildren()` UIA 根遍历——本机 UWP shell 控件上会无限挂起
     （与 typesafe_windows/activate_title 当初改 Win32 同因，当时漏掉了 activate），且
     `control.ProcessId` 属性读取会抛 COMError -2147220991 把 run 记成 crashed（except 只接
     OSError/psutil.Error 接不住）。现改用 `_visible_top_windows()`（Win32 EnumWindows）+
     `_pid`/`_name` 匹配 + `_focus_window` 置前，与文件内既有 Win32 模式一致。
  2. 原实现要求「进程下可见顶层窗口唯一」才激活；Edge 常驻一个 600x72 的「搜索栏」小部件窗口，
     导致 Edge 永远不唯一。现多窗口时取最大面积窗口：同一浏览器进程 = 同一配置档
     （Chromium 每配置档一个浏览器进程），不违背 open_url 的 "never silently switch profiles" 原则。
- 实测：`activate('Microsoft Edge')` 立即 True 且前台确为 Edge（原版挂起 >25s）；192 单测全绿。

## MCP 更名（2026-09-28，用户指示，中性命名）

- 注册名沿革：`jev-computer-use` → `decide` → 最终定名 **`decide-computer-use`**
  （用户级 `~/.zcode/cli/config.json` 的 mcp.servers key）。用户未使用 Jev/Tev（Typesafe AI）模型，
  名称不绑定任何模型/厂商，取"决策模型驱动 computer use"的中性语义。
- 工具前缀 `mcp__decide-computer-use__typesafe_*`；`mcp.mjs` server 名 `decide-computer-use`；
  仓库 SKILL.md frontmatter 同步。ZCode 对 MCP 配置热重载，会话内新前缀即时生效。
- 仓库内文档/基准记录中的历史名称保留并加注，不回写历史（fixture 标题 "Jev General Benchmark"
  是基准程序名，与 MCP 无关，保留）。

## offscreen 超预算崩溃修复 + JCU-Bench v1 混合路由（2026-09-28）

- **修复 decide.py offscreen 崩溃**：虚拟化列表（55 项 ListBox）会把 41 个离屏控件塞进一个 Choice，
  超硅基流动单问题 26 上限直接 ValueError（JCU-Bench long-list 族首跑崩溃）。现
  `offscreen_criteria/offscreen_records` 走 `_offscreen_selected`：目标命名（goal 内出现的标签）
  优先、其余按阅读序，截断到 `max_options()`；**键保持 screen.offscreen 原始位置**
  （actions.press_offscreen 按它索引执行，重排会错点）。192 单测全绿；补丁后重测：
  diffusiongemma 1.00 直选目标 → offscreen 拒绝 → 滚动×2 → 点击 → 提交，评估器 success。
- **JCU-Bench v1 对比基准跑完**（GeneralFixture 8 族 × seed 0 × MCP/原生双引擎，独立评估器判分）：
  成功率 7/8 vs 7/8 打平，失败点正交。MCP 能自主点掉模态对话框「确定」（2.2s），原生 SDK 对同一
  对话框 helper UIA 挂死且 stop() 后会话不可恢复；原生对虚拟化长列表直接命中离屏项，MCP 补丁前崩溃。
  MCP 的 "accessibility press did not take" 是系统性校验滞后误报（事件流显示动作已落地）——判成败
  以独立评估器为准。报告 `../out/benchmark-report.md`，数据与脚本 `benchmarks/bench-jev/`。
- **混合路由技能落地**：工作区技能 `.zcode/skills/hybrid-computer-use/SKILL.md`（本仓 SKILL.md
  已加第 0 条指向它）——多步控制密集/模态框/滚动定位/OCR 文本/中文打字给本运行时；单步快操作/
  虚拟化长列表/ComboBox 设值/拖拽组合键坐标/纯视觉给原生 SDK；模态框开着时原生禁止再观察。

## 已知边界

- 只做过干跑验证，`--act` 真实执行未开（何时开由使用者决定）。
- 硅基流动单 Choice 上限 26 个 criterion：超复杂界面（>24 可交互元素）时感知预算自动截断，
  OCR-only 元素优先被丢（上游 kept_by_budget 逻辑），必要时用 `SILIFLOW_MAX_OPTIONS` 调整。
- Electron 应用（如 ZCode）的 UIA 可交互控件树常为空（ax=0），决策只能依赖 OCR 文本块；
  Win32 应用（如记事本）的 AX 通道正常。
- 上游对 macOS 的支持代码（macos_native.py 等）原样保留，未做国产化改造（本机用不到）。
