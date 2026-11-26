---
name: wrap-up
description: End a working session so a fresh one can pick up without this conversation - record the session's state, results and agreed next steps in the project's own docs, commit, and tell the user to start a new session. Use whenever the user says "wrap up", "wrap it up", "let's stop here", "save state", "clean session", "fresh session", "start new", "hand off", or asks whether a clean session is worth it and the answer is yes. Works in any project; it adapts to wherever and however the project already records its state.
---

# Wrap up

Leave the project so that a fresh session, with none of this conversation, can carry on correctly. Everything the
next session needs must be in files the project already reads at startup or points to from there. Nothing in this
conversation survives otherwise.

## 1. Find where this project keeps its state

Read the project's CLAUDE.md (and any files it imports), the user's global CLAUDE.md, and the memory index if there
is one. Look for:

- the docs it names for status, next steps, decisions, findings, test results, changelogs or tool lists;
- its conventions for them: tables, dated entries, "verified vs hypothesis" rules, index rows that must be added
  for new files, which build or version a finding depends on;
- its git rules: whether to commit, which branch, attribution lines, what must never be committed;
- rules about keeping artifacts (logs, captures, test outputs) before they're overwritten;
- memory rules that say what to persist at the end of a session.

Use the project's own structure. Don't add a handoff file, a new folder or a new format if the project already has
a place for this. If the project has no state doc at all, ask the user where the state should go before creating
anything.

## 2. List what this session changed or decided that isn't recorded yet

Go back through the conversation and collect:

- results: tests run and what they showed, measurements, verified findings, hypotheses still open;
- decisions and agreements, including ones the user made in passing ("go with 0.7", "drop test 18");
- approaches tried or considered and rejected, with the reason, so the next session doesn't retry them;
- assumptions the next step depends on that were settled only in discussion;
- the agreed next step, and anything deferred for later, with enough detail to act on without this chat (addresses,
  file paths, values, the reason it was chosen);
- things noticed but not acted on;
- files and tools created or changed, and installed or deployed state the next session must know about;
- user corrections or preferences that should outlive the session (save these as memories if the memory rules say so).

Write the list out, and next to each item give the file and section that already records it, or MISSING. Don't
count something as recorded because you remember it being discussed, or because only a commit message holds it:
point to the text. Only the MISSING items need writing.

## 3. Write it into the project's docs

- Update the status or "where we are" doc so its next step is the agreed one, not a stale one (in a `docs/state/`
  project, the `next` flags in `tasks.json`; see below).
- Write results into the findings or test docs the project uses, in its format, with dates as absolute dates and
  the build or version they depend on when the project tracks that.
- Add index rows, tool-table rows or README entries for anything new.
- Copy ephemeral artifacts the project says to keep (logs, captures) to where it keeps them.
- Correct anything this session proved wrong, rather than appending a contradiction.

Write for a reader who wasn't here: name the actual files, functions, values and commands. Keep each doc's existing
length and tone; this is an update, not a rewrite, except for `docs/status.md` in a `docs/state/` project.

If the project has `docs/state/` (the layout in `${CLAUDE_PLUGIN_ROOT}/skills/project-scaffold/layout.md`):

- Set task statuses, evidence and `next` flags in `tasks.json`, with what showed each `done`: a test, a command and
  its output, or the user's confirmation.
- Add or fill `tests.json` entries, and update `environment.json`.
- Rewrite `docs/status.md` as focus, half-done work and gotchas, rather than appending to it. Put notes for upcoming
  tasks in their `detail` docs and facts in findings, as "What `status.md` holds" in `layout.md` says.
- Run the session start check, `python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/session_start.py"`, from the project
  directory. Fix its errors before committing. Report its warnings to the user, such as a task
  started this session with no `done_when`, rather than filling them in without asking.

## 4. Check and commit

- Check that links and paths you wrote resolve.
- Run `git status` and look at what will be committed. Leave out scratch, build output, secrets and anything the
  project ignores. If unrelated or unexpected changes are present, ask before including them.
- Commit to the current branch, following the project's and user's git rules: message style, attribution lines or
  the rule against them, no pushing unless asked. Summarise the session's outcome in the message, not the steps
  taken. If the rules say not to commit without asking, ask.

## 5. Cold-read the handoff

Read the handoff as a fresh session would, from the committed state. This session can't judge its own docs, because
it fills gaps from the conversation without noticing, so spawn a read-only subagent on Sonnet (Agent tool
`model: "sonnet"`) and give it only this prompt, with no summary of the session or hint of what you expect:

> This is the start of a fresh session in this project. Follow the project's CLAUDE.md startup routine (if the
> project has `docs/state/`, run `python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/session_start.py"` from the project
> directory as its startup check), then read what it points you to for the next task. Don't change any
> files. Report: which task you'd work on, what done looks like for it, your first three concrete steps, what
> you'd need to ask the user before starting, and anything that reads as ambiguous, contradictory or stale.

Compare its answer with what this session intends next. Treat every difference as a gap in the docs, not a mistake
by the reader: fix the docs, commit the fixes, and tell the user what you added. If the project has no CLAUDE.md,
name its status doc in the prompt instead. If subagents aren't available, re-read the status doc's next step and ask
whether a fresh session could act on it alone.

## 6. Report and hand over

Reply briefly with:

- where things stand and the next step, as the docs now record it;
- the files changed, one line each, and the commit hashes;
- what the cold read got wrong or asked about, and what you added to the docs because of it;
- anything left uncommitted or unresolved, and why.

End by telling the user the state is saved and they can start a fresh session (`/clear` or a new chat), and which
doc the new session should start from if the project's startup instructions don't already point there. If the
project has `docs/state/`, say instead that the new session gets the state on startup from the gibbon plugin's hook,
and repeat the `Next:` items. A skill can't clear the session itself.
