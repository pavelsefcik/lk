# err 0.3 — thin shell shim (hooks + Python handoff)
# Configuration lives in err.conf next to this file.

_err_last_cmd=""
_err_last_exit=0

_err_preexec() {
  [[ "$1" == "err" ]] && return
  _err_last_cmd="$1"
}

_err_precmd() {
  _err_last_exit=$?
}

if [[ -n "$ZSH_VERSION" ]]; then
  preexec_functions+=(_err_preexec)
  precmd_functions=(_err_precmd "${precmd_functions[@]}")
elif [[ -n "$BASH_VERSION" ]]; then
  trap '[[ "$BASH_COMMAND" != "err" ]] && _err_last_cmd="$BASH_COMMAND"' DEBUG
  PROMPT_COMMAND="_err_precmd${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
fi

_ERR_PY="${0:A:h}/err.py"

err() {
  _ERR_LAST_CMD="$_err_last_cmd" _ERR_LAST_EXIT="$_err_last_exit" \
    python3 "$_ERR_PY" "$@"
}
