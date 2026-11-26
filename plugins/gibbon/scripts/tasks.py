"""Query docs/state/tasks.json and tests.json: list, show and trace the dependencies of tasks, summarise workstreams,
and list tests.

Usage:
  python tasks.py list [--open] [--status S] [--workstream W] [--ready]
  python tasks.py show ID...
  python tasks.py deps ID
  python tasks.py streams [--open]
  python tasks.py tests [--status S]

--root REPO_ROOT before the command reads that project; by default it's the nearest folder at or above the current
directory that has docs/state/. Reads only; check_state.py validates the files.
"""

import argparse
import json
import sys
from pathlib import Path

CLOSED = ("done", "dropped")


def find_root():
    """Return the nearest folder at or above the current directory that has docs/state/, or the current directory."""
    cwd = Path.cwd().resolve()
    return next((p for p in (cwd, *cwd.parents) if (p / "docs" / "state").is_dir()), cwd)


def load(root, name, key):
    path = root / "docs" / "state" / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))[key]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        sys.exit(f"{path}: can't read '{key}': {e}")


def is_stream(t):
    return t.get("kind") == "workstream"


def open_deps(t, by_id):
    """Return the ids in t's depends_on that aren't done or dropped."""
    return [d for d in t.get("depends_on", []) if by_id.get(d, {}).get("status") not in CLOSED]


def is_ready(t, by_id):
    """Return whether a todo item can start now: its depends_on are closed, and so are its workstream's."""
    if t.get("status") != "todo" or open_deps(t, by_id):
        return False
    ws = by_id.get(t.get("workstream"))
    return not (ws and open_deps(ws, by_id))


def task_line(t, by_id):
    """Return one line for a task: status, id, workstream (or {stream} for a workstream item), next and ready flags,
    dependencies and title."""
    flag = (" *next" if t.get("next") else "") + (" *ready" if is_ready(t, by_id) else "")
    deps = f" <- {', '.join(t['depends_on'])}" if t.get("depends_on") else ""
    group = "{stream}" if is_stream(t) else f"({t.get('workstream', '-')})"
    return f"[{t.get('status')}] {t.get('id')} {group}{flag}{deps}: {t.get('title')}"


def cmd_list(tasks, args):
    by_id = {t.get("id"): t for t in tasks}
    for t in tasks:
        if args.open and t.get("status") in CLOSED:
            continue
        if args.status and t.get("status") != args.status:
            continue
        if args.workstream and t.get("workstream") != args.workstream:
            continue
        if args.ready and not is_ready(t, by_id):
            continue
        print(task_line(t, by_id))


def cmd_show(tasks, args):
    by_id = {t.get("id"): t for t in tasks}
    for i, tid in enumerate(args.ids):
        t = by_id.get(tid)
        if i:
            print()
        if t is None:
            print(f"{tid}: no such task")
            continue
        print(task_line(t, by_id))
        for key in ("done_when", "evidence", "blocked_by"):
            value = t.get(key)
            if not value:
                continue
            print(f"  {key}:")
            for item in value if isinstance(value, list) else [value]:
                print(f"    - {item}")
        for key in ("detail", "updated"):
            if t.get(key):
                print(f"  {key}: {t[key]}")


def print_tree(tid, edges, by_id, depth, path):
    """Print tid's chain through edges, indented by depth, marking a task already on the current path as a cycle."""
    for nxt in edges.get(tid, []):
        t = by_id.get(nxt)
        status = t.get("status") if t else "unknown"
        if nxt in path:
            print(f"{'  ' * depth}{nxt} [{status}] (cycle)")
            continue
        print(f"{'  ' * depth}{nxt} [{status}]")
        print_tree(nxt, edges, by_id, depth + 1, path | {nxt})


def cmd_deps(tasks, args):
    by_id = {t.get("id"): t for t in tasks}
    if args.id not in by_id:
        sys.exit(f"{args.id}: no such task")
    waits_on = {t.get("id"): t.get("depends_on", []) for t in tasks}
    waited_on_by = {}
    for t in tasks:
        for dep in t.get("depends_on", []):
            waited_on_by.setdefault(dep, []).append(t.get("id"))
    print(task_line(by_id[args.id], by_id))
    for label, edges in (("waits on", waits_on), ("waited on by", waited_on_by)):
        print(f"{label}:")
        if edges.get(args.id):
            print_tree(args.id, edges, by_id, 1, {args.id})
        else:
            print("  (none)")


def counts(tasks, sid):
    """Return the open and done task counts of workstream sid."""
    members = [t for t in tasks if t.get("workstream") == sid]
    return sum(1 for t in members if t.get("status") not in CLOSED), sum(
        1 for t in members if t.get("status") == "done"
    )


def cmd_streams(tasks, args):
    """Print one line per workstream item: status, id, open and done task counts, unfinished depends_on and title.
    Then one line per workstream string on tasks that has no item, with its counts."""
    by_id = {t.get("id"): t for t in tasks}
    for s in tasks:
        if not is_stream(s) or (args.open and s.get("status") in CLOSED):
            continue
        n_open, n_done = counts(tasks, s.get("id"))
        waits = open_deps(s, by_id)
        wait_text = f" waits on {', '.join(waits)}" if waits else ""
        flag = " *next" if s.get("next") else ""
        print(f"[{s.get('status')}] {s.get('id')}{flag} ({n_open} open, {n_done} done){wait_text}: {s.get('title')}")
    items = {s.get("id") for s in tasks if is_stream(s)}
    orphans = dict.fromkeys(t["workstream"] for t in tasks if t.get("workstream") and t["workstream"] not in items)
    for sid in orphans:
        n_open, n_done = counts(tasks, sid)
        if not (args.open and n_open == 0):
            print(f"[no item] {sid} ({n_open} open, {n_done} done)")


def cmd_tests(tests, args):
    for t in tests:
        if args.status and t.get("status") != args.status:
            continue
        when = " ".join(str(t[k]) for k in ("date", "build") if t.get(k))
        text = t.get("result") if t.get("status") not in ("planned", "not_run") else t.get("checks")
        print(f"[{t.get('status')}] {t.get('id')}{' ' + when if when else ''}: {text}")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Query docs/state/tasks.json and tests.json.")
    parser.add_argument("--root", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="one line per task")
    p.add_argument("--open", action="store_true", help="leave out done and dropped tasks")
    p.add_argument("--status")
    p.add_argument("--workstream")
    p.add_argument(
        "--ready", action="store_true", help="only todo items whose dependencies and workstream's are closed"
    )
    p = sub.add_parser("show", help="full entries")
    p.add_argument("ids", nargs="+", metavar="ID")
    p = sub.add_parser("deps", help="what a task waits on and what waits on it, recursively")
    p.add_argument("id", metavar="ID")
    p = sub.add_parser("streams", help="one line per workstream with its task counts and what it waits on")
    p.add_argument("--open", action="store_true", help="leave out done and dropped workstreams")
    p = sub.add_parser("tests", help="one line per test")
    p.add_argument("--status")
    args = parser.parse_args()

    root = args.root.resolve() if args.root else find_root()
    if args.cmd == "tests":
        cmd_tests(load(root, "tests.json", "tests"), args)
    else:
        commands = {"list": cmd_list, "show": cmd_show, "deps": cmd_deps, "streams": cmd_streams}
        commands[args.cmd](load(root, "tasks.json", "items"), args)


if __name__ == "__main__":
    main()
