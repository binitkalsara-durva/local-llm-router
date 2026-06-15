#!/usr/bin/env python3
"""
Local LLM Router
Routes prompts to local Ollama models first, with optional cloud fallback.
Designed for Termux/Android but works anywhere.
"""

import json
import sys
import sqlite3
import subprocess
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

CONFIG_PATH = Path.home() / ".llm-router.json"
DB_PATH = Path.home() / ".llm-router" / "session.db"
MAX_HISTORY = 20


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {
        "local_model": "qwen2.5:1.5b",
        "ollama_url": "http://localhost:11434",
        "fallback": None,
        "system_prompt": "You are a helpful assistant."
    }


def save_config(config: dict):
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            model_used TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def append_message(conn: sqlite3.Connection, role: str, content: str, model_used: Optional[str]):
    conn.execute(
        "INSERT INTO messages (ts, role, content, model_used) VALUES (?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), role, content, model_used)
    )
    conn.commit()


def get_recent(conn: sqlite3.Connection, limit: int = MAX_HISTORY) -> List[Dict]:
    cur = conn.execute(
        "SELECT id, role, content, model_used FROM messages ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = [{"id": r[0], "role": r[1], "content": r[2], "model_used": r[3]} for r in cur.fetchall()]
    return list(reversed(rows))


def clear_history(conn: sqlite3.Connection):
    conn.execute("DELETE FROM messages")
    conn.commit()


def is_ollama_running() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434", timeout=2)
        return True
    except Exception:
        return False


def run_local(prompt: str, config: dict) -> Optional[str]:
    if not is_ollama_running():
        return None
    try:
        import urllib.request
        payload = json.dumps({
            "model": config["local_model"],
            "prompt": prompt,
            "system": config.get("system_prompt", ""),
            "stream": False
        }).encode()
        req = urllib.request.Request(
            f"{config['ollama_url']}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data.get("response", "")
    except Exception:
        return None


def run_fallback(prompt: str, config: dict) -> Optional[str]:
    if not config.get("fallback"):
        return None
    fb = config["fallback"]
    try:
        import urllib.request
        if fb.get("provider") == "openrouter":
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {fb['api_key']}"}
            payload = json.dumps({
                "model": fb["model"],
                "messages": [
                    {"role": "system", "content": config.get("system_prompt", "")},
                    *[{"role": m["role"], "content": m["content"]} for m in (fb.get("history") or [])],
                    {"role": "user", "content": prompt}
                ]
            }).encode()
        elif fb.get("provider") == "direct":
            url = fb.get("base_url", "https://api.nousresearch.com/v1/chat/completions")
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {fb['api_key']}"}
            payload = json.dumps({
                "model": fb["model"],
                "messages": [
                    {"role": "system", "content": config.get("system_prompt", "")},
                    *[{"role": m["role"], "content": m["content"]} for m in (fb.get("history") or [])],
                    {"role": "user", "content": prompt}
                ]
            }).encode()
        else:
            return None
        req = urllib.request.Request(url, data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def chat(prompt: str, continue_mode: bool = True):
    config = load_config()
    conn = init_db()
    history = []
    model_used = None

    if continue_mode:
        history = get_recent(conn)
        history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history)
        full_prompt = f"{history_text}\nuser: {prompt}"
    else:
        full_prompt = prompt

    print("→ Trying local model...")
    out = run_local(full_prompt, config)
    if out:
        model_used = config["local_model"]
        print(f"[local:{model_used}] {out}")
        append_message(conn, "user", prompt, model_used)
        append_message(conn, "assistant", out, model_used)
        conn.close()
        return

    print("→ Local unavailable. Trying fallback...")
    out = run_fallback(full_prompt, config)
    if out:
        model_used = config.get("fallback", {}).get("model", "fallback")
        print(f"[fallback:{model_used}] {out}")
        append_message(conn, "user", prompt, model_used)
        append_message(conn, "assistant", out, model_used)
        conn.close()
        return

    print("✗ No backend available. Run Ollama or set a fallback.")
    conn.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: llm-router <prompt> | llm-router config | llm-router test | llm-router history | llm-router clear")
        return

    cmd = sys.argv[1]
    if cmd == "config":
        if len(sys.argv) > 2:
            key = sys.argv[2]
            val = sys.argv[3] if len(sys.argv) > 3 else ""
            cfg = load_config()
            if key in ("local_model", "ollama_url", "system_prompt"):
                cfg[key] = val
            elif key == "fallback":
                provider = sys.argv[2]
                model = sys.argv[3] if len(sys.argv) > 3 else ""
                base_url = sys.argv[4] if len(sys.argv) > 4 else ""
                api_key = sys.argv[5] if len(sys.argv) > 5 else ""
                cfg["fallback"] = {
                    "provider": "direct",
                    "model": model,
                    "base_url": base_url,
                    "api_key": api_key
                }
                save_config(cfg)
                print(f"Set fallback = {provider} | {model} | {base_url}")
                return
            save_config(cfg)
            print(f"Set {key} = {val}")
        else:
            print(json.dumps(load_config(), indent=2))

    elif cmd == "test":
        print("Checking backends...")
        print(f"Ollama running: {is_ollama_running()}")
        chat("Say 'OK' if you can hear me.")

    elif cmd == "history":
        conn = init_db()
        rows = get_recent(conn, 50)
        conn.close()
        if not rows:
            print("No history yet.")
        for r in rows:
            print(f"{r['id']:>4} | {r['ts'][:19]} | {r['role']:<9} | {r['content'][:80]}")

    elif cmd == "clear":
        conn = init_db()
        clear_history(conn)
        conn.close()
        print("History cleared.")

    else:
        chat(" ".join(sys.argv[1:]))


if __name__ == "__main__":
    main()
