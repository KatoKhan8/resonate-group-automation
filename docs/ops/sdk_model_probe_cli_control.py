import json, os, subprocess, time
SETTINGS = r"C:\Users\Zvonimir\Desktop\wt-glm-c-2026-10-14\.claude\settings.local.json"
cfg = json.load(open(SETTINGS, encoding="utf-8"))["env"]
SCRATCH = os.path.dirname(os.path.abspath(__file__))
env = dict(os.environ)
for k in ("CLAUDECODE","CLAUDE_CODE_ENTRYPOINT","CLAUDE_CODE_SESSION_ID",
          "CLAUDE_CODE_CHILD_SESSION","CLAUDE_CODE_MESSAGING_SOCKET",
          "CLAUDE_CODE_MESSAGING_TOKEN","CLAUDE_PID","CLAUDE_EFFORT"):
    env.pop(k, None)
env.update({"ANTHROPIC_BASE_URL": cfg["ANTHROPIC_BASE_URL"],
            "ANTHROPIC_AUTH_TOKEN": cfg["ANTHROPIC_AUTH_TOKEN"],
            "ANTHROPIC_MODEL": cfg["ANTHROPIC_MODEL"],
            "ANTHROPIC_API_KEY": "", "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64"})
t0 = time.time()
p = subprocess.run(["cmd","/c","claude","-p","--output-format","json",
                    "--append-system-prompt","Answer in one word. Do not use tools."],
                   input="Reply with exactly: OK", capture_output=True, text=True,
                   cwd=SCRATCH, env=env, timeout=600)
el = time.time()-t0
print("exit", p.returncode, "elapsed %.1fs" % el)
try:
    d = json.loads(p.stdout)
    for k in ("subtype","is_error","num_turns","total_cost_usd","result","modelUsage"):
        if k in d: print(" ", k, "=", json.dumps(d[k])[:300])
    print("  usage =", json.dumps(d.get("usage"))[:400])
except Exception as e:
    print("  unparsed:", p.stdout[:800], p.stderr[:400])
