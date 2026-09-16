PRIORITY: P0
DEPENDS:

# TASK-182 - 42 green tests against an endpoint xAI has withdrawn

## WHERE THIS SITS

TASK-157 built `src/providers/xai.py` with 42 tests, all passing, against a
fake transport. TASK-166 then made real calls and could not use it:

    the Chat Completions live_search parameter is DEPRECATED - HTTP 410 Gone
    web search now lives on the Responses API at /v1/responses
    with {"type": "web_search"}

So TASK-166 called `/v1/responses` directly from a script, and the adapter -
allowlist, bounds, trimmed returns, usage and cost capture, bounded retry -
was bypassed entirely. Its 42 tests are green because a fake transport will
faithfully fake an endpoint that no longer exists.

That is the failure mode worth naming: a cassette-backed suite cannot tell you
the provider changed. It is also why TASK-166's real call was worth its money.

## THE QUESTION

1. **Move the adapter onto the Responses API.** `/v1/responses`, web search as
   a tool entry, and whatever the response envelope actually is - take the
   shape from TASK-166's working script, which has the only verified request
   and response pair we own.
2. **Keep everything the adapter was for.** The allowlist, the bounds, the
   trimmed returns, the usage and cost capture (`cost_in_usd_ticks`, 10B ticks
   = $1), `server_side_tool_usage`, `prompt_tokens_details.cached_tokens`, and
   the bounded retry that re-raises `MissingKey` immediately rather than
   spending attempts on a credential that will not appear. If the new envelope
   reports these under different names, map them and say so.
3. **Re-cassette from a real call.** Replace `tests/fixtures/cassettes/xai.json`
   with a recording of an actual `/v1/responses` call. ONE call, one domain,
   and scrub the response of anything identifying before committing it.
4. **Make the deprecation detectable.** Add a test that fails if the adapter's
   endpoint path or its tool-type string drifts from the one in the cassette,
   and say in a comment why a passing fake proves nothing about the provider.
5. **Point TASK-166's script at the adapter** and re-run it on ONE domain to
   prove the adapter produces what the script produced. Same domain, compare.

## THE TRAP

The 42 tests will keep passing whatever you do, because they test the adapter
against a fake you control. Green is not the goal here. The goal is one real
call through the adapter that returns what TASK-166's direct call returned, and
the only evidence that counts is that comparison.

Second trap: `XAI_API_KEY` was missing from a worker worktree's `config/.env`
this morning and was copied in. Read the key from the environment, never print
it, never commit it, never put it in a cassette - a recorded response can carry
a key in an echoed request header, so check the recording before you commit it.

## WHAT YOU MAY NOT DO

- ONE real API call for the cassette, ONE for the comparison. Not more.
- Do not wire the adapter into `qualify`, `generate`, `research` or any
  production path - TASK-183 does that behind a flag, and it needs this first.
- No provider writes to HeyReach or EmailBison.
- Never commit a key, a token, or a `.env`. Env var NAME only.
- Do not delete a test to make the suite green.

## FILES ALLOWED

    src/providers/xai.py
    tests/test_xai_adapter.py
    tests/fixtures/cassettes/xai.json
    docs/GROK-LANE-2026-09-15.md   (correct it - it documents the dead endpoint)
    scripts/task182_*.py

## FILES FORBIDDEN

    config/   work/   src/providerwrites.py

## DELIVERABLE

The adapter on the Responses API with the capture fields mapped, a cassette
recorded from a real call and scrubbed, the drift test, and the one-domain
comparison showing adapter output matches TASK-166's direct call.
