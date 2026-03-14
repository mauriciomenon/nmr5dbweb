#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="${HOME}/.nmr5dbweb_repo"

is_repo_dir() {
  local p="$1"
  [[ -f "$p/main.py" && -f "$p/pyproject.toml" ]]
}

find_repo_from() {
  local p="$1"
  while [[ "$p" != "/" ]]; do
    if is_repo_dir "$p"; then
      echo "$p"
      return 0
    fi
    p="$(dirname "$p")"
  done
  return 1
}

resolve_repo() {
  local script_dir
  script_dir="$(cd "$(dirname "$0")" && pwd)"

  if [[ -n "${NMR5DBWEB_REPO:-}" ]] && is_repo_dir "${NMR5DBWEB_REPO}"; then
    echo "${NMR5DBWEB_REPO}"
    return 0
  fi

  if [[ -f "$CONFIG_PATH" ]]; then
    local saved
    saved="$(cat "$CONFIG_PATH" 2>/dev/null || true)"
    if [[ -n "$saved" ]] && is_repo_dir "$saved"; then
      echo "$saved"
      return 0
    fi
  fi

  if find_repo_from "$script_dir" >/dev/null 2>&1; then
    find_repo_from "$script_dir"
    return 0
  fi

  if find_repo_from "$(pwd)" >/dev/null 2>&1; then
    find_repo_from "$(pwd)"
    return 0
  fi

  echo "Repo nao encontrado automaticamente."
  local manual=""
  while true; do
    read -r -p "Digite o caminho absoluto do repo nmr5dbweb: " manual
    if [[ "$manual" = /* ]] && [[ -n "$manual" ]] && is_repo_dir "$manual"; then
      break
    fi
    echo "Caminho invalido. Informe um caminho absoluto."
  done
  printf '%s' "$manual" > "$CONFIG_PATH"
  echo "$manual"
}

pick_python() {
  local repo="$1"
  if [[ -x "$repo/.venv/bin/python" ]]; then
    echo "$repo/.venv/bin/python"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  echo "Python nao encontrado." >&2
  exit 3
}

main() {
  local repo
  repo="$(resolve_repo)"
  local py
  py="$(pick_python "$repo")"
  local port
  port="$($py - <<'PY'
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
)"

  local url="http://127.0.0.1:${port}"
  echo "Repo: $repo"
  echo "URL: $url"
  echo "Escolha navegador: [1] padrao [2] custom"
  read -r -p "> " browser_choice
  if [[ "$browser_choice" == "2" ]]; then
    read -r -p "Caminho do navegador custom (app/exe): " custom_path
    if [[ -n "$custom_path" ]]; then
      open -a "$custom_path" "$url" || open "$url" || true
    else
      open "$url" || true
    fi
  else
    open "$url" || true
  fi

  cd "$repo"
  if command -v uv >/dev/null 2>&1; then
    exec uv run --python "$py" python main.py --host 127.0.0.1 --port "$port" --no-port-fallback
  else
    exec "$py" main.py --host 127.0.0.1 --port "$port" --no-port-fallback
  fi
}

main "$@"
