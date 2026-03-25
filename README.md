# lk

A minimal bookmarking tool for the terminal — save folders, files, and URLs, then find and open them with a fuzzy search.

## What it does

- `lk /some/path` — save a folder or file with a title and description
- `lk https://example.com` — save a URL bookmark
- `lk something` — search your saved bookmarks and open the chosen one

Supports regular paths, `~` paths, `smb://` network share URLs, and `http(s)://` URLs.

When opening a **file**, Finder reveals it in its containing folder. When opening a **folder**, Finder opens it directly. When opening a **URL**, it opens in your default browser.

## Setup

### 1. Copy the files to `~/.lk`

```bash
mkdir -p ~/.lk
cp lk_helper.py ~/.lk/
cp lk.zsh ~/.lk/
```

### 2. Add one line to `~/.zshrc`

```zsh
source ~/.lk/lk.zsh
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
```
Saving: /Volumes/Work/Projects/MyProject
Title: My Project
Description (optional): Main working folder
Saved: My Project
```

**Save a URL:**
```
lk https://github.com/pavelsefcik/lk
```
```
Saving: https://github.com/pavelsefcik/lk
Title: GitHub lk
Description (optional): lk repository
Saved: GitHub lk
```

**Search and open:**
```
lk project
```
```
  Results for project

  1  My Project
     Main working folder
     /Volumes/Work/Projects/MyProject

  Pick: 1
```
Finder opens the chosen folder.

Search is fuzzy — `lk proejct` or `lk work models` will still find the right entry.

## Data

Bookmarks are stored in `~/.lk/lk_data.json` — plain JSON, easy to back up or edit by hand.

To open it directly: `lk_data`

## Dependencies

- Python 3 (already on your Mac)
- No pip installs required
