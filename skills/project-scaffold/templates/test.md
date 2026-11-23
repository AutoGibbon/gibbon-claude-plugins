# <test id>: <what it checks, as in tests.json>

Status, date, build and the one-line result are in `docs/state/tests.json`; this file holds the detail.

## Checks

What the test establishes and what result would count as a pass. Fixed once the test has run.

## Setup

What must be true before the steps: the build, deployed artefacts, installed tools or mods and their settings, and the
state to start from.

## Steps

1. Each action, with exact commands, inputs and values.

## Results

What happened at each step: values, log lines, and the paths of any captures kept.

## Conclusion

What the results show for the checks and the tasks the test bears on, marked Verified (with the build) or Hypothesis
(with a confidence). Its first line is the test's `result` in `tests.json`.
