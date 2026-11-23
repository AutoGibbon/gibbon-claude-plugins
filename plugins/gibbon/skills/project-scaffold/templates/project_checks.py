"""Check this project's environment for the gibbon plugin's session start check, which calls check() at startup."""


def check(root, env):
    """Return a message for each way the live environment differs from env["facts"], naming the fix.

    root is the project directory as a Path; env is docs/state/environment.json as a dict. To report something that
    isn't a failure, such as stale extracts, return (problems, notes) instead; notes don't fail the check.
    """
    problems = []
    # Compare live state with env["facts"] here, such as a game exe's PE timestamp, a tool version or the age of
    # extracted data, and append a message naming the fix (for example "follow the game-update skill").
    return problems
