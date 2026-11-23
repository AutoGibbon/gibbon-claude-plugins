---
name: project-state-migrate
description: Audit an existing project's status, next-step and test-result tracking, and optionally migrate it to the project state layout - docs/state/ JSON for tasks, tests and environment, a short docs/status.md, a session start check, and memories and skills pointing at them. Use when the user says "audit the state docs", "migrate this project's status", "bring state tracking in line", or asks where a project's status tracking falls short. Audit alone changes nothing. Not for new projects (use gibbon:project-scaffold).
---

# Audit and migrate project state

The target layout, schemas and rules are in `${CLAUDE_PLUGIN_ROOT}/skills/project-scaffold/layout.md`; read it first.
Templates are in `${CLAUDE_PLUGIN_ROOT}/skills/project-scaffold/templates/`.

The user may hand you an earlier audit for this project. Use it as a starting point, but check each point against the
current files, since they may have changed.

## Audit (read-only)

Read:

- `CLAUDE.md` and any files it imports;
- every doc that records status, next steps, plans, decisions, test results, releases or deployed state (check
  `docs/`, READMEs and changelogs; follow links from `CLAUDE.md`);
- `.claude/skills/*/SKILL.md`, for skills that write any of the above;
- the project's memories, in `~/.claude/projects/<project-slug>/memory/`, where the slug is the project path with
  `:`, `\`, `/` and spaces replaced by `-` (list `~/.claude/projects/` if unsure);
- `git log --oneline -20` and `git status`;
- the files the environment claims describe: deploy folders, installed tools or mods, build outputs. Compare them with
  what the docs say, and list anything present that the docs don't mention.

If the project already has `docs/state/`, also compare `tools/check_state.py` and `tools/tasks.py` with the
templates (report `tasks.py` as missing if it isn't there), and the project's
`tools/session_start.py` and `.claude/settings.json` with the template's features (`--hook`, artefact hashes, the
`SessionStart` hook).

Report, grouped by the layout's files:

1. **Where each kind of state lives now:** task status, next steps, test results, environment and deploys, history.
   Name the file and section for each place.
2. **Gaps against the layout:** the same state in several places, history retold in a status doc, tests or acceptance
   checks with no status, work in progress with no stated definition of done, order between tasks kept only in prose,
   deployed state in prose, design or changelog content in a status doc, status words or dated history in other docs
   ("Answered:", "Partly answered", "settled 2026-11-16", "seen in tests 3-5"), the same open question listed in more
   than one place, project scripts behind the templates, no session start check or hook.

   Name what already works in the project's tracking, and keep it: the aim is to move state into the layout, not to
   add process the project has managed without.
3. **Contradictions:** claims in two places that disagree, such as two different "next" steps, or a doc against the
   files on disk. Quote both. This includes summaries that later findings have overtaken, such as "nothing can write
   this format" when a findings doc records a working writer.
4. **Memories and skills** that name status files, README rows or installed and deployed state, and what each would
   need to say after a migration.

If the user asked for an audit only, stop here.

## Migrate

Do these in order. Commit after each step, following the project's and user's git rules. Lose no information: before
removing a sentence from a prose doc, make sure its fact is in a JSON entry, a test file, a findings or design doc, the
changelog or git history.

1. **Audit** as above. Stop until the user has settled every contradiction.
2. **Create `docs/state/`** and its three JSON files from the current docs. Give each task an `id`, `status` and
   evidence from what the docs say (the tests, commits or docs that settled it); when the docs don't settle a status,
   use `todo` and list it for the user. When you infer a status the docs don't state, such as a test's pass or fail
   from its result text, list each inferred status for the user. Turn order the docs give in prose into
   `depends_on`. Don't add `done_when` to finished items. For `in_progress` and `next` items, take it from the docs'
   acceptance checks, requirements or planned test checks, or propose one and mark it for the user. Don't make tasks
   from open questions unless planned work needs their answer (see "Open questions" in `layout.md`). Use only the
   layout's fields. For an artefact's `commit`, find the commit whose build matches the deployed file, not the one
   the docs name. Show the user `tasks.json`, including the `next` flags, the proposed `done_when` and the inferred
   statuses, and stop until they accept it.
3. **Add the scripts:** copy `check_state.py` and `tasks.py` unchanged to `tools/`, and write `tools/session_start.py` from the
   template with `project_checks()` covering the checks the docs ask for by hand (build or version changes, stale
   extracts, tools or venvs the project relies on). Run it until it passes. Add the `SessionStart` hook from
   `templates/settings.json` to `.claude/settings.json`, merging it into the file if it exists, and pipe-test it:
   `echo '{}' | CLAUDE_PROJECT_DIR="$PWD" python "$PWD/tools/session_start.py" --hook` should exit 0.
4. **Trim the prose docs.** Cut `docs/status.md` to focus, half-done work and gotchas, linking to `docs/state/`.
   In other docs, replace "Next" lists and any status wording or dated history ("done", "(next)", "Answered:",
   "Partly answered", "settled on", "seen in tests") with a link to `tasks.json`; keep their reasoning and decisions.
   Where you keep a summary, check its claims against later findings and correct any that have been overtaken. Leave
   each open question in one findings doc and link to it from elsewhere. Replace test index tables with a link to
   `tests.json`, keeping any reference material (log formats, conventions, how to write a test). Move design detail
   out of status docs into a design doc.
5. **Update `CLAUDE.md`** with the Session routine from `layout.md` and the new file locations. Update skills from the
   audit so they write `docs/state/`. Update or delete the memories from the audit so they name the new files, and
   move state held in memory into `environment.json`; update `MEMORY.md` to match.
6. **Check:** run `tools/session_start.py`, read only `docs/status.md`, and tell the user what the next step is. Ask
   whether it matches what they expect, and tell them the hook runs from the next session on; its output should then
   be in context without running anything. Recommend an audit-only run of this skill in a fresh session: a session
   that didn't do the migration finds what this one can't see in its own work.

Reply with the files changed, one line each, and the commits made.
