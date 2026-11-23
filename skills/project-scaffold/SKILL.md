---
name: project-scaffold
description: Set up a new project so Claude can work on it across many sessions - CLAUDE.md, docs/state/ JSON for tasks, tests and environment, a short docs/status.md, the project's own session start checks, .gitignore and git. Use when the user says "scaffold a project", "set up a new project", "start a project", or opens a directory with no CLAUDE.md and no state docs and asks to begin work there. Not for a project that already records its status (use gibbon:project-state-migrate), nor for writing a CLAUDE.md from existing code (/init).
---

# Scaffold a project

Create the project state layout described in `${CLAUDE_PLUGIN_ROOT}/skills/project-scaffold/layout.md`. Read it
first; it defines every file, schema and rule used here. Templates are in
`${CLAUDE_PLUGIN_ROOT}/skills/project-scaffold/templates/`.

## 1. Check the directory

List it. If it has a `CLAUDE.md`, a `docs/status.md` or any other status, plan or test doc, stop and suggest the
`gibbon:project-state-migrate` skill instead. If it has code but no docs, scaffold around the code, and read enough of
it to fill `CLAUDE.md`'s Paths, Layout and Build sections.

## 2. Ask

Ask only what the files can't be written without, in one message:

1. The project's goal, in a sentence or two, and the first piece of work with what makes it done (its `done_when`).
2. What `environment.json` should track: a game or app build and where builds are deployed, tool or service versions,
   or nothing.
3. Whether it's an investigation project (reverse engineering, research, tuning by tests), which adds
   `docs/discovery.md` (problem, objective, open questions, routes), `docs/findings/` (evidence by topic, each claim
   Verified with its build or Hypothesis with a confidence) and `docs/tests/` (one file per test).

Skip a question the user has already answered.

## 3. Create

- `docs/state/tasks.json`, `tests.json`, `environment.json` from the templates, with the first tasks the user named and
  `next: true` and the agreed `done_when` on the first. Fill `environment.json`'s `facts` with what step 2 named.
- `docs/status.md` from the template, with the focus filled in.
- `tools/tasks.py`, copied unchanged.
- `tools/project_checks.py` from the template, with `check()` implemented for the `facts` from step 2; leave the file
  out if there are none.
- `CLAUDE.md`: one paragraph on the goal, then Paths, Layout, Build (if any), the Session routine pointer from
  `layout.md`, and
  Working notes for anything the user said about how they want to work. Keep it under about 80 lines.
- The investigation docs from step 2.3, if wanted, with a `docs/tests/README.md` that says how to write a test and to
  add it to `tests.json`.
- `.gitignore` with `scratch/`, `build/` and `.claude/settings.local.json`, plus the language's usual entries.
- `scratch/`, for files the agent manages that aren't committed.

## 4. Check and commit

1. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/session_start.py"` in the project until it passes. Tell the user the
   gibbon plugin's hook shows its output at the start of every session from the next one on.
2. If `CLAUDE.md` imports any file outside the project directory, tell the user to approve external imports for this
   project (see their global `CLAUDE.md`) and to confirm with `/context`.
3. `git init` if the directory isn't a repository, then commit everything except ignored files, following the user's
   git rules.

Reply with the files created, one line each, and the session start check's Next section.
