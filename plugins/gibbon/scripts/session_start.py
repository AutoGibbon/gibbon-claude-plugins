"""Print what a new session in a docs/state/ project needs before it starts work: the session routine, git state,
environment checks, notes on the project's scripts, the state check with the tasks to pick up, and docs/status.md.

Usage: python session_start.py [--hook] [--part routine|state|status] [PROJECT_DIR]

PROJECT_DIR defaults to $CLAUDE_PROJECT_DIR, then the current directory. Exits 1 if a check fails. --part prints one
section: routine (the session routine, git and environment), state (the state check) or status (docs/status.md, cut to
fit the hook output limit); without it all three print. With --hook, as the gibbon plugin's SessionStart hooks run
it with the hook input on stdin, prints nothing for a project without docs/state/ and always exits 0, because Claude
Code adds a SessionStart hook's output to the session's context only when the hook exits 0. Reads only.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from check_state import HOOK_OUTPUT_LIMIT, STATUS_HEADER, STATUS_MD_LIMIT

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
# The routine's {plugin} placeholders become PLUGIN_ROOT when it is printed.
ROUTINE = PLUGIN_ROOT / "skills" / "project-scaffold" / "session_routine.md"
# Scripts projects held under earlier versions of the layout, which the plugin's scripts replace.
SUPERSEDED_SCRIPTS = ("session_start.py", "check_state.py", "tasks.py")
# The output sections --part selects; the plugin runs one SessionStart hook per part, since each hook's output reaching
# the context is capped at HOOK_OUTPUT_LIMIT characters.
PARTS = ("routine", "state", "status")
STATUS_CUT = "[... rest of docs/status.md not shown]"


def run(root, *args):
    result = subprocess.run(args, check=False, cwd=root, capture_output=True, encoding="utf-8", errors="replace")
    return result.stdout.rstrip()


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


def sets_utf8_mode(settings):
    """Return whether the Claude Code settings file at settings sets PYTHONUTF8=1 under env."""
    try:
        env = json.loads(settings.read_text(encoding="utf-8")).get("env", {})
    except (OSError, ValueError, AttributeError):
        return False
    return isinstance(env, dict) and str(env.get("PYTHONUTF8")) == "1"


def utf8_notes(root):
    """Return a note if neither the project's .claude/settings.json nor the user's settings.json sets PYTHONUTF8=1
    under env, or an empty list."""
    user_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    if sets_utf8_mode(root / ".claude" / "settings.json") or sets_utf8_mode(user_dir / "settings.json"):
        return []
    return [
        ".claude/settings.json doesn't set PYTHONUTF8=1 under env, so Python on Windows prints in the console's code "
        "page; the gibbon:project-state-migrate skill adds it"
    ]


def hook_source():
    """Return the SessionStart source (startup, resume, clear or compact) from the hook input on stdin, or ""."""
    try:
        return json.loads(sys.stdin.buffer.read().decode("utf-8")).get("source", "")
    except (ValueError, AttributeError):
        return ""


def print_routine(root, source, hook):
    """Print the session routine, git state and environment checks; return whether a check failed."""
    print("== session routine (from the gibbon plugin; part of this project's instructions)")
    print(ROUTINE.read_text(encoding="utf-8").replace("{plugin}", PLUGIN_ROOT.as_posix()).rstrip())

    print("\n== git")
    in_repo = run(root, "git", "rev-parse", "--is-inside-work-tree") == "true"
    if in_repo:
        status = run(root, "git", "status", "--short")
        print(status or "(clean)")
        print(run(root, "git", "log", "--oneline", "-5") or "(no commits)")
        # After compaction the changes are this session's own work in progress.
        if status and hook and source != "compact":
            print("  note: uncommitted changes from before this session; ask the user whether to commit them")
    else:
        print("  ! not a git repository")

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
    notes += script_notes(root) + utf8_notes(root)
    for note in notes:
        print(f"  note: {note}")
    for line in info:
        print(f"  info: {line}")
    if not problems and not notes and not info:
        print("  ok")
    return bool(problems or not in_repo)


def print_state(root):
    """Print check_state.py's output; return whether it failed."""
    print("== state", flush=True)
    check_state = [sys.executable, "-X", "utf8", str(HERE / "check_state.py"), str(root)]
    return subprocess.run(check_state, check=False, cwd=root).returncode != 0


def print_status(root, trim):
    """Print docs/status.md; with trim, cut it at a line end to fit HOOK_OUTPUT_LIMIT, with a note saying so."""
    status_md = root / "docs" / "status.md"
    print(STATUS_HEADER)
    if not status_md.is_file():
        print("  ! docs/status.md missing")
        return
    text = status_md.read_text(encoding="utf-8").rstrip()
    if not trim or len(text) <= STATUS_MD_LIMIT:
        print(text)
        return
    note = (
        f"  note: docs/status.md is {len(text)} characters, over this hook's output limit, so only its start is shown; "
        "read the file for the rest and tell the user to shorten it"
    )
    # Four newlines join the header, note, cut text and STATUS_CUT.
    cut = text[: HOOK_OUTPUT_LIMIT - len(STATUS_HEADER) - len(note) - len(STATUS_CUT) - 4]
    if "\n" in cut:
        cut = cut[: cut.rfind("\n")]
    print(f"{note}\n{cut}\n{STATUS_CUT}")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            # Write LF line ends, so the output's length on Windows equals the character count HOOK_OUTPUT_LIMIT caps.
            stream.reconfigure(encoding="utf-8", errors="replace", newline="\n")
    hook = "--hook" in sys.argv
    source = hook_source() if hook else ""
    args = [a for a in sys.argv[1:] if a != "--hook"]
    part = None
    if "--part" in args:
        i = args.index("--part")
        part = args[i + 1] if i + 1 < len(args) else None
        del args[i : i + 2]
        if part not in PARTS:
            print(f"--part takes one of {', '.join(PARTS)}", file=sys.stderr)
            return 0 if hook else 2
    root = Path(args[0] if args else os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()
    if not (root / "docs" / "state").is_dir():
        if hook:
            return 0
        print(f"{root} has no docs/state/; nothing to check")
        return 1

    failed = False
    if part in (None, "routine"):
        failed |= print_routine(root, source, hook)
    if part in (None, "state"):
        if part is None:
            print()
        failed |= print_state(root)
    if part in (None, "status"):
        if part is None:
            print()
        print_status(root, part == "status")

    if hook:
        if failed:
            print("\nSession start check found problems; tell the user before starting work.")
        return 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
