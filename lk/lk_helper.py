#!/usr/bin/env python3
"""
LK v0.21 // bookmark folders, files, and URLs

Usage:
  lk                     Save current Finder path or search bookmarks
  lk /some/path          Save a folder or file
  lk https://example.com Save a URL
  lk something           Search bookmarks and open selected result
  lk -d | --data         Open JSON data file in Finder
  lk -e | --edit         Edit JSON data file in TextEdit
  lk -f | --form         Edit JSON data file in Terminal
  lk -h | --help         Show help

Behavior:
  - No args: grabs the Finder selection/window path, offers to save it
  - Files are revealed in Finder
  - Folders are opened in Finder
  - URLs are opened in the default browser
"""

import json
import os
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import unquote, urlparse

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, Static

DATA_FILE = Path.home() / ".lk" / "lk_data.json"


# --- Data helpers ---

def load():
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def persist(entries):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def normalize_path(path_str):
    if path_str.startswith("smb://"):
        parsed = urlparse(path_str)
        return "/Volumes" + unquote(parsed.path)
    return os.path.expanduser(path_str)


def resolve_stored(path_str):
    if path_str.startswith(("http://", "https://")):
        return path_str
    normalized = normalize_path(path_str)
    return str(Path(normalized).resolve())


def word_matches(word, haystack):
    if word in haystack:
        return True
    return any(
        SequenceMatcher(None, word, hw).ratio() >= 0.8 for hw in haystack.split()
    )


def filter_entries(query, entries, search_texts=None):
    if not query.strip():
        return entries
    words = query.lower().split()
    return [
        e
        for i, e in enumerate(entries)
        if all(
            word_matches(w, search_texts[i] if search_texts else f"{e['title']} {e.get('description', '')} {e['path']}".lower())
            for w in words
        )
    ]


def build_search_texts(entries):
    return [
        f"{e['title']} {e.get('description', '')} {e['path']}".lower()
        for e in entries
    ]


def open_path(path):
    if path.startswith(("http://", "https://")):
        subprocess.run(["/usr/bin/open", path])
    elif os.path.isfile(path):
        subprocess.run(["osascript", "-e", """
            on run argv
                set thePath to POSIX file (item 1 of argv) as alias
                tell application "Finder"
                    activate
                    set theFolder to container of thePath
                    if (count of Finder windows) > 0 then
                        tell application "System Events" to keystroke "t" using command down
                        delay 0.3
                        set target of front Finder window to theFolder
                        delay 0.1
                        select thePath
                    else
                        reveal thePath
                    end if
                end tell
            end run
        """, path])
    elif os.path.isdir(path):
        subprocess.run(["osascript", "-e", """
            on run argv
                set thePath to POSIX file (item 1 of argv)
                tell application "Finder"
                    activate
                    if (count of Finder windows) > 0 then
                        tell application "System Events" to keystroke "t" using command down
                        delay 0.3
                        set target of front Finder window to thePath
                    else
                        open thePath
                    end if
                end tell
            end run
        """, path])
    else:
        subprocess.run(["/usr/bin/open", path])


def get_finder_path():
    try:
        result = subprocess.run(
            ["osascript", "-e", """
                tell app "Finder"
                    set sel to selection
                    if sel is {} then
                        POSIX path of (target of front window as alias)
                    else
                        POSIX path of (item 1 of sel as alias)
                    end if
                end tell
            """],
            capture_output=True, text=True, timeout=3,
        )
        path = result.stdout.strip()
        return path if path else None
    except Exception:
        return None


# --- TUI Widgets ---

class SearchInput(Input):
    """Input that forwards arrow keys and enter to the app."""

    class Navigate(Message):
        def __init__(self, direction: int):
            super().__init__()
            self.direction = direction

    class Submit(Message):
        pass

    class EditBookmark(Message):
        pass

    class DeleteBookmark(Message):
        pass

    class MultiPick(Message):
        pass

    def _on_key(self, event):
        if event.key == "down":
            event.prevent_default()
            event.stop()
            self.post_message(self.Navigate(1))
        elif event.key == "up":
            event.prevent_default()
            event.stop()
            self.post_message(self.Navigate(-1))
        elif event.key == "enter":
            event.prevent_default()
            event.stop()
            self.post_message(self.Submit())
        elif event.key == "ctrl+e":
            event.prevent_default()
            event.stop()
            self.post_message(self.EditBookmark())
        elif event.key == "ctrl+d":
            event.prevent_default()
            event.stop()
            self.post_message(self.DeleteBookmark())
        elif event.key == "ctrl+o":
            event.prevent_default()
            event.stop()
            self.post_message(self.MultiPick())
        else:
            super()._on_key(event)

