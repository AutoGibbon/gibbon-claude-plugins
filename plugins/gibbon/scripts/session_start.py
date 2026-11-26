"""Print what a new session in a docs/state/ project needs before it starts work: the session routine, git state,
environment checks, notes on the project's scripts, the state check with the tasks to pick up, and docs/status.md.

Usage: python session_start.py [--hook] [PROJECT_DIR]

PROJECT_DIR defaults to $CLAUDE_PROJECT_DIR, then the current directory. Exits 1 if a check fails. With --hook, as the
gibbon plugin's SessionStart hook runs it with the hook input on stdin, prints nothing for a project without
docs/state/ and always exits 0, because Claude Code adds a SessionStart hook's output to the session's context only
when the hook exits 0. Reads only.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
# The routine's {plugin} placeholders become PLUGIN_ROOT when it is printed.
ROUTINE = PLUGIN_ROOT / "skills" / "project-scaffold" / "session_routine.md"
# Scripts projects held under earlier versions of the layout, which the plugin's scripts replace.
SUPERSEDED_SCRIPTS = ("session_start.py", "check_state.py", "tasks.py")


def run(root, *args):
    return subprocess.run(args, check=False, cwd=root, capture_output=True, text=True).stdout.rstrip()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(path):
    """Return {relative path: sha256} for every file under path, or for path itself if it is a file."""
    if path.is_file():
        return {"": sha256(path)}
    return {str(p.relative_to(path)).replace("\\", "/"): sha256(p) for p in path.rglob("*") if p.is_file()}


def artefact_checks(root, env):
    """Compare each artefact's built and deployed file or folder by hash; return the problems found."""
    problems = []
    for a in env.get("artefacts", []):
        built, deployed = a.get("built"), a.get("deployed")
        if not (built and deployed):
            continue
        b = root / built
        d = Path(deployed)
        if not b.exists():
            problems.append(f"{a['name']}: build output {built} missing")
        elif not d.exists():
            problems.append(f"{a['name']}: not deployed at {deployed}")
        elif tree_hashes(b) != tree_hashes(d):
            problems.append(f"{a['name']}: deployed copy differs from {built}")
    return problems


def project_checks(root, env):
    """Run check(root, env) from the project's tools/project_checks.py, if it has one; return (problems, notes, info).

    check() returns a list of problems, a (problems, notes) tuple, or a (problems, notes, info) tuple.
    """
    path = root / "tools" / "project_checks.py"
    if not path.is_file():
        return [], [], []
    try:
        spec = importlib.util.spec_from_file_location("project_checks", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.check(root, env)
        if isinstance(result, tuple):
            return list(result[0]), list(result[1]), list(result[2]) if len(result) > 2 else []
        return list(result), [], []
    except Exception as e:  # Report a broken project check as a problem so the rest of the check still runs.
        return [f"tools/project_checks.py failed: {type(e).__name__}: {e}"], [], []


def script_notes(root):
    """Return notes naming the superseded scripts, project SessionStart hook and copied session routine still in the
    project, or an empty list."""
    leftovers = [f"tools/{name}" for name in SUPERSEDED_SCRIPTS if (root / "tools" / name).is_file()]
    settings = root / ".claude" / "settings.json"
    if settings.is_file() and "session_start.py" in settings.read_text(encoding="utf-8"):
        leftovers.append("the SessionStart hook in .claude/settings.json")
    claude_md = root / "CLAUDE.md"
    if claude_md.is_file() and "- **Start:**" in claude_md.read_text(encoding="utf-8"):
        leftovers.append("the copy of the session routine in CLAUDE.md")
    if not leftovers:
        return []
    return [
        f"the gibbon plugin replaces {', '.join(leftovers)}",
        "the gibbon:project-state-migrate skill removes them",
    ]


def hook_source():
    """Return the SessionStart source (startup, resume, clear or compact) from the hook input on stdin, or ""."""
    try:
        return json.load(sys.stdin).get("source", "")
    except (ValueError, AttributeError):
        return ""


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    hook = "--hook" in sys.argv
    source = hook_source() if hook else ""
    args = [a for a in sys.argv[1:] if a != "--hook"]
    root = Path(args[0] if args else os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()
    if not (root / "docs" / "state").is_dir():
        if hook:
            return 0
        print(f"{root} has no docs/state/; nothing to check")
        return 1

    print("== session routine (from the gibbon plugin; part of this project's instructions)")
    print(ROUTINE.read_text(encoding="utf-8").replace("{plugin}", PLUGIN_ROOT.as_posix()).rstrip())

    print("\n== git")
    status = run(root, "git", "status", "--short")
    print(status or "(clean)")
    print(run(root, "git", "log", "--oneline", "-5"))
    # After compaction the changes are this session's own work in progress.
    if status and hook and source != "compact":
        print("  note: uncommitted changes from before this session; ask the user whether to commit them")

    problems, notes, info = [], [], []
    print("\n== environment")
    env_path = root / "docs" / "state" / "environment.json"
    if env_path.is_file():
        try:
            env = json.loads(env_path.read_text(encoding="utf-8"))
        except ValueError as e:
            problems = [f"environment.json: invalid JSON ({e}); environment checks skipped"]
        else:
            problems, notes, info = project_checks(root, env)
            problems += artefact_checks(root, env)
    for p in problems:
        print(f"  ! {p}")
    notes += script_notes(root)
    for note in notes:
        print(f"  note: {note}")
    for line in info:
        print(f"  info: {line}")
    if not problems and not notes and not info:
        print("  ok")

    print("\n== state", flush=True)
    state = subprocess.run([sys.executable, str(HERE / "check_state.py"), str(root)], check=False, cwd=root)

    status_md = root / "docs" / "status.md"
    print("\n== docs/status.md")
    print(status_md.read_text(encoding="utf-8").rstrip() if status_md.is_file() else "  ! docs/status.md missing")

    failed = bool(problems or state.returncode)
    if hook:
        if failed:
            print("\nSession start check found problems; tell the user before starting work.")
        return 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
