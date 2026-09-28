// Drive one real task through the MCP stack exactly as a ZCode host would:
// typesafe_run → answer every host request (free text / final answer) → poll to the outcome.
// Usage: node run_task.mjs "<goal>" [--window-title T] [--steps N] [--act]
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const argv = process.argv.slice(2);
const goal = argv[0];
if (!goal) {
  console.log('用法: node run_task.mjs "<goal>" [--window-title T] [--steps N] [--act]');
  process.exit(1);
}
const opt = (name, def) => {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : def;
};
const windowTitle = opt('--window-title');
const steps = Number(opt('--steps', '8'));
const act = argv.includes('--act');
// 自由文本应答队列：--text "A|B|C" 依次应答多次 type_text 请求（如先搜联系人再发消息）
const typeSegments = (opt('--text') ?? 'hello world').split('|');
const typeQueue = [...typeSegments];

const transport = new StdioClientTransport({ command: 'node', args: ['mcp.mjs'] });
const client = new Client({ name: 'zcode-host-driver', version: '1.0.0' });
await client.connect(transport);
const text = (t) => console.log(`[host] ${t}`);

const snap = async () => JSON.parse((await client.callTool({ name: 'typesafe_status', arguments: {} })).content[0].text);
const replyFor = (request) => {
  const reply = {};
  if ('fill' in request.properties) {
    if (typeQueue.length > 0) {
      reply.fill = true;
      reply.text = typeQueue.shift();
      reply.reason = `the goal asks for this text`;
    } else {
      reply.fill = false;
      reply.text = '';
      reply.reason = 'nothing more to type';
    }
  }
  if ('ok' in request.properties) {
    reply.ok = false;
    reply.url = '';
    reply.reason = 'no website needed for this test';
  }
  if ('achieved' in request.properties) {
    // 最终作答：用 packet 里的真实动作与屏幕 OCR 判断（以最后一段文本为准）
    const last = typeSegments[typeSegments.length - 1];
    const seen = JSON.stringify(request.packet ?? {}).includes(last);
    reply.achieved = seen;
    reply.answer = seen
      ? `屏幕上已出现「${last}」，任务完成。`
      : `屏幕上尚未看到「${last}」，任务未完成。`;
  }
  return reply;
};

let state = await snap();
const run = await client.callTool({
  name: 'typesafe_run',
  arguments: { goal, act, steps, ...(windowTitle ? { windowTitle } : {}) },
});
state = JSON.parse(run.content[0].text);
text(`run 发起 act=${act} steps=${steps} → ${state.status} ${state.runId ?? ''}`);

let answered = 0;
while (state.status === 'running' || state.status === 'needs_host') {
  if (state.status === 'needs_host') {
    const request = state.request;
    const reply = replyFor(request);
    answered += 1;
    text(`宿主请求 #${answered} ${request.id.slice(0, 8)}… fields=${Object.keys(request.properties).join(',')} → 应答 ${JSON.stringify(reply)}`);
    await client.callTool({ name: 'typesafe_respond', arguments: { requestId: request.id, reply } });
  }
  const waited = await client.callTool({ name: 'typesafe_wait', arguments: { seconds: 10 } });
  state = JSON.parse(waited.content[0].text);
}
text(`终态：${state.status}`);
if (state.report) text(`run.json：${JSON.stringify(state.report, null, 2)}`);
await client.close();
console.log(answered > 0 ? `完成，宿主应答 ${answered} 次` : '完成，无宿主请求');
