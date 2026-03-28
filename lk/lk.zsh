# lk v0.21 - terminal bookmarking with TUI

# noglob prevents zsh from expanding glob characters (e.g. ? in URLs)
# before passing arguments to the function
_LK_DIR="${0:A:h}"
_lk() {
  python3 "$_LK_DIR/lk_helper.py" "$@" </dev/tty >/dev/tty
}
alias lk='noglob _lk'
