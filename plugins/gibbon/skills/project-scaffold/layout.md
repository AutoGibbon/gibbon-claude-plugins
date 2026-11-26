# Project state layout

Shared by the `gibbon:project-scaffold` and `gibbon:project-state-migrate` skills. It follows Anthropic's guidance for
long-horizon work across context windows: task and test status in JSON with a fixed schema, short freeform progress
notes, git as the history, and a script that checks the environment at session start.

## Files

| What | Where | Format | Who changes what |
| --- | --- | --- | --- |
| Work items: workstreams, tasks, spec and acceptance items, release steps | `docs/state/tasks.json` | JSON | Claude changes `status`, `evidence`, `blocked_by`, `next` and `updated`. Adding, removing or rewording an item needs the user's agreement |
| Tests | `docs/state/tests.json`, plus one `.md` file per test in `docs/tests/` with its steps and results | JSON index, Markdown detail | Claude adds entries and fills in results. A test's `checks` doesn't change after it runs |
| Environment: builds, deployed artefacts, installed tools or mods that affect tests | `docs/state/environment.json` | JSON | Updated whenever something is built, deployed, installed or toggled |
| Current focus, half-done work, gotchas for the next session | `docs/status.md` | Freeform Markdown, under about 60 lines | Rewritten at the end of each session, not appended to |
| What happened and when | git commits, test files, the project's changelog | — | Never copied back into `status.md` |
| Session start check | The gibbon plugin's `scripts/session_start.py`, which runs the plugin's `scripts/check_state.py`, run by the plugin's `SessionStart` hook | Script | Read-only |
| The project's own environment checks | `tools/project_checks.py`: `check(root, env)` returns a message for each check that fails, or `(problems, notes)` or `(problems, notes, info)`: notes are raised with the user without failing the check, info is current state for Claude alone | Script | Read-only |
| Task and test queries | The gibbon plugin's `scripts/tasks.py`: `list`, `show`, `deps` (what a task waits on and what waits on it), `streams` and `tests` | Script | Read-only |
| Edit checks | The gibbon plugin's `PreToolUse` and `PostToolUse` hooks on edits to `docs/state/` | Hook | — |
| Python in UTF-8 mode | `.claude/settings.json`: `"env": {"PYTHONUTF8": "1"}`, which Claude Code passes to every command and hook it runs in the project | JSON | Kept alongside any other settings the project has |

Templates for project files are in `templates/` next to this file: `project_checks.py` gets the project's own checks,
and a project with none leaves it out. The plugin's scripts are in `scripts/` and its hooks in `hooks/`, two folders
above this file.

## How strict

`check_state.py` fails only on broken structure: a missing or invalid file, a bad id, status or `kind`, a reference to
a task, workstream, test, commit or path that doesn't exist, a nested workstream, or a dependency cycle. Gaps in
process (no `done_when` on work in progress, `done` with no evidence, a run test with no result, `blocked` with no
`blocked_by`, work started before what it waits on is done) are warnings, so they show at every session start
without stopping work. Keep it that way: structural errors break the next session's reading of the state, while
process gaps are for the user to weigh.

## Session start check

The gibbon plugin's `SessionStart` hook runs `scripts/session_start.py --hook` on startup, `/clear` and compaction in
every project, and Claude Code adds its output to the session's context. In a project with `docs/state/` it prints:

- the session routine, with the plugin's path filled in;
- git status and recent commits, and on startup, `/clear` or resume, a note that uncommitted changes are left over;
- the problems `tools/project_checks.py` and the artefact hash comparison find, and notes on per-project scripts the
  plugin replaces;
- `check_state.py`'s output, which ends with the tasks to pick up;
- `docs/status.md`.

Elsewhere it prints nothing. `--hook` makes the script exit 0 even when a check fails, because the
output only reaches the context on exit 0; the output then ends with a line asking Claude to tell the user. Without
`--hook` it exits 1 on a failed check. Skills run it from the project directory as
`python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/session_start.py"`. The scripts use only the standard library, so any
`python` on `PATH` runs them. `-X utf8` puts Python in UTF-8 mode; without it, Python on Windows reads and prints in
the console's code page and fails on characters outside it.

## Edit checks

