#!/usr/bin/env python3
"""err 0.3 — explains your last shell command or answers questions using a local llama.cpp model."""

import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── config ──────────────────────────────────────────────────────────

DEFAULTS = {
    "model_path": "",
    "prompt_success": "In 1 short sentence: what does this command do?",
    "prompt_fail": "In one or few short sentences: what went wrong? If it looks like a typo, say so.",
    "thinking": "off",
    "max_tokens": "100",
    "temperature": "0.7",
    "port": "8080",
    "gpu_layers": "99",
    "server_extra_flags": "",
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    conf_path = os.path.join(SCRIPT_DIR, "err.conf")
    if os.path.isfile(conf_path):
        with open(conf_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key in cfg:
                    cfg[key] = value
    return cfg


CFG = load_config()

LLAMA_HOST = f"http://localhost:{CFG['port']}"
LLAMA_BIN = os.environ.get("LLAMA_BIN", "llama-server")

# ── help ────────────────────────────────────────────────────────────

HELP = """\

ERR 0.3 // explains the last command or answers questions using a local LLM

Usage:
  err                  Explain the last command
  err <question>       Ask a shell/CLI question
  err -h|--help        Show this help

Exit codes explained:
  1     General error (catchall)
  2     Misuse of shell builtin
  126   Command found but not executable (permission denied)
  127   Command not found (typo, not installed, not in PATH)
  128   Invalid exit argument
  128+N Killed by signal N (e.g. 130 = Ctrl-C, 137 = SIGKILL, 139 = segfault)
  255   Exit status out of range

How it works:
  Run a command, then type `err`. It sends the command and exit code
  to a local llama.cpp server and streams a short explanation.
  Optionally capture stderr: some-cmd 2>/tmp/err_stderr; err

"""

# ── llama.cpp server management ─────────────────────────────────────


def health_ok() -> bool:
    try:
        req = urllib.request.Request(f"{LLAMA_HOST}/health", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return b'"ok"' in resp.read()
    except Exception:
        return False


def ensure_running() -> bool:
    if health_ok():
        return True

    if not CFG["model_path"]:
        print(
            "❌ model_path is not set. Edit err.conf next to err.py.",
            file=sys.stderr,
        )
        return False

    print("🚀 Starting llama.cpp server...")
    log = open("/tmp/llama_server.log", "w")

    cmd = [
        LLAMA_BIN,
        "--model", CFG["model_path"],
        "--host", "127.0.0.1",
        "--port", CFG["port"],
        "--no-mmap",
        "-ngl", CFG["gpu_layers"],
        "--jinja",
    ]

    if CFG["thinking"] == "off":
        cmd += ["--reasoning-budget", "0"]

    extra = CFG["server_extra_flags"].strip()
    if extra:
        cmd += shlex.split(extra)

    subprocess.Popen(cmd, stdout=log, stderr=log)

    for _ in range(30):
        time.sleep(1)
        if health_ok():
            print("✅ llama.cpp ready")
            return True

    print("❌ llama.cpp failed to start. Check /tmp/llama_server.log", file=sys.stderr)
    return False


# ── LLM call with streaming ────────────────────────────────────────


def stream_response(cmd: str, exit_code: int, stderr_content: str) -> None:
    if exit_code == 0:
        context = f"Shell command succeeded (exit 0): {cmd}"
        prompt = CFG["prompt_success"]
    else:
        context = f"Shell command failed with exit code {exit_code}: {cmd}"
        prompt = CFG["prompt_fail"]

    if stderr_content:
        context += f"\n\nError output:\n{stderr_content}"

    thinking = CFG["thinking"] == "on"

    payload = json.dumps(
        {
            "model": "local",
            "max_tokens": int(CFG["max_tokens"]),
            "temperature": float(CFG["temperature"]),
            "top_p": 0.8,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 1.5,
            "stream": True,
            "chat_template_kwargs": {"enable_thinking": thinking},
            "messages": [{"role": "user", "content": f"{context}\n\n{prompt}"}],
        }
    ).encode()

    req = urllib.request.Request(
        f"{LLAMA_HOST}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        print(delta, end="", flush=True)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
        print("\n")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err_msg = json.loads(body).get("error", body)
        except json.JSONDecodeError:
            err_msg = body
        print(f"\n❌ Server error ({e.code}): {err_msg}", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"\n❌ Connection failed: {e.reason}", file=sys.stderr)


# ── freeform question ─────────────────────────────────────────────


def stream_question(question: str) -> None:
    prompt = (
        "You are a concise shell/CLI assistant. "
        "Answer in a few short sentences. "
        "Include a brief example command if relevant."
    )

    payload = json.dumps(
        {
            "model": "local",
            "max_tokens": int(CFG["max_tokens"]),
            "temperature": float(CFG["temperature"]),
            "top_p": 0.8,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 1.5,
            "stream": True,
            "chat_template_kwargs": {"enable_thinking": CFG["thinking"] == "on"},
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ],
        }
    ).encode()

    req = urllib.request.Request(
        f"{LLAMA_HOST}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        print(delta, end="", flush=True)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
        print("\n")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err_msg = json.loads(body).get("error", body)
        except json.JSONDecodeError:
            err_msg = body
        print(f"\n❌ Server error ({e.code}): {err_msg}", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"\n❌ Connection failed: {e.reason}", file=sys.stderr)


# ── main ────────────────────────────────────────────────────────────


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
        print(HELP)
        return

    # freeform question mode: err <question...>
    if len(sys.argv) >= 2:
        question = " ".join(sys.argv[1:])
        print()
        if not ensure_running():
            sys.exit(1)
        stream_question(question)
        return

    # default mode: explain last command
    cmd = os.environ.get("_ERR_LAST_CMD", "")
    exit_code_str = os.environ.get("_ERR_LAST_EXIT", "0")

    if not cmd:
        print("No command recorded yet.", file=sys.stderr)
        sys.exit(1)

    exit_code = int(exit_code_str)

    print()
    if exit_code == 0:
        print(f"✅ {cmd} (exit 0)")
    else:
        print(f"💥 {cmd} (exit {exit_code})")

    if not ensure_running():
        sys.exit(1)

    stderr_content = ""
    stderr_file = "/tmp/err_stderr"
    if os.path.isfile(stderr_file) and os.path.getsize(stderr_file) > 0:
        with open(stderr_file) as f:
            stderr_content = f.read()

    stream_response(cmd, exit_code, stderr_content)


if __name__ == "__main__":
    main()
