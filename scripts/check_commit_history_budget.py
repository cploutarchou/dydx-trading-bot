#!/usr/bin/env python3
"""Enforce the repository's commit-history budget: at most 4 commits per
calendar day on a branch, as GitHub's commit history displays them.

Usage: check_commit_history_budget.py <before-sha> <after-sha>

- Checks every calendar day touched by the commits in before..after.
- For each touched day, counts ALL commits reachable from after that share
  that author date (merged PR commits included, matching what GitHub shows).
- Also validates committer-date grouping, since rebases/cherry-picks can
  concentrate old-dated commits onto a new day.
Exits non-zero with a report when any day exceeds the budget.
"""
import subprocess
import sys
from collections import Counter

MAX_COMMITS_PER_DAY = 4


def git(*args):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def main():
    if len(sys.argv) != 3:
        print("usage: check_commit_history_budget.py <before> <after>", file=sys.stderr)
        return 2
    before, after = sys.argv[1], sys.argv[2]
    zero = "0" * 40
    if before in (zero, after):
        print("history-budget: new-branch or no-op push, skipping")
        return 0

    try:
        pushed = git("rev-list", f"{before}..{after}").split()
    except subprocess.CalledProcessError:
        # Divergent histories (force push / rewrite): re-check everything.
        pushed = git("rev-list", after).split()

    # Day of every commit reachable from after, by author and committer date.
    lines = git("log", "--format=%H|%ad|%cd", "--date=format:%Y-%m-%d", after).splitlines()
    author_days = {}
    committer_days = {}
    for line in lines:
        sha, aday, cday = line.split("|")
        author_days[sha] = aday
        committer_days[sha] = cday

    author_counts = Counter(author_days.values())
    committer_counts = Counter(committer_days.values())

    touched = {author_days[s] for s in pushed if s in author_days}
    touched |= {committer_days[s] for s in pushed if s in committer_days}

    violations = []
    for day in sorted(touched):
        for label, counts in (("author-date", author_counts), ("committer-date", committer_counts)):
            if counts[day] > MAX_COMMITS_PER_DAY:
                violations.append(f"{day}: {counts[day]} commits ({label}) exceeds budget of {MAX_COMMITS_PER_DAY}")

    if violations:
        print("history-budget: FAIL — commit budget exceeded:")
        for v in violations:
            print(f"  - {v}")
        print(
            "Consolidate the day's commits (e.g. interactive rebase, or\n"
            "`git reset --soft <first-commit-of-day>^` + one combined commit)\n"
            "and force-push. Repository rule: max 4 commits per calendar day."
        )
        return 1

    busiest = max(author_counts.items(), key=lambda kv: kv[1]) if author_counts else ("none", 0)
    print(
        f"history-budget: OK — {len(touched)} day(s) checked, "
        f"busiest {busiest[0]} with {busiest[1]} commit(s) (budget {MAX_COMMITS_PER_DAY})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