Two plugin hooks run on `Edit`, `MultiEdit` and `Write` calls to `docs/state/`:

- `hooks/guard_state.py` (`PreToolUse`) asks the user before an edit to `tasks.json` that adds or removes a task or
  changes a task field other than `status`, `evidence`, `blocked_by`, `next` and `updated`, and before an edit to
  `tests.json` that removes a test or changes the `checks` of one that has run. Creating either file goes through,
  since the scaffold and migrate skills agree its contents with the user first.
- `hooks/post_state_check.py` (`PostToolUse`) runs `check_state.py` after the edit and reports its errors to Claude to
  fix, and its warnings on the entries the edit touched to raise with the user.

`hooks/pre_bash_state_stamp.py` (`PreToolUse`) records the modification times of the files in `docs/state/` before a
Bash call, and `hooks/post_bash_state_check.py` (`PostToolUse`) runs `check_state.py` when the call changed one and
reports its errors to Claude to fix. Changes made through Bash skip `guard_state.py`'s question.

## `tasks.json`

```json
{
  "schema": 1,
  "statuses": ["todo", "in_progress", "blocked", "done", "dropped"],
  "items": [
    {
      "id": "dawn-fog",
      "kind": "workstream",
      "title": "Morning fog that rolls in and burns off",
      "status": "in_progress",
      "done_when": ["Fog density follows weather stage and time of day, tunable from WeatherMod.toml"],
      "depends_on": [],
      "detail": "docs/findings/fog-volumes.md",
      "updated": "2026-11-22"
    },
    {
      "id": "fog-weather-prefab-patch",
      "workstream": "dawn-fog",
      "title": "Data patch adding a density-0 fog volume to weather.prefab",
      "status": "todo",
      "next": true,
      "done_when": [
        "weather.prefab extracts with the added FogComponent and the patched file loads in game",
        "WeatherMod's fog probe finds the added volume at density 0 in every weather stage"
      ],
      "depends_on": [],
      "evidence": [],
      "detail": "docs/findings/fog-volumes.md#writable-fields",
      "updated": "2026-11-22"
    }
  ]
}
```

- `id`: stable kebab-case. Never reuse or rename one.
- `done_when`: a line or two on what makes the item done, agreed with the user when the item starts. For exploratory
  work it can be the question the work answers. Items finished before the project used this field don't need one.
- `evidence`: what shows the current `status`: test ids, commit hashes, repo paths with an optional `#anchor`, or
  short text such as `run: pytest -q -> 12 passed` or `user 2026-11-22: rain looks right at 1.0`. Ids, hashes and
  paths are checked; text isn't. When the only check was Claude's own review, say so, so the item can be revisited.
- `next`: true on the items to pick up next. It replaces every "Next:" line in prose docs.
- `blocked_by`: required when `status` is `blocked`; free text naming what blocks it, such as "tester must reach a
  ship".
- `detail`: optional repo path, with an optional `#anchor`, to the doc that explains the item.
- `depends_on`: ids of tasks or workstreams that must be done first. Order the docs give in prose ("then", "after",
  "first") goes here, so it isn't kept only in prose.
- `kind`: `"workstream"` on a workstream item; absent on a task.
- `workstream`: optional id of the workstream item the task belongs to.

### Workstreams

A workstream groups tasks toward one goal, held in its `done_when`. It has the same fields as a task except
`workstream`: workstreams don't nest. Its `depends_on` names the tasks or workstreams that must be done before it
starts, not its own tasks; a phase is a workstream that depends on the one before it.

- A workstream goes `in_progress` only once its `depends_on` are done, and its tasks go `in_progress` only while it is
  `in_progress`. Close it once its tasks are closed.
- `next` on a workstream marks the one to start when none is `in_progress`.
- A task that depends on its own workstream, directly or through other items, is a cycle and fails the check.
- Until a project has a workstream item, `workstream` strings on tasks only warn, so projects from before workstreams
  keep passing until `gibbon:project-state-migrate` adds the items.

The session start check groups the Next tasks under each workstream with its goal and task counts, puts tasks with
no workstream under Other, and lists the items ready to start.

Use only the fields shown in these schemas; `check_state.py` warns on others. Explanations, plans and paths go in the
doc that `detail` points to, not in a JSON field.

