# Local LLM Router

Routes prompts to a local Ollama model first, with an optional fallback to another provider. Works on Termux/Android, macOS, Linux.

## Setup

```bash
cd ~/local-llm-router
llm-router test
```

## Commands

```bash
llm-router config
llm-router config local_model qwen2.5:1.5b
llm-router config system_prompt "You are Jarvis-lite."

# Fallback (Nous / Stepfun / any OpenAI-compatible API)
llm-router config fallback direct stepfun/step-2-16k https://api.stepfun.com/v1/chat/completions sk-...
```

## Routing
- Local first when Ollama is reachable on `localhost:11434`
- Then fallback if configured
- No third-party dependencies beyond Python stdlib

## Notes
- For `direct` fallback, `base_url` must end in `/chat/completions` unless the provider uses a custom path.
