# Project state layout

Shared by the `gibbon:project-scaffold` and `gibbon:project-state-migrate` skills. It follows Anthropic's guidance for
long-horizon work across context windows: task and test status in JSON with a fixed schema, short freeform progress
notes, git as the history, and a script that checks the environment at session start.

## Files

| What | Where | Format | Who changes what |
| --- | --- | --- | --- |
| Work items: workstreams, tasks, spec and acceptance items, release steps | `docs/state/tasks.json` | JSON | Claude changes `status`, `evidence`, `blocked_by`, `next` and `updated`. Adding, removing or rewording an item needs the user's agreement |
| Tests | `docs/state/tests.json`, plus one `.md` file per test with its steps and results | JSON index, Markdown detail | Claude adds entries and fills in results. A test's `checks` doesn't change after it runs |
| Environment: builds, deployed artefacts, installed tools or mods that affect tests | `docs/state/environment.json` | JSON | Updated whenever something is built, deployed, installed or toggled |
| Current focus, half-done work, gotchas for the next session | `docs/status.md` | Freeform Markdown, under about 60 lines | Rewritten at the end of each session, not appended to |
| What happened and when | git commits, test files, the project's changelog | — | Never copied back into `status.md` |
| Session start check | The gibbon plugin's `scripts/session_start.py`, which runs the plugin's `scripts/check_state.py`, run by the plugin's `SessionStart` hook | Script | Read-only |
| The project's own environment checks | `tools/project_checks.py`: `check(root, env)` returns a message for each check that fails | Script | Read-only |
| Task and test queries | `tools/tasks.py`: `list`, `show`, `deps` (what a task waits on and what waits on it) and `tests` | Script | Read-only |

Templates for every project file are in `templates/` next to this file. `tasks.py` is copied unchanged;
`project_checks.py` gets the project's own checks, and a project with none leaves it out. The plugin's scripts are in
`scripts/`, two folders above this file.

## How strict

`check_state.py` fails only on broken structure: a missing or invalid file, a bad id or status, or a reference to a
task, test, commit or path that doesn't exist. Gaps in process (no `done_when` on work in progress, `done` with no
evidence, a run test with no result, `blocked` with no `blocked_by`) are warnings, so they show at every session start
without stopping work. Keep it that way: structural errors break the next session's reading of the state, while
process gaps are for the user to weigh.

## Session start check

The gibbon plugin's `SessionStart` hook runs `scripts/session_start.py --hook` on startup, `/clear` and compaction in
every project, and Claude Code adds its output to the session's context. In a project with `docs/state/` it prints the
session routine, git status and recent commits, the problems `tools/project_checks.py` and the artefact hash comparison find, notes on
`tools/tasks.py` and on per-project scripts the plugin replaces, and `check_state.py`'s output, which ends with the
tasks to pick up; elsewhere it prints nothing. `--hook` makes the script exit 0 even when a check fails, because the
output only reaches the context on exit 0; the output then ends with a line asking Claude to tell the user. Without
`--hook` it exits 1 on a failed check. Skills run it from the project directory as
`python "${CLAUDE_PLUGIN_ROOT}/scripts/session_start.py"`. The scripts use only the standard library, so any `python`
on `PATH` runs them.

## `tasks.json`

```json
{
  "schema": 1,
  "statuses": ["todo", "in_progress", "blocked", "done", "dropped"],
  "items": [
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
- `depends_on`: ids of tasks that must be done first. Order the docs give in prose ("then", "after", "first") goes
  here, so it isn't kept only in prose.

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

- `facts`: whatever `tools/project_checks.py` compares against, such as a game build, a tool version or a service URL.
- `artefacts`: the session start check compares `built` and `deployed` by hash when both are set, so a stale deploy
  shows before a test.
- `installed`: tools, mods or services outside the repo that change results.

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

## Templates in projects

Projects hold a copy of `tasks.py`, which falls behind when the template changes. The session start check notes when
`tools/tasks.py` is missing or differs from its template. It also notes per-project scripts from earlier versions of
this layout, `tools/session_start.py` and `tools/check_state.py`, and a `SessionStart` hook in `.claude/settings.json`
that runs them, and a copy of the session routine in `CLAUDE.md`; the plugin replaces them, and
`gibbon:project-state-migrate` removes them.

## Memories

Project memories (`~/.claude/projects/<project-slug>/memory/`) hold preferences and workflow rules, not state. A
memory that records installed or deployed state belongs in `environment.json`; one that names a status file or index
row must name the files above.
