from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
from typing import Any

from .command_router import ALIASES, COMMANDS, help_text, run_command
from .mcp import TOOLS

try:
    import readline
except ImportError:  # pragma: no cover
    readline = None


def _print_output(data: Any) -> None:
    if data is None:
        return
    if isinstance(data, str):
        print(data)
        return
    print(json.dumps(data, indent=2, sort_keys=True))


def _path_suggestions(prefix: str) -> list[str]:
    base_dir = "."
    partial = prefix
    if "/" in prefix:
        base_dir, partial = os.path.split(prefix)
        base_dir = base_dir or "."
    try:
        names = os.listdir(base_dir)
    except OSError:
        return []

    out: list[str] = []
    for name in names:
        if name.startswith(partial):
            full = os.path.join(base_dir, name)
            candidate = os.path.join(base_dir, name) if base_dir != "." else name
            out.append(candidate + "/" if os.path.isdir(full) else candidate)
    return sorted(out)


def _complete(text: str, state: int) -> str | None:
    if readline is None:
        return None

    buffer = readline.get_line_buffer()
    begidx = readline.get_begidx()
    try:
        parts = shlex.split(buffer[:begidx]) if buffer[:begidx].strip() else []
    except ValueError:
        parts = []
    current = parts[0] if parts else ""

    if begidx == 0:
        candidates = sorted([c for c in COMMANDS + list(ALIASES) if c.startswith(text)])
    elif current in {"schema", "call"} or ALIASES.get(current) in {"schema", "call"}:
        candidates = sorted([name for name in TOOLS if name.startswith(text)])
    elif current in {"analyze_repo", "analyze"}:
        candidates = _path_suggestions(text)
    else:
        candidates = []

    if state < len(candidates):
        return candidates[state]
    return None


def _setup_readline() -> None:
    if readline is None:
        return
    readline.parse_and_bind("tab: complete")
    readline.set_completer(_complete)


def _print_terminal_title(title: str = "OpenX") -> None:
    columns = shutil.get_terminal_size(fallback=(80, 24)).columns
    print(title.center(columns))


def run_repl() -> None:
    _setup_readline()
    _print_terminal_title()
    print("OpenX terminal started. Type 'help' for commands, 'exit' to quit.")
    while True:
        try:
            raw = input("openx> ").strip()
            if not raw:
                continue
            tokens = shlex.split(raw)
            result = run_command(tokens)
            _print_output(result.output)
            if not result.should_continue:
                break
        except KeyboardInterrupt:
            print("\nInterrupted. Type 'exit' to quit.")
        except EOFError:
            print()
            break
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="openx",
        description="OpenX MCP terminal for listing and running tools.",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Optional one-shot command. If omitted, starts interactive mode.",
    )
    args = parser.parse_args()

    if args.command:
        try:
            result = run_command(args.command)
            _print_output(result.output)
            if not result.should_continue:
                return
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}")
            raise SystemExit(1) from exc
    else:
        run_repl()


if __name__ == "__main__":
    main()
