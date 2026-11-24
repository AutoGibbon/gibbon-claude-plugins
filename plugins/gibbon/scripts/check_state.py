"""Validate docs/state/*.json against the project state layout and print the work to pick up.

Usage: python check_state.py [REPO_ROOT]

Exits 1 on errors: a missing or invalid file, a bad id, status or kind, a reference to a task, workstream, test,
commit or path that doesn't exist, a nested workstream, or a dependency cycle. Warnings (gaps in done_when, evidence,
results or blocked_by, and work started out of order) are printed but don't fail. Reads only.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

TASK_STATUSES = ["todo", "in_progress", "blocked", "done", "dropped"]
CLOSED = ("done", "dropped")
# Workstream statuses under which its tasks may be in_progress or done.
STREAM_STARTED = ("in_progress", "done")
WORKSTREAM = "workstream"
TEST_STATUSES = ["planned", "passed", "failed", "partial", "inconclusive", "not_run", "aborted"]
TASK_FIELDS = {
    "id",
    "kind",
    "workstream",
    "title",
    "status",
    "next",
    "done_when",
    "depends_on",
    "evidence",
    "blocked_by",
    "detail",
    "updated",
}
TEST_FIELDS = {"id", "file", "checks", "status", "date", "build", "tasks", "result"}
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
# Evidence with a slash and no spaces is a repo path, checked for existence; other text is accepted as written.
PATH_RE = re.compile(r"^[^\s]*/[^\s]*$")


def load(path, errors):
    if not path.is_file():
        errors.append(f"{path}: missing")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"{path}: invalid JSON: {e}")
        return None


def path_exists(root, ref):
    """Return whether a repo path, with an optional #anchor, exists."""
    return (root / ref.split("#", 1)[0]).exists()


def commit_exists(root, ref):
    result = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"{ref}^{{commit}}"], check=False, capture_output=True
    )
    return result.returncode == 0


def check_header(name, data, statuses, list_key, errors):
    if data.get("schema") != 1:
        errors.append(f"{name}: schema must be 1")
    if "statuses" in data and data["statuses"] != statuses:
        errors.append(f"{name}: statuses must be {statuses}")
    if not isinstance(data.get(list_key), list):
        errors.append(f"{name}: '{list_key}' must be a list")
        return []
    return data[list_key]


def check_ids(name, entries, errors):
    seen = set()
    for e in entries:
        i = e.get("id")
        if not isinstance(i, str) or not ID_RE.match(i):
            errors.append(f"{name}: bad id {i!r} (kebab-case required)")
        elif i in seen:
            errors.append(f"{name}: duplicate id {i}")
        seen.add(i)
    return seen


def is_stream(t):
    return t.get("kind") == WORKSTREAM


def find_cycles(edges):
    """Return each cycle in edges ({id: [ids it waits on]}) as a list of ids with the first id repeated at the end."""
    cycles = []
    state = {}
    stack = []

    def visit(node):
        state[node] = "open"
        stack.append(node)
        for nxt in edges.get(node, []):
            if state.get(nxt) == "open":
                cycles.append(stack[stack.index(nxt) :] + [nxt])
            elif nxt not in state:
                visit(nxt)
        stack.pop()
        state[node] = "closed"

    for node in list(edges):
        if node not in state:
            visit(node)
    return cycles