class BookmarkItem(Static):
    DEFAULT_CSS = """
    BookmarkItem {
        padding: 0 2;
        height: auto;
        margin-bottom: 1;
    }
    BookmarkItem:hover {
        background: $surface-lighten-1;
    }
    BookmarkItem.--selected {
        background: $accent 30%;
    }
    """

    def __init__(self, entry, index, mark=None, mode=None):
        super().__init__()
        self.entry = entry
        self.index = index
        self.mark = mark  # None=normal, True=marked, False=unmarked
        self.mode = mode  # "delete", "multi", or None

    def _render_text(self):
        title = self.entry["title"]
        desc = self.entry.get("description", "")
        path = self.entry["path"]
        if self.mark is not None:
            if self.mark:
                indicator = "[bold red]✕[/bold red]" if self.mode == "delete" else "[bold green]✓[/bold green]"
            else:
                indicator = "[dim]·[/dim]"
            lines = f" {indicator}  [bold]{title}[/bold]"
        else:
            lines = f"[bold]{self.index + 1}[/bold]  [bold]{title}[/bold]"
        if desc:
            lines += f"\n    [dim]{desc}[/dim]"
        lines += f"\n    [dim italic]{path}[/dim italic]"
        return lines

    def compose(self):
        yield Static(self._render_text(), markup=True, id=f"bm-label-{self.index}")

    def set_mark(self, mark):
        self.mark = mark
        self.query_one(f"#bm-label-{self.index}", Static).update(self._render_text())


class MenuItem(Static):
    DEFAULT_CSS = """
    MenuItem {
        padding: 0 2;
        height: 1;
    }
    MenuItem:hover {
        background: $surface-lighten-1;
    }
    MenuItem.--selected {
        background: $accent 30%;
    }
    """

    def __init__(self, label, value):
        super().__init__(label, markup=True)
        self.value = value


# --- Save App ---

class SaveApp(App):
    TITLE = "lk - save"

    CSS = """
    Screen { background: $background; }
    #header { margin: 1 2; height: auto; }
    #form { margin: 1 2; height: auto; }
    #form Input { margin-bottom: 1; }
    #status { dock: bottom; height: 1; padding: 0 2; color: $text-muted; }
    """

    BINDINGS = [
        Binding("escape", "quit", "Exit", show=False),
    ]

    def __init__(self, stored_path, existing=None):
        super().__init__()
        self.stored_path = stored_path
        self.existing = existing
        self.result_title = None
        self.result_description = None
        self.result_path = None

    def compose(self) -> ComposeResult:
        if self.existing:
            yield Static(
                f"[bold yellow]Editing bookmark[/bold yellow]",
                id="header", markup=True,
            )
        else:
            yield Static(f"[bold]Saving:[/bold] [dim]{self.stored_path}[/dim]", id="header", markup=True)
        with Vertical(id="form"):
            if self.existing:
                yield Input(
                    placeholder="Path / URL",
                    value=self.stored_path,
                    id="path",
                )
            yield Input(
                placeholder="Title (required)",
                value=self.existing["title"] if self.existing else "",
                id="title",
            )
            yield Input(
                placeholder="Description (optional)",
                value=self.existing.get("description", "") if self.existing else "",
                id="description",
            )
        yield Static("  enter confirm   esc cancel", id="status")

    def on_mount(self):
        if self.existing:
            self.query_one("#path", Input).focus()
        else:
            self.query_one("#title", Input).focus()

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "path":
            self.query_one("#title", Input).focus()
        elif event.input.id == "title":
            title = event.value.strip()
            if title:
                self.query_one("#description", Input).focus()
        elif event.input.id == "description":
            title = self.query_one("#title", Input).value.strip()
            if title:
                self.result_title = title
                self.result_description = event.value.strip()
                if self.existing:
                    self.result_path = self.query_one("#path", Input).value.strip()
                self.exit()

    def action_quit(self):
        self.exit()


