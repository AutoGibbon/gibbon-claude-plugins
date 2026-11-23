"""Note each script a docs/state/ project copies from the project-scaffold templates that is missing or differs.

Run by the gibbon plugin's SessionStart hook on $CLAUDE_PROJECT_DIR. Prints nothing for a project without docs/state/
or with current copies. Always exits 0, because Claude Code adds a SessionStart hook's output to the session's context
only when the hook exits 0.
"""

import os
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "skills" / "project-scaffold" / "templates"
# Scripts each project copies unchanged from TEMPLATES.
COPIED_SCRIPTS = ("check_state.py", "tasks.py")


def norm(path):
    return path.read_bytes().replace(b"\r\n", b"\n")


def main():
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    if not (root / "docs" / "state").is_dir():
        return
    notes = []
    for name in COPIED_SCRIPTS:
        ours, template = root / "tools" / name, TEMPLATES / name
        if not ours.is_file():
            notes.append(f"tools/{name} is missing; copy it from the project-scaffold template")
        elif norm(ours) != norm(template):
            notes.append(
                f"tools/{name} differs from the project-scaffold template (see the project-state-migrate audit)"
            )
    if notes:
        print("== project-scaffold templates")
        for note in notes:
            print(f"  note: {note}")


if __name__ == "__main__":
    main()
