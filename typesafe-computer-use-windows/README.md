# Jev Computer Use — Desktop Automation for Windows

A Windows adaptation of [TypeSafe Computer Use](https://github.com/awlevin/typesafe-computer-use),
with local OCR, UI Automation and MCP integration for Codex, Grok and other agents.

<img src="docs/banner.svg" alt="Jev Computer Use — Desktop Automation for Windows" width="100%">

<p align="center">
  <a href="https://github.com/kofanlabs/typesafe-computer-use-windows/actions"><img alt="CI" src="https://github.com/kofanlabs/typesafe-computer-use-windows/actions/workflows/ci.yaml/badge.svg"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white">
  <img alt="Windows" src="https://img.shields.io/badge/platform-Windows-0078D4?logo=windows&logoColor=white">
  <a href="https://docs.typesafe.ai"><img alt="TypeSafe" src="https://img.shields.io/badge/decisions-TypeSafe%20jev-8b5cf6"></a>
  <a href="https://github.com/astral-sh/ruff"><img alt="Ruff" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json"></a>
</p>

Give it a goal and select an open Windows application. Jev chooses the next
operation and target from the window's text and controls. The MCP host supplies
free text when needed and independently checks the final screen.

This is an independent KofanLabs Windows port, not an official TypeSafe product.
The original dynamic decision loop is retained; tasks do not require a scripted
sequence of clicks.

## What differs from upstream?

| Component | Original macOS project | This Windows port |
|---|---|---|
| Screen capture | macOS capture APIs | DPI-aware target-window PrintWindow capture |
| OCR | Apple Vision | Local Windows.Media.Ocr |
| Accessibility | macOS AX | Windows UI Automation |
| Input and window handling | Quartz and AppleScript | Windows input, UIA and window activation |
| Text and final-screen interpretation | Auxiliary Anthropic models | MCP host handoff; standalone Anthropic mode remains available |
| Agent integration | CLI | Windows MCP server plus CLI |

The macOS backend remains available. Its installation, architecture and historical
benchmarks are preserved in the [upstream macOS reference](docs/upstream-macos-reference.md).

## Windows quick start

Requirements: Windows 10/11, Python 3.12+, Node.js 20+, and a TypeSafe Jev API key
or a Vercel AI Gateway key with access to Jev.

1. Download or clone [this repository](https://github.com/kofanlabs/typesafe-computer-use-windows).
2. Double-click **Install-Windows.cmd**.
3. Open **1-Start.cmd**, choose **Change API key**, select your provider and paste
   the key into the hidden prompt.
4. Add the generated `mcp-config.json` to your MCP host and restart the host.
5. Open the target application and ask the agent to use **Jev Computer Use** there.

Example request:

> Use Jev Computer Use on the open inventory window. Select Chestnut, set the
> priority to Low, save, and verify the final state.

The setup menu stores keys using Windows DPAPI. No separate Anthropic key is
required when the MCP host supplies text and evaluates the final screen.
See [WINDOWS.md](WINDOWS.md) for configuration and [SECURITY.md](SECURITY.md) for data handling.

## How it works

```text
Selected window → capture + local OCR/UIA → Jev chooses operation and target
                → execute → observe again
                     ↕
          MCP host: text, URLs and final-screen verification
```

The host first lists windows with `typesafe_windows` and selects the intended title.
It starts `typesafe_run` with a bounded goal; `act=false` previews a decision,
while `act=true` applies input. `typesafe_wait` returns progress or a `needs_host`
packet. The host inspects the packet and any image, then uses `typesafe_respond`.
Jev's completion signal alone does not establish success.

Stop a run with `typesafe_stop`, **0-Stop.cmd**, or the top-left mouse abort gesture.
Stopping takes effect at the next boundary; already-issued input cannot be undone.

## Windows measurements and limits

The recorded September 20, 2026 native-window checks completed a grid form in
5.5 seconds and a dynamic refresh/select/commit task in 5.5 seconds. A visual-code
task with host text handoff also succeeded, with 2.243 seconds of measured UI
interaction **after** the host reply. That last number is not total task time.

These are fixture-specific observations, not a general speedup guarantee or a
comparison against frontier models. See [the Windows test notes](WINDOWS.md#verified-behavior).
Upstream cost and speed tables are kept separately and do not describe this port.

- The primary display is supported; secondary displays and mixed-DPI setups are not comprehensively tested.
- PrintWindow can fail on some GPU-rendered applications. OCR and UIA also depend on what an app exposes.
- Arbitrary applications and live websites have not been comprehensively validated.
- For DOM-based Chrome/Edge tasks, use [Jev Browser Bridge](https://github.com/kofanlabs/jev-browser-chrome).
- Authentication, password managers, terminals and account/security changes remain under direct user control.
- Selected-window text is sent to the configured Jev provider. Screenshots and traces are stored locally under `runs/`.

## Development

```text
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
node --check mcp.mjs
uv build
```

CI is configured for Windows and macOS. See [CONTRIBUTING.md](CONTRIBUTING.md).
The compatibility entry point `typesafe_computer_use/macos.py` dispatches to
`windows.py` or `macos_native.py`; `host_writer.py` handles MCP text/answer handoffs.

## License and attribution

[MIT](LICENSE). Based on `awlevin/typesafe-computer-use` at commit
`cc7b5066ae1a07b5e3182e8f87a9b5b6dfdcffc1`, retaining its license and attribution.