def check_streams(tasks, task_ids, errors, warnings):
    """Check kind, workstream membership, start order between workstreams and tasks, and dependency cycles."""
    by_id = {t.get("id"): t for t in tasks}
    streams = {t.get("id"): t for t in tasks if is_stream(t)}
    members = {}
    orphans = set()
    for t in tasks:
        tid = t.get("id")
        status = t.get("status")
        ws = t.get("workstream")
        if t.get("kind") not in (None, WORKSTREAM):
            errors.append(f"tasks.json {tid}: kind {t.get('kind')!r} must be {WORKSTREAM!r} or absent")
        open_deps = [d for d in t.get("depends_on", []) if d in by_id and by_id[d].get("status") not in CLOSED]
        if status == "done" and open_deps:
            warnings.append(f"tasks.json {tid}: done while depends_on {', '.join(open_deps)} is open")
        if is_stream(t) and status == "in_progress" and open_deps:
            warnings.append(f"tasks.json {tid}: workstream in_progress while depends_on {', '.join(open_deps)} is open")
        if not ws:
            continue
        if is_stream(t):
            errors.append(f"tasks.json {tid}: a workstream can't belong to workstream {ws}")
            continue
        if ws not in streams:
            if streams:
                errors.append(f"tasks.json {tid}: workstream {ws} isn't a workstream item")
            else:
                orphans.add(ws)
            continue
        members.setdefault(ws, []).append(t)
        stream_status = streams[ws].get("status")
        if status in STREAM_STARTED and stream_status not in STREAM_STARTED:
            warnings.append(f"tasks.json {tid}: {status} while its workstream {ws} is {stream_status}")
        if t.get("next") and stream_status != "in_progress":
            warnings.append(f"tasks.json {tid}: next is set while its workstream {ws} is {stream_status}")
    if orphans:
        warnings.append(
            f"tasks.json: workstreams {', '.join(sorted(orphans))} have no workstream item; "
            "the gibbon:project-state-migrate skill adds them"
        )
    for sid, s in streams.items():
        open_members = [m.get("id") for m in members.get(sid, []) if m.get("status") not in CLOSED]
        if s.get("status") in CLOSED and open_members:
            warnings.append(f"tasks.json {sid}: {s.get('status')} workstream with open tasks {', '.join(open_members)}")
        if s.get("status") == "in_progress" and not any(m.get("next") for m in members.get(sid, [])):
            warnings.append(f"tasks.json {sid}: workstream in_progress with no next task")

    # A workstream waits on its tasks as well as its depends_on, so a task that waits on its own workstream, directly
    # or through other items, forms a cycle.
    edges = {t.get("id"): [d for d in t.get("depends_on", []) if d in task_ids] for t in tasks}
    for sid, ms in members.items():
        edges[sid] = edges.get(sid, []) + [m.get("id") for m in ms]
    for cycle in find_cycles(edges):
        errors.append(f"tasks.json: dependency cycle {' -> '.join(cycle)}")


def check(root):
    """Validate root's docs/state/*.json; return (errors, warnings, tasks, tests)."""
    state = root / "docs" / "state"
    errors = []
    warnings = []

    tasks_data = load(state / "tasks.json", errors)
    tests_data = load(state / "tests.json", errors)
    env_data = load(state / "environment.json", errors)

    tasks = check_header("tasks.json", tasks_data, TASK_STATUSES, "items", errors) if tasks_data else []
    tests = check_header("tests.json", tests_data, TEST_STATUSES, "tests", errors) if tests_data else []
    if env_data and env_data.get("schema") != 1:
        errors.append("environment.json: schema must be 1")

    task_ids = check_ids("tasks.json", tasks, errors)
    test_ids = check_ids("tests.json", tests, errors)

    for t in tasks:
        tid = t.get("id")
        status = t.get("status")
        for key in ("title", "status"):
            if not t.get(key):
                errors.append(f"tasks.json {tid}: '{key}' missing")
        for key in sorted(set(t) - TASK_FIELDS):
            warnings.append(f"tasks.json {tid}: field '{key}' isn't in the layout; move its content to the detail doc")
        if status not in TASK_STATUSES:
            errors.append(f"tasks.json {tid}: status {status!r} not in {TASK_STATUSES}")
        if status == "in_progress" and not t.get("done_when"):
            warnings.append(f"tasks.json {tid}: in_progress with no done_when")
        if status == "done" and not t.get("evidence") and not is_stream(t):
            warnings.append(f"tasks.json {tid}: done with no evidence")
        if t.get("next") and status in ("done", "dropped"):
            warnings.append(f"tasks.json {tid}: next is set on a {status} task")
        if status == "blocked" and not t.get("blocked_by"):
            warnings.append(f"tasks.json {tid}: blocked with no blocked_by")
        for dep in t.get("depends_on", []):
            if dep not in task_ids:
                errors.append(f"tasks.json {tid}: depends_on unknown task {dep}")
        for ev in t.get("evidence", []):
            if ev in test_ids:
                continue
            if COMMIT_RE.match(ev):
                if not commit_exists(root, ev):
                    errors.append(f"tasks.json {tid}: evidence commit {ev} not found")
            elif PATH_RE.match(ev) and not path_exists(root, ev):
                errors.append(f"tasks.json {tid}: evidence path {ev} not found")
        if t.get("detail") and not path_exists(root, t["detail"]):
            errors.append(f"tasks.json {tid}: detail {t['detail']} not found")

    check_streams(tasks, task_ids, errors, warnings)

    for t in tests:
        tid = t.get("id")
        for key in ("checks", "status"):
            if not t.get(key):
                errors.append(f"tests.json {tid}: '{key}' missing")
        for key in sorted(set(t) - TEST_FIELDS):
            warnings.append(f"tests.json {tid}: field '{key}' isn't in the layout; move its content to the test file")
        if t.get("status") not in TEST_STATUSES:
            errors.append(f"tests.json {tid}: status {t.get('status')!r} not in {TEST_STATUSES}")
        if t.get("file") and not path_exists(root, t["file"]):
            errors.append(f"tests.json {tid}: file {t['file']} not found")
        if t.get("status") not in ("planned", "not_run") and not t.get("result"):
            warnings.append(f"tests.json {tid}: status {t.get('status')} with no result")
        for task in t.get("tasks", []):
            if task not in task_ids:
                errors.append(f"tests.json {tid}: unknown task {task}")
    return errors, warnings, tasks, tests


