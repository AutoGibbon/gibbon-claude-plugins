# gibbon

Claude Code plugin for project state tracking. This repo is both the plugin and a one-plugin marketplace.

- `gibbon:project-scaffold` - set up a new project's state layout. `skills/project-scaffold/layout.md` defines the
  layout all three skills share.
- `gibbon:project-state-migrate` - audit an existing project's state tracking and optionally migrate it to the layout.
- `gibbon:wrap-up` - record session state and commit before starting a fresh session.

A `SessionStart` hook notes when a `docs/state/` project's `tools/check_state.py` or `tools/tasks.py` is missing or
differs from the template.

## Install

```
claude plugin marketplace add F:\GIT\claude-project-skills
claude plugin install gibbon@gibbon
```

## Update

Claude Code runs an installed copy, not this repo. After changing a file, bump `version` in
`.claude-plugin/plugin.json`, then run `claude plugin marketplace update gibbon` and `claude plugin update gibbon@gibbon`;
without the version bump the installed copy stays stale.
