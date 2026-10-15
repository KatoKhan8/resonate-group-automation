import asyncio, json, os, time
from claude_agent_sdk import query, ClaudeAgentOptions
SETTINGS = r"C:\Users\Zvonimir\Desktop\wt-glm-c-2026-10-14\.claude\settings.local.json"
cfg = json.load(open(SETTINGS, encoding="utf-8"))["env"]
SCRATCH = os.path.dirname(os.path.abspath(__file__))
async def main():
    opts = ClaudeAgentOptions(
        env={"ANTHROPIC_BASE_URL": cfg["ANTHROPIC_BASE_URL"],
             "ANTHROPIC_AUTH_TOKEN": cfg["ANTHROPIC_AUTH_TOKEN"],
             "ANTHROPIC_MODEL": cfg["ANTHROPIC_MODEL"],
             "ANTHROPIC_API_KEY": "", "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64"},
        cwd=SCRATCH, max_turns=1,
        setting_sources=["user", "project", "local"],   # same as the CLI does
        permission_mode="default",
        system_prompt={"type": "preset", "preset": "claude_code",
                       "append": "Answer in one word. Do not use tools."},
    )
    t0 = time.time()
    async for m in query(prompt="Reply with exactly: OK", options=opts):
        if type(m).__name__ == "AssistantMessage":
            print("  model=%r text=%r" % (getattr(m,'model',None),
                  "".join(getattr(b,'text','') for b in m.content).strip()))
        elif type(m).__name__ == "ResultMessage":
            u = m.usage
            print("  is_error=%s cost_usd=%r" % (m.is_error, m.total_cost_usd))
            print("  input=%s cache_read=%s output=%s" % (
                u.get('input_tokens'), u.get('cache_read_input_tokens'), u.get('output_tokens')))
    print("  elapsed %.1fs" % (time.time()-t0))
asyncio.run(main())
