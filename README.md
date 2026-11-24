# gibbon marketplace

Claude Code plugins, one folder each under `plugins/`:

- [`gibbon`](plugins/gibbon/README.md) - project state tracking: scaffold a project, audit and migrate an existing one,
  and wrap up a session.
- `bg-tasks` - a band above the prompt listing running background tasks and subagents, and scheduled prompts.
- [`usage-meter`](plugins/usage-meter/README.md) - a line above the prompt with chat fullness, plan limits and cache
  warmth, a hold before sending to a cold chat, and `/keepwarm` to keep the cache warm while idle.

## Install

```
claude plugin marketplace add F:\GIT\claude-project-skills
claude plugin install gibbon@gibbon
claude plugin install bg-tasks@gibbon
claude plugin install usage-meter@gibbon
```

## Update

Claude Code runs an installed copy, not this repo. After changing a plugin's files, bump `version` in
`plugins/<plugin>/.claude-plugin/plugin.json`, then run `claude plugin marketplace update gibbon` and
`claude plugin update <plugin>@gibbon`; without the version bump the installed copy stays stale.

## Adding a plugin

Put it in `plugins/<name>/` with its own `.claude-plugin/plugin.json`, and add
`{ "name": "<name>", "source": "./plugins/<name>" }` to `plugins` in `.claude-plugin/marketplace.json`.

A mod's (a plugin with a `hooks.json` `modules` entry) tests run with `claude plugin test plugins/<name>`, and
`claude plugin validate plugins/<name>` checks its module.
