"""Ask the user before an Edit, MultiEdit or Write to docs/state/tasks.json or tests.json that the layout reserves for
them: adding or removing a task, changing a task field other than CLAUDE_TASK_FIELDS, removing a test, or changing the
checks of a test that has run.

Run by the gibbon plugin's PreToolUse hook with the tool call as JSON on stdin. Prints a permissionDecision "ask" with
the reasons, or nothing to let the call through. Allows anything it can't evaluate: a new file, an edit that doesn't
apply or JSON that doesn't parse, which the post-edit check reports.
"""

import json
import sys
from pathlib import Path

# Task fields Claude may change without asking; the layout reserves every other change for the user.
CLAUDE_TASK_FIELDS = {"status", "evidence", "blocked_by", "next", "updated"}
NOT_RUN = ("planned", "not_run")


def apply_edit(text, tool, tool_input):
    """Return text after the tool call, or None if an edit's old_string isn't found."""
    if tool == "Write":
        return tool_input.get("content", "")
    edits = tool_input.get("edits") if tool == "MultiEdit" else [tool_input]
    for e in edits or []:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        if not old or old not in text:
            return None
        text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


def by_id(entries):
    return {e.get("id"): e for e in entries if isinstance(e, dict)}


def task_changes(before, after):
    b, a = by_id(before.get("items", [])), by_id(after.get("items", []))
    problems = [f"removes task {i}" for i in b.keys() - a.keys()]
    problems += [f"adds task {i}" for i in a.keys() - b.keys()]
    for i in b.keys() & a.keys():
        fields = sorted(k for k in (b[i].keys() | a[i].keys()) - CLAUDE_TASK_FIELDS if b[i].get(k) != a[i].get(k))
        if fields:
            problems.append(f"changes {', '.join(fields)} of task {i}")
    return problems


def test_changes(before, after):
    b, a = by_id(before.get("tests", [])), by_id(after.get("tests", []))
    problems = [f"removes test {i}" for i in b.keys() - a.keys()]
    for i in b.keys() & a.keys():
        if b[i].get("status") not in NOT_RUN and b[i].get("checks") != a[i].get("checks"):
            problems.append(f"changes the checks of test {i}, which has run")
    return problems


def main():
    event = json.load(sys.stdin)
    tool, tool_input = event.get("tool_name"), event.get("tool_input", {})
    path = Path(tool_input.get("file_path", ""))
    if path.name not in ("tasks.json", "tests.json") or path.parent.parts[-2:] != ("docs", "state"):
        return
    if not path.is_file():
        return
    current = path.read_text(encoding="utf-8")
    updated = apply_edit(current, tool, tool_input)
    if updated is None:
        return
    try:
        before, after = json.loads(current), json.loads(updated)
    except json.JSONDecodeError:
        return
    problems = (task_changes if path.name == "tasks.json" else test_changes)(before, after)
    if problems:
        reason = f"{path.name}: this edit {'; '.join(problems)}. The project state layout needs the user's agreement."
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": reason,
                    }
                }
            )
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # Let the tool call through if the guard itself fails, rather than blocking all edits.
        pass
