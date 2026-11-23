"""Validate docs/state/ after an Edit, MultiEdit or Write to one of its JSON files, and report to Claude the errors
and the warnings about entries the edit touched.

Run by the gibbon plugin's PostToolUse hook with the tool call as JSON on stdin. Exits 2 with the report on stderr,
which Claude Code shows to Claude, or 0 when there is nothing to report.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_state  # noqa: E402


def touched(warning, edit_text):
    """Return whether a warning, which starts "<file> <id>:", names an id that appears in the edit's new text."""
    head = warning.split(":", 1)[0].split(" ")
    return len(head) == 2 and f'"{head[1]}"' in edit_text


def main():
    event = json.load(sys.stdin)
    tool_input = event.get("tool_input", {})
    path = Path(tool_input.get("file_path", ""))
    if path.suffix != ".json" or path.parent.parts[-2:] != ("docs", "state"):
        return 0
    root = path.parent.parent.parent
    edit_text = tool_input.get("content", "") + tool_input.get("new_string", "")
    edit_text += "".join(e.get("new_string", "") for e in tool_input.get("edits") or [])
    errors, warnings, _, _ = check_state.check(root)
    warnings = [w for w in warnings if touched(w, edit_text)]
    if not (errors or warnings):
        return 0
    lines = ["docs/state check after this edit:"]
    if errors:
        lines += ["Errors; fix these now:"] + [f"  - {e}" for e in errors]
    if warnings:
        lines += ["Warnings on the entries this edit touched; tell the user rather than filling these in:"]
        lines += [f"  - {w}" for w in warnings]
    print("\n".join(lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
