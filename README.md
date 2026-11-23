# claude-project-skills

Personal Claude Code skills for project state tracking:

- `project-scaffold` - set up a new project's state layout. `project-scaffold/layout.md` defines the layout all three
  skills share.
- `project-state-migrate` - audit an existing project's state tracking and optionally migrate it to the layout.
- `wrap-up` - record session state and commit before starting a fresh session.

## Install

Claude Code loads personal skills from `~/.claude/skills/<name>/`. Link each skill directory there (PowerShell):

```powershell
foreach ($n in 'project-scaffold','project-state-migrate','wrap-up') {
    New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\$n" -Target "$PWD\$n"
}
```

The skills and `templates/session_start.py` reference `~/.claude/skills/project-scaffold/...` by path, so the links
must use these exact names.
