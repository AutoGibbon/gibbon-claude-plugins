# gibbon

Claude Code plugin for project state tracking.

- `gibbon:project-scaffold` - set up a new project's state layout. `skills/project-scaffold/layout.md` defines the
  layout all three skills share.
- `gibbon:project-state-migrate` - audit an existing project's state tracking and optionally migrate it to the layout.
- `gibbon:wrap-up` - record session state and commit before starting a fresh session.

Hooks, in every project with `docs/state/`:

- `SessionStart` runs `scripts/session_start.py`, which prints the session routine (with the `scripts/tasks.py`
  command), git status, the project's `tools/project_checks.py` and deployed artefact hash results,
  `scripts/check_state.py`'s validation and next tasks, and `docs/status.md`.
- `PreToolUse` runs `hooks/guard_state.py`, which asks the user before an edit to `tasks.json` or `tests.json` that the
  layout reserves for them.
- `PostToolUse` runs `hooks/post_state_check.py`, which reports `check_state.py`'s findings after an edit to
  `docs/state/`.
