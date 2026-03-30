# small-fry

Small personal tools for the terminal.

## err

Explains your last shell command using a local LLM (llama.cpp). Run a command, then type `err` to get a short explanation of what happened. You can also type `err <question>` to ask a shell/CLI question directly.

**Requirements:** Python 3, [llama.cpp](https://github.com/ggml-org/llama.cpp) (`llama-server`), a GGUF model

**Setup:**
1. Copy `err.conf.example` to `err.conf` and set your `model_path`
2. Add `source /path/to/err/err.zsh` to your `~/.zshrc`

## lk

A terminal bookmark manager with a TUI — save folders, files, and URLs, then find and open them with fuzzy search.

**Requirements:** Python 3, [Textual](https://github.com/Textualize/textual), macOS (uses Finder integration)

**Setup:**
1. `pip install -r lk/requirements.txt`
2. Add `source /path/to/lk/lk.zsh` to your `~/.zshrc`

**Usage:**
- `lk /some/path` — save a folder or file
- `lk https://example.com` — save a URL
- `lk something` — search bookmarks and open the result
- `lk` — save current Finder path or search

Data is stored in `~/.lk/lk_data.json`.
