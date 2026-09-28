# Windows Computer Use：决策模型 MCP 引擎 × ZCode 原生 × 混合路由实测

一个完整的桌面自动化（computer use）技术选型项目：从决策模型可行性调研，到组合架构引擎搭建与 MCP 接入，再到三引擎同台基准实测，最终落地为可复用的混合路由规则。

## 一句话结论

- 决策模型独立驱动 computer use 不可行，唯一现实路径是「UIA/OCR 文本快照 → 决策模型单步选择 → 代码执行」组合架构（GLM 当脑、决策模型当手）；
- MCP 引擎与 ZCode 原生 computer use 同台基准：成功率打平（7/8 vs 7/8），但**失败点完全正交**——引擎败于 ComboBox 弹出层感知盲区，原生被模态对话框确定性挂死；
- 按实测数据落地混合路由后三引擎复测：**hybrid 16/16 = 100%，MCP 95.8%，native 87.5%**。

## 目录结构

| 路径 | 内容 |
|---|---|
| `out/` | 项目技术文档：可行性调研、实施方案、移植版调研、基准报告（v1+v2） |
| `agent/` | 组合架构验证骨架（jcu）：决策适配器双后端、UIA 感知、GLM 候选生成、置信度门控回退 |
| `typesafe-computer-use-windows/` | 引擎底座：上游 Windows 移植版 + 本项目改造（决策后端可插拔、writer 国产化换 GLM、Win32 窗口激活重写等，全部变更见其 `docs/ZCODE.md`） |
| `typesafe-computer-use-windows/benchmarks/bench-jev/` | 基准数据：评测协议 `protocol.md`、原始运行记录 `results.jsonl`（含作废行，21 行）、三引擎分组数据 |
| `.zcode/skills/hybrid-computer-use/` | 混合路由技能：什么任务交 MCP、什么交原生、什么宿主直接做，含双向交接与挂死处置协议 |

## 报告入口（建议阅读顺序）

1. `out/research-report.md` — 可行性调研（为什么独立不可行）
2. `out/implementation-plan.md` — 组合架构方案
3. `out/benchmark-report.md` — JCU-Bench v1/v2 三引擎对比基准（核心数据）

## 运行前提

- Windows 11 + Python 3.12+ / Node（MCP 服务器）
- API 密钥通过 `.env` 自行配置（不入库）：硅基流动 SystemOne 端点（决策）与智谱 GLM（宿主/writer），所需变量见 `agent/jcu/config.py` 与 `typesafe-computer-use-windows/` 根 `.env` 的键名
- 引擎单测：`typesafe-computer-use-windows` 内 192 个单元测试（`pytest`）