# --- Search App ---

class SearchApp(App):
    TITLE = "lk"

    CSS = """
    Screen { background: $background; }
    #search { dock: top; margin: 1 2 0 2; }
    #results { margin: 1 0; }
    #status { dock: bottom; height: 1; padding: 0 2; color: $text-muted; }
    """

    BINDINGS = [
        Binding("escape", "quit", "Exit", show=False),
    ]

    MAX_VISIBLE = 50

    selected_index = reactive(0)

    def __init__(self, all_entries, initial_query=""):
        super().__init__()
        self.all_entries = all_entries
        self.initial_query = initial_query
        self._search_texts = build_search_texts(all_entries)
        self.matches = filter_entries(initial_query, all_entries, self._search_texts)
        self._last_query = initial_query.strip()
        self._filter_timer = None
        self.chosen_path = None
        self.chosen_paths = None
        self.edit_entry = None
        # modal mode state: "delete", "multi", or None
        self._mode = None
        self._marked = set()
        self._confirming = False

    def compose(self) -> ComposeResult:
        yield SearchInput(placeholder="Search bookmarks...", value=self.initial_query, id="search")
        yield VerticalScroll(id="results")
        yield Static("", id="status")

    def on_mount(self):
        self.query_one("#search", SearchInput).focus()
        self._refresh_results()

    # --- key handling: modal modes intercept all keys ---

    def on_key(self, event):
        if not self._mode:
            return
        key = event.key
        event.stop()
        event.prevent_default()
        n = min(len(self.matches), self.MAX_VISIBLE)
        if key == "down" and n:
            self.selected_index = (self.selected_index + 1) % n
        elif key == "up" and n:
            self.selected_index = (self.selected_index - 1) % n
        elif key == "space" and not self._confirming and n:
            idx = self.selected_index
            if idx in self._marked:
                self._marked.discard(idx)
            else:
                self._marked.add(idx)
            items = self.query("BookmarkItem")
            if 0 <= idx < len(items):
                items[idx].set_mark(idx in self._marked)
            self._update_status()
        elif key == "enter" and self._marked:
            if self._mode == "delete":
                if not self._confirming:
                    self._confirming = True
                    self._update_status()
                else:
                    self._do_delete()
            elif self._mode == "multi":
                self._do_multi_open()
        elif key == "escape":
            if self._confirming:
                self._confirming = False
                self._update_status()
            else:
                self._exit_mode()

    # --- search mode handlers ---

    def on_search_input_navigate(self, event: SearchInput.Navigate):
        if self.matches:
            self.selected_index = (self.selected_index + event.direction) % len(self.matches)

    def on_search_input_submit(self, event: SearchInput.Submit):
        if self.matches and 0 <= self.selected_index < len(self.matches):
            self.chosen_path = self.matches[self.selected_index]["path"]
            self.exit()

    def on_search_input_edit_bookmark(self, event: SearchInput.EditBookmark):
        if self.matches and 0 <= self.selected_index < len(self.matches):
            self.edit_entry = self.matches[self.selected_index]
            self.exit()

    def on_search_input_delete_bookmark(self, event: SearchInput.DeleteBookmark):
        if self.matches:
            self._enter_mode("delete")

    def on_search_input_multi_pick(self, event: SearchInput.MultiPick):
        if self.matches:
            self._enter_mode("multi")

    def on_input_changed(self, event: Input.Changed):
        if self._filter_timer is not None:
            self._filter_timer.stop()
        self._pending_query = event.value.strip()
        self._filter_timer = self.set_timer(0.15, self._do_filter)

    def _do_filter(self):
        q = self._pending_query
        if q and self._last_query and q.startswith(self._last_query):
            source = self.matches
            texts = build_search_texts(source)
        else:
            source = self.all_entries
            texts = self._search_texts
        self.matches = filter_entries(q, source, texts)
        self._last_query = q
        self.selected_index = 0
        self._refresh_results()

    # --- modal modes (delete / multi-pick) ---

    def _enter_mode(self, mode):
        self._mode = mode
        self._marked = set()
        self._confirming = False
        self.query_one("#search", SearchInput).disabled = True
        self._refresh_results()

    def _exit_mode(self):
        self._mode = None
        self._marked = set()
        self._confirming = False
        search = self.query_one("#search", SearchInput)
        search.disabled = False
        search.focus()
        self._refresh_results()

    def _do_delete(self):
        paths_to_delete = {self.matches[i]["path"] for i in self._marked}
        self.all_entries = [e for e in self.all_entries if e["path"] not in paths_to_delete]
        persist(self.all_entries)
        self._search_texts = build_search_texts(self.all_entries)
        q = self.query_one("#search", SearchInput).value.strip()
        self.matches = filter_entries(q, self.all_entries, self._search_texts)
        self._last_query = q
        self.selected_index = 0
        self._exit_mode()

    def _do_multi_open(self):
        self.chosen_paths = [self.matches[i]["path"] for i in sorted(self._marked)]
        self.exit()

    # --- display ---

    def watch_selected_index(self, value):
        self._highlight()

    def _refresh_results(self):
        container = self.query_one("#results", VerticalScroll)
        container.remove_children()
        visible = self.matches[:self.MAX_VISIBLE]
        for i, entry in enumerate(visible):
            mark = (i in self._marked) if self._mode else None
            container.mount(BookmarkItem(entry, i, mark=mark, mode=self._mode))
        self.call_after_refresh(self._highlight)
        self._update_status()

    def _update_status(self):
        status = self.query_one("#status", Static)
        matched = len(self.matches)
        total = len(self.all_entries)
        if self._mode == "delete":
            n = len(self._marked)
            if self._confirming:
                status.update(f" [bold red]Delete {n} bookmark{'s' if n != 1 else ''}?[/bold red]   enter confirm   esc cancel")
            else:
                sel = f"  [bold]{n} selected[/bold]" if n else ""
                status.update(f" ↑↓ navigate   space toggle   enter delete{sel}   esc back")
        elif self._mode == "multi":
            n = len(self._marked)
            sel = f"  [bold]{n} selected[/bold]" if n else ""
            status.update(f" ↑↓ navigate   space toggle   enter open all{sel}   esc back")
        else:
            if matched > self.MAX_VISIBLE:
                status.update(f" showing {self.MAX_VISIBLE} of {matched} matches ({total} total)   ↑↓ enter open   ^e edit   ^d delete   ^o multi   esc quit")
            else:
                status.update(f" {matched}/{total} bookmarks   ↑↓ enter open   ^e edit   ^d delete   ^o multi   esc quit")

    def _highlight(self):
        items = self.query("BookmarkItem")
        for i, item in enumerate(items):
            if i == self.selected_index:
                item.add_class("--selected")
                item.scroll_visible()
            else:
                item.remove_class("--selected")

    def action_quit(self):
        if self._mode:
            self._exit_mode()
        else:
            self.exit()