def item_line(t):
    extra = f" (blocked by: {t.get('blocked_by', '?')})" if t.get("status") == "blocked" else ""
    return f"[{t.get('status')}] {t.get('id')}: {t.get('title')}{extra}"


def stream_header(s, tasks):
    """Return a workstream's header lines: status, id, title, open and done task counts, then its first done_when."""
    members = [t for t in tasks if t.get("workstream") == s.get("id")]
    n_open = sum(1 for t in members if t.get("status") not in CLOSED)
    n_done = sum(1 for t in members if t.get("status") == "done")
    lines = [f"[{s.get('status')}] {s.get('id')}: {s.get('title')} ({n_open} open, {n_done} done)"]
    if s.get("done_when"):
        lines.append(f"  goal: {s['done_when'][0]}")
    return lines


def print_grouped(label, chosen, tasks, streams, headers):
    """Print chosen tasks under label, grouped by workstream when the project has workstream items, with tasks in no
    workstream under Other. With headers, each group starts with stream_header's lines instead of the workstream id."""
    if not chosen:
        return
    print(f"{label}:")
    if not streams:
        for t in chosen:
            print(f"  - {item_line(t)}")
        return
    groups = {}
    for t in chosen:
        groups.setdefault(t.get("workstream") if t.get("workstream") in streams else None, []).append(t)
    for sid in [s for s in streams if s in groups] + ([None] if None in groups else []):
        if sid is None:
            print("  Other:")
        elif headers:
            for line in stream_header(streams[sid], tasks):
                print(f"  {line}")
        else:
            print(f"  {sid}:")
        for t in groups[sid]:
            print(f"    - {item_line(t)}")


def ready(tasks, streams):
    """Return the todo items without next whose depends_on are all closed: workstreams, and tasks whose workstream is
    in_progress."""
    by_id = {t.get("id"): t for t in tasks}
    found = []
    for t in tasks:
        if t.get("status") != "todo" or t.get("next"):
            continue
        if any(by_id.get(d, {}).get("status") not in CLOSED for d in t.get("depends_on", [])):
            continue
        ws = streams.get(t.get("workstream"))
        if is_stream(t) or (ws and ws.get("status") == "in_progress"):
            found.append(t)
    return found


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    errors, warnings, tasks, tests = check(root)
    streams = {t.get("id"): t for t in tasks if is_stream(t)}
    work = [t for t in tasks if not is_stream(t)]
    print_grouped("Next", [t for t in work if t.get("next")], tasks, streams, True)
    in_progress = [t for t in work if t.get("status") == "in_progress" and not t.get("next")]
    print_grouped("In progress", in_progress, tasks, streams, False)
    blocked = [t for t in work if t.get("status") == "blocked" and not t.get("next")]
    print_grouped("Blocked", blocked, tasks, streams, False)
    if not any(s.get("status") == "in_progress" for s in streams.values()):
        upcoming = [s for s in streams.values() if s.get("next")]
        if upcoming:
            print("Next workstreams:")
            for s in upcoming:
                for i, line in enumerate(stream_header(s, tasks)):
                    print(f"  {'- ' if i == 0 else '  '}{line}")
    candidates = ready(tasks, streams)
    if candidates:
        print("Ready to start:")
        for t in candidates:
            print(f"  - {item_line(t)}{' (workstream)' if is_stream(t) else ''}")
    pending = [t for t in tests if t.get("status") == "planned"]
    if pending:
        print("Planned tests:")
        for t in pending:
            print(f"  - {t.get('id')}: {t.get('checks')}")

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")
    if errors:
        print(f"\nState check FAILED ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("\nState check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
