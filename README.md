# Local LLM Router

Routes prompts to a local Ollama model first, with an optional fallback to cloud providers. Works on Termux/Android, macOS, Linux.

```bash
pip install -e .
llm-router config local_model qwen2.5:1.5b
llm-router test
llm-router "Summarize my last session"
```

## Why this exists
- Offline-first on Termux
- Same entrypoint (`llm-router`) everywhere
- Pure stdlib, no unnecessary deps

## Install

Clone or download this repo, then:

```bash
pip install -e .
```

Requires Python 3.9+.

## Commands

```bash
llm-router config
llm-router config local_model qwen2.5:1.5b
llm-router config system_prompt "You are Jarvis-lite."

# Fallback (OpenAI-compatible; replace with your real key)
llm-router config fallback direct stepfun/step-2-16k https://api.stepfun.com/v1/chat/completions sk-...

llm-router test
llm-router "Pick one: fight 1 goose or 100 duck-sized horses?"
llm-router history
llm-router clear
```

## Routing rules

1. Use local Ollama when `localhost:11434` is reachable
2. Otherwise use the configured fallback
3. If neither is available, return a clear failure

## State

- Config in `~/.llm-router.json`
- Session history in `~/.llm-router/session.db`
