"""Validate docs/state/ after a Bash call that changed one of its JSON files, and report the errors to Claude.

Run by the gibbon plugin's PostToolUse hook with the tool call as JSON on stdin. Compares the state files'
modification times with those pre_bash_state_stamp.py recorded before the call, and exits 0 at once when none changed
or nothing was recorded. Otherwise exits 2 with the errors on stderr, which Claude Code shows to Claude, or 0 when
there are none.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))

from pre_bash_state_stamp import mtimes, stamp_path  # noqa: E402


def main():
    event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    stamp = stamp_path(event)
    try:
        before = json.loads(stamp.read_text(encoding="utf-8"))
        state = Path(before["state"])
    except (OSError, ValueError, KeyError, TypeError):
        return 0
    stamp.unlink(missing_ok=True)
    if not state.is_dir() or mtimes(state) == before.get("mtimes"):
        return 0

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
