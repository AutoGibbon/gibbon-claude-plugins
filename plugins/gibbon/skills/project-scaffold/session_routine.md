- **Start:** raise any problems and notes this check reports with the user; `info:` lines describe the current state
  for you. `docs/status.md` is printed below; work on the `next` items in `docs/state/tasks.json` unless the user says
  otherwise.
- **Queries:** list, show and trace tasks, workstreams and tests with
  `python -X utf8 "{plugin}/scripts/tasks.py" list|show|deps|streams|tests` (`--help` for options), not one-off
  scripts over the JSON.
- **Starting a task:** agree its `done_when` with the user when setting it `in_progress`. Check the open questions in
  the findings docs the task touches; one it depends on becomes a task or a `done_when` line now. If the task's
  workstream isn't `in_progress` yet, check its `depends_on` are done and set it `in_progress` first, telling the user.
- **During:** update a JSON entry in `docs/state/` when its state changes, not at the end. Write an open question into
  its findings doc, and a note for an upcoming task into the doc its `detail` points to, when it comes up. When a
  result answers an open question, take it off its list in the same commit. Commit after each finished step, with a
  message saying what changed and why.
- **Writing a test:** start the file from `{plugin}/skills/project-scaffold/templates/test.md`, follow
  `docs/tests/README.md` if the project has one, and add the test to `docs/state/tests.json`.
- **Done:** record in `evidence` what showed it: a test, a command and its output, or the user's confirmation. For
  code, scripts or data Claude can check without the user, a review by a session that didn't write it (`/code-review`,
  or a read-only reviewer subagent given the task's `done_when`, reporting correctness gaps only and skipping style)
  can help; skip it where it adds cost without catching anything.
- **End** (the `gibbon:wrap-up` skill): set statuses and `next` flags, add or fill `tests.json` entries, update
  `environment.json`, rewrite `docs/status.md`, commit. Don't end a session with uncommitted work.
- **Rules:** never delete or reword a task or test entry, or change a run test's `checks`, without the user's agreement;
  a hook asks the user before such an edit goes through. Mark findings Verified (with the build) or Hypothesis (with a
  confidence: low, medium or high).
