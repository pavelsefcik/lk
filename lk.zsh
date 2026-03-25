lk() {
  python3 ~/.lk/lk_helper.py "$@" </dev/tty >/dev/tty
  if [[ -f ~/.lk/lk_result ]]; then
    open "$(cat ~/.lk/lk_result)"
    rm ~/.lk/lk_result
  fi
}

alias lk_data="nano ~/.lk/lk_data.json"