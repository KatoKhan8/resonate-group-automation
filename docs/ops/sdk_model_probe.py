import asyncio, json, os, sys, time
from urllib.parse import urlparse
from claude_agent_sdk import query, ClaudeAgentOptions

SETTINGS = r"C:\Users\Zvonimir\Desktop\wt-glm-c-2026-10-14\.claude\settings.local.json"
cfg = json.load(open(SETTINGS, encoding="utf-8"))["env"]
BASE, TOKEN, MODEL = cfg["ANTHROPIC_BASE_URL"], cfg["ANTHROPIC_AUTH_TOKEN"], cfg["ANTHROPIC_MODEL"]
SCRATCH = os.path.dirname(os.path.abspath(__file__))

print("configured model     :", MODEL)
print("configured base host :", urlparse(BASE).hostname)   # host only, no path, no credential
print("token                : <not printed> len=%d" % len(TOKEN))
print()

async def run(label, env, prompt):
    opts = ClaudeAgentOptions(
        env=env, cwd=SCRATCH, allowed_tools=[], max_turns=1,
        setting_sources=[], permission_mode="default",
        system_prompt="Answer in one word. Do not use tools.",
    )
    print("### %s" % label)
    t0 = time.time()
    try:
        async for m in query(prompt=prompt, options=opts):
            t = type(m).__name__
            if t == "AssistantMessage":
                txt = "".join(getattr(b, "text", "") for b in m.content)
                print("  Assistant model=%r text=%r" % (getattr(m, "model", None), txt.strip()))
            elif t == "ResultMessage":
                print("  Result subtype=%s is_error=%s turns=%s" % (m.subtype, m.is_error, m.num_turns))
                print("  Result cost_usd=%r" % (m.total_cost_usd,))
                print("  Result usage=%r" % (m.usage,))
                print("  Result text=%r" % ((m.result or "")[:120],))
    except Exception as e:
        print("  EXCEPTION %s: %s" % (type(e).__name__, str(e)[:500]))
    print("  elapsed %.1fs\n" % (time.time() - t0))

async def main():
    # CONTROL, zero spend: same code path, base URL pointed at a dead local port.
    # If the session still answers, options.env is NOT reaching the binary and
    # any success in run 2 would prove nothing.
    await run("CONTROL - env honoured? base URL -> dead local port",
              {"ANTHROPIC_BASE_URL": "http://127.0.0.1:1",
               "ANTHROPIC_AUTH_TOKEN": TOKEN, "ANTHROPIC_MODEL": MODEL,
               "ANTHROPIC_API_KEY": "", "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64"},
              "Reply with exactly: OK")
    # LIVE: the real lane credential, the real lane model. Smallest call possible.
    await run("LIVE - the model a lane uses today (%s)" % MODEL,
              {"ANTHROPIC_BASE_URL": BASE, "ANTHROPIC_AUTH_TOKEN": TOKEN,
               "ANTHROPIC_MODEL": MODEL, "ANTHROPIC_API_KEY": "",
               "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64"},
              "Reply with exactly: OK")

asyncio.run(main())
