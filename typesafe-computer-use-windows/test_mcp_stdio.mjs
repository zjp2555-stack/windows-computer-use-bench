// Simulate a ZCode-style MCP host session against mcp.mjs over stdio:
// initialize → tools/list → typesafe_windows → typesafe_run (dry) → wait for the outcome.
// Run from the repo root:  node test_mcp_stdio.mjs
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const step = (label, ok, detail = '') =>
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
let failed = false;
const check = (label, ok, detail) => {
  step(label, ok, detail);
  if (!ok) failed = true;
};

const transport = new StdioClientTransport({ command: process.env.CLICKER_NODE || 'node', args: ['mcp.mjs'] });
const client = new Client({ name: 'zcode-simulator', version: '1.0.0' });
await client.connect(transport);

const tools = await client.listTools();
const names = tools.tools.map((t) => t.name).sort();
check(
  'tools/list 返回 6 个工具',
  names.length === 6 && names.join() === 'typesafe_respond,typesafe_run,typesafe_status,typesafe_stop,typesafe_wait,typesafe_windows',
  names.join(', '),
);

const windows = await client.callTool({ name: 'typesafe_windows', arguments: {} });
if (windows.isError) {
  check('typesafe_windows 列出窗口', false, String(windows.content?.[0]?.text).slice(0, 200));
  process.exit(1);
}
const listed = JSON.parse(windows.content[0].text);
const target = listed.find((w) => w.title && w.title.length > 1 && w.title !== 'Program Manager');
check('typesafe_windows 列出窗口', Array.isArray(listed) && listed.length > 0, `${listed.length} 个窗口，选中 ${target?.title ?? '无'}`);
if (!target) {
  console.log('没有可用目标窗口，提前结束');
  process.exit(1);
}

const run = await client.callTool({
  name: 'typesafe_run',
  arguments: { goal: '把当前窗口最小化', windowTitle: target.title, act: false, steps: 3 },
});
const runState = JSON.parse(run.content[0].text);
check('typesafe_run 发起干跑', ['running', 'needs_host'].includes(runState.status), `runId=${runState.runId ?? '(见下)'}`);

let final = runState;
const started = Date.now();
for (let i = 0; i < 60 && final.status === 'running'; i++) {
  await new Promise((r) => setTimeout(r, 1000));
  const snap = await client.callTool({ name: 'typesafe_status', arguments: {} });
  final = JSON.parse(snap.content[0].text);
}
check(
  'typesafe_status 轮询到终态',
  final.status === 'dry run',
  `outcome=${final.status}，耗时 ${((Date.now() - started) / 1000).toFixed(1)}s，run 目录=${final.runFolder ?? '?'}`,
);

const stop = await client.callTool({ name: 'typesafe_stop', arguments: {} });
check('typesafe_stop 空跑调用不报错', stop.content?.length > 0);

await client.close();
console.log(failed ? '\nMCP 链路测试 FAIL' : '\nMCP 链路测试 ALL PASS');
process.exit(failed ? 1 : 0);
