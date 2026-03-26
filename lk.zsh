lk() {
  case "$1" in
    -h|--help)
      nano ~/.lk/README.md
      ;;
    -d|--data)
      nano ~/.lk/lk_data.json
      ;;
    *)
      python3 ~/.lk/lk_helper.py "$@" </dev/tty >/dev/tty
      ;;
  esac
}