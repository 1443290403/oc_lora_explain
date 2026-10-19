#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == "--python" ]]; then
    [[ $# -ge 2 ]] || { echo "--python needs an interpreter path" >&2; exit 2; }
    helper_python="$2"
    shift 2
elif command -v python3.12 >/dev/null 2>&1; then
    helper_python=python3.12
elif command -v python3 >/dev/null 2>&1; then
    helper_python=python3
else
    echo "Install Python 3.12 with venv support or activate a Python 3.12 Conda environment." >&2
    exit 2
fi
exec "$helper_python" -X utf8 "$script_dir/bootstrap.py" "$@"
