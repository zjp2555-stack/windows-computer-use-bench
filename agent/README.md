# jcu —— Jev 风格组合架构 computer use agent

「UIA 文本快照 → GLM 生成候选 → systemone 决策（低置信回退 GLM）→ pywinauto 执行」。
背景与完整方案见 `../out/implementation-plan.md` 与 `../out/research-report.md`。

## 上手步骤

```bash
cd agent
pip install -r requirements.txt

# 1. 配置密钥：复制 .env.example 为 .env，填 SILICONFLOW_API_KEY 和 ZHIPU_API_KEY
#    （智谱 key 在 open.bigmodel.cn 单独创建；ZHIPU_MODEL 按账号可用模型调整）

# 2. M0 冒烟：确认两条 API 鉴权可用、核对 systemone 实际返回 schema
python -m jcu.smoke_test

# 3. M1 决策质量 A/B（go/no-go 关口）
python -m jcu.eval_run

# 4. M3+ 桌面任务（默认 dry-run 只打印动作；确认无误后在 .env 改 EXEC_DRY_RUN=false）
python -c "from jcu.loop import run_task; run_task('在记事本里输入你好并另存为 hello.txt', title_re='记事本')"
```

## 安全提示

- 执行器默认 **dry-run**，真实键鼠操作需显式改 `EXEC_DRY_RUN=false`；
- 先在记事本、计算器等无害应用上验证，再考虑其他目标窗口；
- 动作白名单见 `jcu/executor.py`，步数上限默认 15（`.env` 可调）。

## 常见问题

- **候选里的中文文本哪来的？** GLM 预置在候选里——Jev 类模型不生成文本，只做选择。
- **界面控件太多？** 用 `run_task(..., scope='关键字')` 分域，或调小 `MAX_CANDIDATES`。
- **diffusiongemma 选错/低置信？** 属预期内的质量风险，看 M1 评测结果再决定去留（切 `DECISION_BACKEND=typesafe` 用官方 Jev 复测）。