# --- Help App ---

HELP_TEXT = __doc__.strip()

class HelpApp(App):
    TITLE = "lk - help"

    CSS = """
    Screen { background: $background; }
    #help { margin: 1 2; height: auto; }
    #status { dock: bottom; height: 1; padding: 0 2; color: $text-muted; }
    """

    BINDINGS = [
        Binding("escape", "quit", "Exit", show=False),
        Binding("enter", "quit", "Exit", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Static(HELP_TEXT, id="help")
        yield Static("  enter/esc close", id="status")

    def action_quit(self):
        self.exit()


# --- Chooser App (for no-args with Finder path) ---

class ChooserApp(App):
    TITLE = "lk"

    CSS = """
    Screen { background: $background; }
    #header { margin: 1 2; height: auto; }
    #menu { margin: 1 2; height: auto; }
    #status { dock: bottom; height: 1; padding: 0 2; color: $text-muted; }
    """

    BINDINGS = [
        Binding("escape", "quit", "Exit", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("enter", "select", "Select", show=False),
    ]

    selected_index = reactive(0)

    def __init__(self, finder_path=None):
        super().__init__()
        self.finder_path = finder_path
        self.choice = None
        self.options = []
        if finder_path:
            self.options.append(("  [bold]Save this path[/bold]", "save"))
        self.options.extend([
            ("  [bold]Search bookmarks[/bold]", "search"),
            ("  [dim]Help[/dim]", "help"),
            ("  [dim]Exit[/dim]", "exit"),
        ])

    def compose(self) -> ComposeResult:
        if self.finder_path:
            yield Static(
                f"\n  [bold]Finder path:[/bold] [dim]{self.finder_path}[/dim]\n",
                id="header", markup=True,
            )
        else:
            yield Static(
                f"\n  [dim]No Finder path selected[/dim]\n",
                id="header", markup=True,
            )
        with Vertical(id="menu"):
            for label, value in self.options:
                yield MenuItem(label, value)
        yield Static("  ↑↓ navigate   enter select   esc quit", id="status")

    def on_mount(self):
        self._highlight()

    def watch_selected_index(self, value):
        self._highlight()

    def _highlight(self):
        items = self.query("MenuItem")
        for i, item in enumerate(items):
            if i == self.selected_index:
                item.add_class("--selected")
            else:
                item.remove_class("--selected")

    def action_move_down(self):
        self.selected_index = (self.selected_index + 1) % len(self.options)

    def action_move_up(self):
        self.selected_index = (self.selected_index - 1) % len(self.options)

    def action_select(self):
        self.choice = self.options[self.selected_index][1]
        self.exit()

    def action_quit(self):
        self.exit()


# --- Commands ---

def cmd_add(path_str):
    stored = resolve_stored(path_str)

    entries = load()
    existing = None
    for e in entries:
        if e["path"] == stored:
            existing = e
            break

    app = SaveApp(stored, existing=existing)
    app.run()

    if app.result_title:
        if existing:
            existing["title"] = app.result_title
            existing["description"] = app.result_description or ""
            persist(entries)
            print(f"Updated: {app.result_title}", file=sys.stderr)
        else:
            entries.append({
                "path": stored,
                "title": app.result_title,
                "description": app.result_description or "",
            })
            persist(entries)
            print(f"Saved: {app.result_title}", file=sys.stderr)
    else:
        print("Cancelled.", file=sys.stderr)


def cmd_search(query=""):
    while True:
        entries = load()
        if not entries:
            print("No entries yet. Add one with: lk /some/path", file=sys.stderr)
            sys.exit(1)

        app = SearchApp(entries, initial_query=query)
        app.run()

        if app.chosen_path:
            open_path(app.chosen_path)
            break
        elif app.chosen_paths:
            for p in app.chosen_paths:
                open_path(p)
            break
        elif app.edit_entry:
            entry = app.edit_entry
            existing = None
            for e in entries:
                if e["path"] == entry["path"]:
                    existing = e
                    break
            if existing:
                save = SaveApp(existing["path"], existing=existing)
                save.run()
                if save.result_title:
                    existing["title"] = save.result_title
                    existing["description"] = save.result_description or ""
                    if save.result_path and save.result_path != existing["path"]:
                        existing["path"] = resolve_stored(save.result_path)
                    persist(entries)
            query = ""
            continue
        else:
            break


def cmd_noargs():
    finder_path = get_finder_path()

    chooser = ChooserApp(finder_path)
    chooser.run()

    if chooser.choice == "save" and finder_path:
        cmd_add(finder_path)
    elif chooser.choice == "search":
        cmd_search()
    elif chooser.choice == "help":
        cmd_help()


def cmd_help():
    app = HelpApp()
    app.run()


def cmd_data():
    if DATA_FILE.exists():
        subprocess.run(["/usr/bin/open", "-R", str(DATA_FILE)])
    else:
        print("No data file found.", file=sys.stderr)


def cmd_edit():
    subprocess.run(["/usr/bin/open", "-a", "TextEdit", str(DATA_FILE)])


def cmd_form():
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(DATA_FILE)])


# --- Main ---

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        cmd_noargs()
        sys.exit(0)

    input_str = " ".join(args)

    if input_str in ("-h", "--help"):
        cmd_help()
    elif input_str in ("-d", "--data"):
        cmd_data()
    elif input_str in ("-e", "--edit"):
        cmd_edit()
    elif input_str in ("-f", "--form"):
        cmd_form()
    elif input_str.startswith(("http://", "https://", "smb://", "/", "./", "../", "~")):
        cmd_add(input_str)
    else:
        cmd_search(input_str)
