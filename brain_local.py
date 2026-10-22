#!/usr/bin/env python3
"""Echo's OWN brain — local model via Ollama (added 2026-10-17).

Same contract as the Meta-backed brain module
(~/workspace/echo-brain-prep/echo_brain.py): reads stdin JSON
{"messages": [...]}, prints ONE JSON line
{"ok": true, "reply": "...", "model": "<local model name>"}.

Differences from the Meta brain: this one talks only to a local Ollama
runtime on this machine (http://127.0.0.1:11434). No account, no API
key, no credentials anywhere, nothing leaves the machine. It loads the
exact same system prompt file as the Meta brain, so Echo's identity and
rules are identical whichever brain is plugged in.

Usage:
  echo '{"messages": [{"role": "user", "content": "Hi"}]}' | python3 brain_local.py [--model qwen2.5:0.5b]
The model can also be set with the ECHO_LOCAL_MODEL environment variable.
"""
import json
import os
import sys
import urllib.request

PROMPT_FILE = os.path.join(
    os.path.expanduser("~"), "workspace", "echo-brain-prep", "echo_system_prompt.txt"
)
SYSTEM_PROMPT = open(PROMPT_FILE).read().strip()
OLLAMA_CHAT = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = os.environ.get("ECHO_LOCAL_MODEL", "qwen2.5:0.5b")


def ask_brain(messages, model=DEFAULT_MODEL):
    body = {
        "model": model,
        "stream": False,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        # Keep replies in Echo's short, plain style and bound the work:
        # this machine is small, so cap the answer length.
        "options": {"num_predict": 300},
    }
    req = urllib.request.Request(
        OLLAMA_CHAT,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # Generous timeout: a cold model load on this VM can take a while.
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read().decode("utf-8"))
    msg = data.get("message") or {}
    return {"ok": True, "reply": msg.get("content", "").strip(), "model": data.get("model", model)}


if __name__ == "__main__":
    model = DEFAULT_MODEL
    if "--model" in sys.argv:
        model = sys.argv[sys.argv.index("--model") + 1]
    payload = json.loads(sys.stdin.read())
    try:
        print(json.dumps(ask_brain(payload.get("messages", []), model=model)))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
