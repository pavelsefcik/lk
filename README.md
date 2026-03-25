# lk

A minimal folder bookmarking tool for the terminal.

## What it does

- `lk /some/path` — save a folder with a title and description
- `lk something` — search your saved folders and open the chosen one in Finder

## Setup

### 1. Copy the helper script to your home folder

```bash
cp /path/to/lk_helper.py ~/.lk_helper.py
```

The file can be copied from anywhere — Downloads, Desktop, wherever you saved it.

### 2. Add the following to your `~/.zshrc`

```zsh
lk() {
  local arg="$*"

  if [[ "$arg" == /* ]] || [[ "$arg" == ~* ]] || [[ "$arg" == Users/* ]] || [[ "$arg" == Volumes/* ]]; then
    python3 ~/.lk_helper.py add "$arg"
  else
    rm -f ~/.lk_result
    python3 ~/.lk_helper.py search "$arg" </dev/tty >/dev/tty
    if [[ -f ~/.lk_result ]]; then
      open "$(cat ~/.lk_result)"
      rm ~/.lk_result
    fi
  fi
}
```

### 3. Reload your shell

```bash
source ~/.zshrc
```

## Usage

**Save a folder:**
```
lk /Volumes/Work/Projects/MyProject
```
You will be prompted:
```
Saving: /Volumes/Work/Projects/MyProject
Title: My Project
Description (optional): Main working folder
Saved: My Project
```

**Search and open:**
```
lk project
```
```
  Results for: project

  1)  My Project
      Main working folder
      /Volumes/Work/Projects/MyProject

  Pick: 1
```
Finder opens the chosen folder.

## Data

Your bookmarks are stored in `~/.lk_data.json` — plain JSON, human-readable, easy to back up or edit by hand.

## Dependencies

- Python 3 (already on your Mac)
- No pip installs required