## `tests.json`

```json
{
  "schema": 1,
  "statuses": ["planned", "passed", "failed", "partial", "inconclusive", "not_run", "aborted"],
  "tests": [
    {
      "id": "test-33",
      "file": "docs/tests/test-33.md",
      "checks": "Fog volume colour and noise through the game's setters",
      "status": "passed",
      "date": "2026-11-22",
      "build": "0x6AFDC0CF",
      "tasks": ["fog-writable-fields"],
      "result": "Setters work safely; _color is B, G, R, A; noise ratio 0 fills, 1 leaves sparse patches"
    }
  ]
}
```

- `result`: one line. Detail stays in the test's `.md` file.
- `build`: the version or build the test ran on, when results depend on it; otherwise omit.
- `tasks`: ids from `tasks.json` that the test bears on.

## `environment.json`

```json
{
  "schema": 1,
  "facts": {
    "exe_timestamp": "0x6AFDC0CF",
    "exe_seen": "2026-11-20"
  },
  "artefacts": [
    {
      "name": "WeatherMod.asi",
      "built": "build/WeatherMod/WeatherMod.asi",
      "deployed": "E:/Tools/mods/crimson desert/DMM/mods/WeatherMod.asi",
      "commit": "cbbcbe3",
      "date": "2026-11-22",
      "enabled": true,
      "notes": "Numpad keys; settings in bin64/WeatherMod.toml"
    }
  ],
  "installed": [
    { "name": "RenoDX", "on": true, "notes": "Changes rendering; on for all tests" }
  ]
}
```

- `facts`: values `tools/project_checks.py` compares against, such as a game build, a tool version or a service URL,
  and reference values tests or releases depend on, such as installed DLC, a test save or the released version.
- `artefacts`: the session start check compares `built` and `deployed` by hash when both are set, so a stale deploy
  shows before a test.
- `installed`: tools, mods or services outside the repo that change results.

## Writing a test

Test files live in `docs/tests/`. Start each one from `templates/test.md`: what it checks, setup, steps, results, and
a conclusion whose first line is the `result` in `tests.json`. A project's `docs/tests/README.md` adds only what is
specific to it, such as how to launch the game or app, log formats and where captures go, and extra sections its tests
need; it doesn't replace the template's layout. A project with nothing specific has no README.

## Session routine

The routine for working in a project is `session_routine.md`, next to this file. The session start check prints it at
the top of its output, so every project gets the current version. A project's `CLAUDE.md` holds this pointer instead
of a copy, so that the routine carries `CLAUDE.md`'s weight:

```markdown
## Session routine

Follow the session routine the gibbon plugin's session start check prints at startup; it is part of these
instructions. If its output isn't in context, tell the user the gibbon plugin isn't enabled.
```

Project-specific rules go in `CLAUDE.md`'s Working notes, not in the routine.

## Open questions

Open questions live in the findings docs, in a "Still open" or "Open questions" section next to the evidence that
bears on them, not in `tasks.json`. A question becomes a task only when planned work needs its answer, which the
"Starting a task" step checks. List each question once, in one findings doc; other docs link to it.

## What `status.md` holds

`status.md` names each upcoming task in a line or two and links to its notes; it doesn't hold them. Notes a task
needs before it starts (topics to raise, candidate ideas, scope questions for the user) go in a "To settle" list in
the doc its `detail` points to, next to the section the task will fill, and its `detail` links to that section. Facts
learned along the way go in findings. Gotchas keep only traps in how the project is worked (keys, switches, deploy
steps, conversions), linking to the finding behind each; a fact about the game or code that a finding already holds
doesn't go there.

## Copies from earlier versions of the layout

Projects set up under earlier versions of this layout hold copies of what the plugin now provides:
`tools/session_start.py`, `tools/check_state.py` and `tools/tasks.py`, a `SessionStart` hook in
`.claude/settings.json` that runs them, and the session routine in `CLAUDE.md`. The session start check notes each
one, and `gibbon:project-state-migrate` removes them.

## Memories

Project memories (`~/.claude/projects/<project-slug>/memory/`) hold preferences and workflow rules, not state. A
memory that records installed or deployed state belongs in `environment.json`; one that names a status file or index
row must name the files above.
