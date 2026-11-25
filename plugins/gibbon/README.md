# gibbon

Claude Code plugin for project state tracking.

- `gibbon:project-scaffold` - set up a new project's state layout. `skills/project-scaffold/layout.md` defines the
  layout all three skills share.
- `gibbon:project-state-migrate` - audit an existing project's state tracking and optionally migrate it to the layout.
- `gibbon:wrap-up` - record session state and commit before starting a fresh session.

Hooks, in every project with `docs/state/`:

- `SessionStart` runs `scripts/session_start.py`, which prints the session routine (with the `scripts/tasks.py`
  command), git status, the project's `tools/project_checks.py` and deployed artefact hash results,
  `scripts/check_state.py`'s validation and next tasks, and `docs/status.md`. It prints the routine in full rather
  than a pointer to it, because Claude follows it more reliably that way; don't shorten it to save context.
- `PreToolUse` runs `hooks/guard_state.py`, which asks the user before an edit to `tasks.json` or `tests.json` that the
  layout reserves for them.
- `PostToolUse` runs `hooks/post_state_check.py`, which reports `check_state.py`'s findings after an edit to
  `docs/state/`, and `hooks/post_bash_state_check.py`, which reports its errors after a Bash call that changed a file
  there.

When adding a safeguard, prefer a hook that checks the result whatever tool produced it, exiting early when nothing it
checks changed, over a rule restricting which tools Claude uses. Tool rules narrow how Claude works and miss whatever
goes around them.
