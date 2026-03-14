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
    if [[ -n "$manual" && -d "$manual" ]] && is_repo_dir "$manual"; then
      break
    fi
    echo "Caminho invalido. Tente novamente."
  done
  if { [[ -e "$CONFIG_PATH" && -w "$CONFIG_PATH" ]] || [[ -w "$(dirname "$CONFIG_PATH")" ]]; }; then
    printf '%s' "$manual" > "$CONFIG_PATH"
  else
    echo "Aviso: sem permissao para salvar $CONFIG_PATH; usando apenas nesta execucao."
  fi
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

  cd "$repo"
  if command -v uv >/dev/null 2>&1; then
    exec uv run --python "$py" python tools/run_min_compare_report.py
  else
    exec "$py" tools/run_min_compare_report.py
  fi
}

main "$@"
