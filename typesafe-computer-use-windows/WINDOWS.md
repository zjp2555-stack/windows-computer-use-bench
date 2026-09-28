# TypeSafe Computer Use — Windows port

This repository is derived from commit `cc7b5066ae1a07b5e3182e8f87a9b5b6dfdcffc1`
of **awlevin/typesafe-computer-use**. It retains the original MIT license and
documentation in [the upstream reference](docs/upstream-macos-reference.md).
This is an independent Windows port, not an official TypeSafe product.

## Preserved decision loop

Capture the selected window → combine OCR and accessibility controls → ask Jev
for an operation and target in one request → execute → observe again.

The original decision questions, date handling, option generation, text
validation, task history, stopping conditions, and final-screen evaluation remain
available. Tasks do not require a prewritten list of clicks or field values.

## Windows equivalents

| Original macOS component | Windows implementation |
|---|---|
| Vision OCR | Local `Windows.Media.Ocr` |
| AX accessibility | Windows UI Automation |
| Quartz input | Windows keyboard/mouse input and UIA actions |
| Screen capture | DPI-aware `PrintWindow` capture of only the selected window |
| AppleScript app management | Observed Windows windows and foreground activation |
| Auxiliary writer model | MCP handoff to the current host agent; the original Anthropic option remains available for direct CLI use |

The host can be Codex, Grok, or any other agent that can call MCP tools and return
the requested JSON schema. The host is not consulted after every click. It is
only used for free text, uncatalogued URLs, and final-screen interpretation.

## Installation

Requirements: Windows 10/11, Python 3.12 or newer, Node.js 20 or newer, and a
TypeSafe Jev API key or Vercel AI Gateway key with access to Jev.

1. Download or clone the repository.
2. Double-click `Install-Windows.cmd`. It creates `.venv`, installs Python and
   Node dependencies, and generates a portable `mcp-config.json`.
3. Open `1-Start.cmd`, choose **Change API key**, select your provider, and paste
   your own key into the hidden prompt.
4. Add the generated `mcp-config.json` server to your MCP host and restart it.

If you move the folder, choose **Generate and open MCP configuration** again and
update the path in your host. Windows DPAPI binds the encrypted key to the Windows
account that saved it, so each Windows account must enter its own key.

## Agent workflow

Ask your agent, for example:

> Use Jev Computer Use on the open inventory window. Select Chestnut, set the
> priority to Low, save, and verify the final state.

The host then follows this MCP flow:

1. Call `typesafe_windows` and select the unique intended window.
2. Start `typesafe_run(goal, windowTitle, act=true)`. `act=false` predicts without
   applying input.
3. Poll with `typesafe_wait`. A `needs_host` result contains the exact context
   and response schema.
4. Inspect any supplied image, then answer with `typesafe_respond` using exactly
   the requested JSON fields.
5. Continue waiting until the worker returns its final report. Use
   `typesafe_status` for progress and `typesafe_stop` to request a stop.

Some MCP hosts load tools only when a new task starts. If the tools do not appear
after installation, fully restart the host or open a new task. Direct CLI use is
also available:

```powershell
.venv\Scripts\clicker.exe "your goal" --act --window-title "exact window title"
```

The original Anthropic writer settings remain available for standalone CLI use.
They are not required when an MCP host supplies text and verifies the result.

## Keys and task data

The setup menu stores the selected provider key under `config/` with Windows
DPAPI encryption. Plain `TYPESAFE_API_KEY` and Vercel `AI_GATEWAY_API_KEY`
environment variables are also supported. Keys are never logged.

The selected window's OCR and control text is sent to the configured Jev
provider. Host handoff packets go to the current MCP host. Screenshots, goals,
decisions, and action traces remain local under `runs/`; review private run data
before sharing it.

## Verified behavior

On September 20, 2026, the Windows port completed three live native visual tasks:

- A grid form with item selection, priority selection, and save: 5.5 seconds.
- A dynamic interface that required refresh, wait, option selection, and commit:
  5.5 seconds.
- A visual-code task requiring screenshot reading and host text handoff: success,
  with 2.243 seconds of measured UI interaction after the host reply.

The suite contains 183 passing tests. GitHub Actions passes on both Windows and
macOS. These measurements describe the tested machine and fixtures; they are not
a guarantee of a particular speedup or success rate for every application.

## Limits and safety boundaries

- The primary display is supported. Secondary displays and mixed-DPI layouts are
  not comprehensively certified.
- `PrintWindow` may not capture some GPU or canvas applications. The runtime does
  not silently switch to an unrelated desktop window.
- Windows OCR does not expose word confidence. A displayed OCR value of `1.0` is
  not model confidence.
- Browser address-bar handling uses the active browser profile, but arbitrary
  live websites are outside this native-window test matrix. Use Jev Browser for
  DOM-based Chrome tasks.
- Password fields are refused. UAC, lock screens, password managers, terminals,
  account security, and authentication remain under direct user control.
- Request a stop with `typesafe_stop`, `0-Stop.cmd`, or the upper-left mouse abort
  gesture. Input that has already been sent cannot be undone.
- During a host text handoff, the runtime rechecks the original field before
  writing. If focus or field state changed, it aborts instead of replaying input.

This is a working Windows port of the upstream project. Full equivalence has not
been certified across every Windows application.
