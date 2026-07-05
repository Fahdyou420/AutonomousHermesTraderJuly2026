import re

with open('C:\\Users\\user\\Desktop\\hermes_claude\\server.ts', 'r', encoding='utf-8') as f:
    content = f.read()

tools_code = '''
const DASHBOARD_TOOLS: any[] = [
  {
    type: "function",
    function: {
      name: "get_current_price",
      description: "Get the current market price for an instrument.",
      parameters: {
        type: "object",
        properties: {
          instrument: { type: "string", description: "The symbol, e.g. XAUUSD" }
        },
        required: ["instrument"]
      }
    }
  },
  {
    type: "function",
    function: {
      name: "get_account_state",
      description: "Get current MT5 account balance and equity.",
      parameters: { type: "object", properties: {} }
    }
  }
];

async function executeDashboardTool(name: string, args: any): Promise<string> {
  try {
    if (name === "get_current_price") {
      const inst = args.instrument || "XAUUSD";
      const r = await fetchWithTimeout(http://mt5_bridge:5558/latest_bars?instrument=&tf=M15&n=1, {}, 5000);
      if (r.ok) {
        const bars = await r.json();
        if (Array.isArray(bars) && bars.length > 0) return JSON.stringify({ price: bars[bars.length - 1].close });
      }
      return JSON.stringify({ error: "Could not fetch price" });
    }
    if (name === "get_account_state") {
      const r = await fetchWithTimeout("http://mt5_bridge:5558/account_state", {}, 5000);
      if (r.ok) {
        const data = await r.json();
        return JSON.stringify(data);
      }
      return JSON.stringify({ error: "Could not fetch account state" });
    }
    return JSON.stringify({ error: Tool  not implemented });
  } catch (e: any) {
    return JSON.stringify({ error: e.message });
  }
}
'''

nous_code = '''async function tryNousPortal(finalPrompt: string): Promise<{ text: string; provider: string } | null> {
  if (!nousClient) return null;
  const start = Date.now();
  let messages: any[] = [
    { role: "system", content: SMC_SYSTEM_INSTRUCTION },
    { role: "user", content: finalPrompt }
  ];
  try {
    let completion = await nousClient.chat.completions.create({
      model: nousModel,
      messages: messages,
      max_tokens: 4096,
      temperature: 0.7,
      tools: DASHBOARD_TOOLS
    });
    
    let message = completion.choices?.[0]?.message;
    if (message?.tool_calls && message.tool_calls.length > 0) {
      messages.push(message);
      for (const tc of message.tool_calls) {
        let args = {};
        try { args = JSON.parse(tc.function.arguments); } catch (e) {}
        const result = await executeDashboardTool(tc.function.name, args);
        messages.push({
          role: "tool",
          tool_call_id: tc.id,
          name: tc.function.name,
          content: result
        });
      }
      completion = await nousClient.chat.completions.create({
        model: nousModel,
        messages: messages,
        max_tokens: 4096,
        temperature: 0.7,
        tools: DASHBOARD_TOOLS
      });
      message = completion.choices?.[0]?.message;
    }
    
    const text = message?.content;
    const latency = Date.now() - start;
    if (text) {
      console.log([LLM] Nous Portal () responded successfully);
      await setLlmStatus("nous", nousModel);
      await broadcastLog("LLM_CASCADE", "SUCCESS", Tier 1: Nous Portal () completed in ms);
      return { text, provider: "nous-portal" };
    }
    return null;
  } catch (e: any) {
    const latency = Date.now() - start;
    console.warn([LLM] Nous Portal failed, falling through: );
    await broadcastLog("LLM_CASCADE", "WARNING", Tier 1: Nous Portal failed in ms - );
    return null;
  }
}'''

old_nous_match = re.search(r'async function tryNousPortal.*?return null;\n  }\n}', content, re.DOTALL)
if old_nous_match:
    content = content[:old_nous_match.start()] + tools_code + "\n\n" + nous_code + content[old_nous_match.end():]
    with open('C:\\Users\\user\\Desktop\\hermes_claude\\server.ts', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully updated server.ts")
else:
    print("Failed to find tryNousPortal")
