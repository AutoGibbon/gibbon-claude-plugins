"""Record the modification times of docs/state/'s JSON files before a Bash call, for post_bash_state_check.py.

Run by the gibbon plugin's PreToolUse hook with the tool call as JSON on stdin. Writes the times to a file in the temp
directory named after the tool call, and nothing for a directory without docs/state/. Always exits 0.
"""

import json
import sys
import tempfile
from pathlib import Path


def state_dir(cwd):
    """Return the docs/state directory of cwd or its nearest parent that has one, or None."""
    for d in [cwd, *cwd.parents]:
        if (d / "docs" / "state").is_dir():
            return d / "docs" / "state"
    return None


def mtimes(state):
    """Return {path: modification time in ns} for each JSON file in state."""
    return {str(p): p.stat().st_mtime_ns for p in sorted(state.glob("*.json"))}


def stamp_path(event):
    """Return the temp file that holds the times recorded before the tool call in event."""
    key = f"{event.get('session_id', 'none')}-{event.get('tool_use_id', 'none')}"
    return Path(tempfile.gettempdir()) / f"gibbon-state-{key}.json"


def main():
    event = json.load(sys.stdin)
    state = state_dir(Path(event.get("cwd") or "."))
    if state is not None:
        stamp = {"state": str(state), "mtimes": mtimes(state)}
        stamp_path(event).write_text(json.dumps(stamp), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
