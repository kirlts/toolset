# API Message Alternation Errors

Debugging HTTP 400 errors caused by strict message alternation enforcement in LLM providers.

## Symptom

```
HTTP 400: Error from provider (DeepSeek): An assistant message with 'tool_calls'
must be followed by tool messages responding to each 'tool_call_id'.
(insufficient tool messages following tool_calls message)
```

Or any variant of "tool_calls must be followed by tool messages".

## Root Cause

The OpenAI chat completions API requires strict message role alternation:

```
user → assistant(tool_calls) → tool → assistant → user → ...
```

**Violation**: When an `assistant` message contains `tool_calls` but the NEXT message is NOT a `tool` response (another `assistant` or `user` message instead), the provider rejects the request.

## How It Happens in Hermes

1. The agent sends a response with `tool_calls`
2. The API call is **interrupted** (user sends new message, session forks, gateway restart)
3. The conversation history gets truncated/repaired, but some `tool_calls` fragments remain without their corresponding `tool` responses
4. On the next API call, the message history violates alternation
5. Provider returns HTTP 400

## Diagnosis

### Check agent.log

```bash
grep "Error from provider.*tool_calls must be followed" ~/.hermes/logs/agent.log
```

### Check for interruption signals

```bash
grep "interrupted_during_api_call\|Turn ended: reason=interrupted" ~/.hermes/logs/agent.log
```

### Check for message repair

```bash
grep "Repaired.*message-alternation violations" ~/.hermes/logs/agent.log
```

Hermes has an auto-repair feature that fixes alternation violations. If it reports `Repaired N message-alternation violations`, the history was cleaned up successfully.

## Resolution

1. **Fork the conversation** (creates a fresh message history from the same context)
2. **Start a new session** (`/new` or new `hermes` invocation) — the truncated history won't have orphan tool_calls
3. **Wait for the auto-repair** — Hermes logs `Repaired N message-alternation violations` when it fixes the issue automatically

## Prevention

- Avoid rapid message sending that could interrupt tool call execution
- When the WebUI shows a tool call in progress, wait for it to complete or time out before sending a new message
- If a session gets confused, forking (/fork) is faster than retrying

## Strictness by Provider

| Provider | Alternation Enforcement |
|---|---|
| **DeepSeek V4 Flash** (via OpenCode Go) | STRICT — rejects malformed alternation |
| **OpenAI** | Lenient — auto-fixes minor alternation issues |
| **Anthropic** | N/A — uses own message format, not OpenAI |

## Real Case: WebUI error June 2026

**Symptom**: User saw HTTP 400 in WebUI. Had to fork the conversation.

**Chain of events:**
1. A previous turn's tool calls were interrupted mid-execution (user navigated or sent new message)
2. History truncation left orphan tool_calls
3. Next API call hit DeepSeek's strict alternation check → 400
4. Hermes logged: `"Stored system prompt for session ... is null; rebuilding from scratch"`
5. User forked → new session with clean history → worked

**Takeaway**: The 400 is a symptom of a history integrity issue, not a provider outage. Fix the history (fork), not the provider config.
