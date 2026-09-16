#!/usr/bin/env sh
set -eu

scope=user
project=
codex_home=
mode=

usage() {
    printf '%s\n' 'Usage: ./install.sh [--dry-run|--apply] [--scope user|project] [--project PATH] [--codex-home PATH]'
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run)
            [ -z "$mode" ] || { printf '%s\n' 'Choose --apply or --dry-run, not both.' >&2; exit 2; }
            mode=--dry-run
            ;;
        --apply)
            [ -z "$mode" ] || { printf '%s\n' 'Choose --apply or --dry-run, not both.' >&2; exit 2; }
            mode=--apply
            ;;
        --scope)
            [ "$#" -ge 2 ] || { usage >&2; exit 2; }
            scope=$2
            shift
            [ "$scope" = user ] || [ "$scope" = project ] || { printf '%s\n' '--scope must be user or project' >&2; exit 2; }
            ;;
        --project)
            [ "$#" -ge 2 ] || { usage >&2; exit 2; }
            project=$2
            shift
            ;;
        --codex-home)
            [ "$#" -ge 2 ] || { usage >&2; exit 2; }
            codex_home=$2
            shift
            ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

if [ "$scope" = project ] && [ -z "$project" ]; then
    printf '%s\n' '--project is required when --scope project is selected' >&2
    exit 2
fi

[ -n "$mode" ] || mode=--dry-run

if command -v python3 >/dev/null 2>&1; then
    python_command=python3
elif command -v python >/dev/null 2>&1; then
    python_command=python
else
    printf '%s\n' 'Python 3.10 or newer is required. Install Python, then run this script again.' >&2
    exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
set -- -X utf8 "$script_dir/scripts/install.py" --scope "$scope"
[ -n "$project" ] && set -- "$@" --project "$project"
[ -n "$codex_home" ] && set -- "$@" --codex-home "$codex_home"
set -- "$@" "$mode"
exec "$python_command" "$@"
