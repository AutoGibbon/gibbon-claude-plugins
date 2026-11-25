"""Validate docs/state/ after a Bash call that changed one of its JSON files, and report the errors to Claude.

Run by the gibbon plugin's PostToolUse hook with the tool call as JSON on stdin. Compares the state files'
modification times with those recorded for the session in the temp directory, and exits 0 at once when none changed.
Otherwise exits 2 with the errors on stderr, which Claude Code shows to Claude, or 0 when there are none.
"""

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))


def state_dir(cwd):
    """Return the docs/state directory of cwd or its nearest parent that has one, or None."""
    for d in [cwd, *cwd.parents]:
        if (d / "docs" / "state").is_dir():
            return d / "docs" / "state"
    return None


def main():
    event = json.load(sys.stdin)
    state = state_dir(Path(event.get("cwd") or "."))
    if state is None:
        return 0
    mtimes = {str(p): p.stat().st_mtime_ns for p in sorted(state.glob("*.json"))}
    stamp = Path(tempfile.gettempdir()) / f"gibbon-state-{event.get('session_id', 'none')}.json"
    try:
        seen = json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        seen = None
    if seen == mtimes:
        return 0
    stamp.write_text(json.dumps(mtimes), encoding="utf-8")

    import check_state
    from post_state_check import grouped

    errors, _, _, _ = check_state.check(state.parent.parent)
    if not errors:
        return 0
    lines = ["docs/state check after this command changed a state file:", "Errors; fix these now:"]
    lines += [f"  - {e}" for e in grouped(errors)]
    print("\n".join(lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
