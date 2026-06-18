# Draft PR Creation Automation Spec

## Purpose

Automate the final handoff step after a worker run and separate reviewer pass have succeeded.

This automation creates a **draft PR only**. It does not merge, mark ready for review, deploy, close issues, change repo settings, edit secrets, or make product decisions.

The goal is to make the PR handoff repeatable and auditable, not to remove the human gate.

## Current state

Today, the loop can:

1. classify issues in manager dry-run mode,
2. apply approved labels and Agent Assessment comments,
3. select one eligible worker issue,
4. create a branch/worktree,
5. write a worker plan before editing,
6. make one bounded docs/test fixture change,
7. run verification,
8. write a worker run report,
9. run a separate reviewer/checker pass,
10. write a reviewer report.

The draft PR creation step was performed manually for the first pilot PR.

This spec defines the next automation layer:

```text
reviewer pass
  → render PR body from artifacts
  → create draft PR
  → comment PR link/run report on issue
  → write PR creation report
  → stop at human gate
```

## Non-goals

This automation must not:

- merge PRs,
- mark PRs ready for review by default,
- deploy,
- publish,
- close issues,
- change repo settings,
- change permissions,
- edit secrets,
- create or edit unrelated issues,
- repair worker output,
- override reviewer findings,
- create PRs for `revise` or `human_escalation` reviewer results.

## Proposed files

Implementation:

```text
src/agent_looop/draft_pr.py
scripts/create_draft_pr.py
tests/test_draft_pr.py
```

Reports:

```text
reports/pr-runs/issue-<number>-draft-pr.md
```

## CLI shape

```bash
python scripts/create_draft_pr.py \
  --repo MichaelAtherton/agent-looop \
  --worktree /tmp/agent-looop-worktrees/issue-1 \
  --issue 1 \
  --base main
```

Optional flags:

```bash
--dry-run                 # render body/report but do not create PR or comment
--title "Fix broken README link"
--output reports/pr-runs/issue-1-draft-pr.md
```

Default behavior:

- validates all gates before any GitHub mutation,
- pushes the worker branch if needed,
- creates a draft PR,
- writes a PR creation report in the worktree,
- commits/pushes that PR creation report back to the same worker branch,
- posts or updates an issue run report comment with the PR link,
- exits non-zero on any gate failure.

Ordering matters: the PR URL does not exist until after `gh pr create --draft`, so the PR creation report is necessarily written after PR creation and then pushed as a follow-up commit to the same draft PR branch.

## Inputs

Required:

| Input | Source | Purpose |
|---|---|---|
| repo | CLI | GitHub repo, e.g. `MichaelAtherton/agent-looop` |
| issue number | CLI | Source issue to link/comment |
| worktree path | CLI | Worker output branch/worktree |
| base branch | CLI/default | PR target branch, default `main` |

Discovered from worktree/GitHub:

| Input | Source | Purpose |
|---|---|---|
| branch name | `git branch --show-current` | PR head branch |
| changed files | `git diff --name-only <base>...HEAD` + untracked check | Scope/audit check |
| worker plan | `reports/worker-plans/issue-<n>-plan.md` | PR body Plan section |
| worker run report | `reports/worker-runs/issue-<n>-worker-run.md` | Verification evidence |
| reviewer report | `reports/reviewer-runs/issue-<n>-reviewer-report.md` | Reviewer evidence/gate |
| issue title/body/labels/url | GitHub API / `gh issue view` | Source context and final eligibility check |
| existing PR | `gh pr list --head <branch>` | Idempotency / duplicate prevention |

## Preconditions / gates

The script must stop before creating a PR unless all conditions are true.

### Git/worktree gates

- Worktree exists.
- Current branch is not `main`.
- Branch name starts with expected worker prefix, e.g. `agent/issue-`.
- Branch has been pushed or can be pushed to origin.
- Worktree has no uncommitted changes before PR creation.
- Diff against base branch is non-empty.
- Branch is up to date with the latest base branch, or the script explicitly reports that rebase/merge is required before PR creation.
- After the PR creation report is written, only `reports/pr-runs/issue-<n>-draft-pr.md` may be newly changed before the report commit.

### Issue eligibility gates

The source issue must have:

```text
risk:low
agent:ready
```

The source issue must not have:

```text
needs:human
agent:blocked
risk:medium
risk:high
```

For the current prototype, issue type must be one of:

```text
type:docs
type:test
```

### Artifact gates

Required files must exist:

```text
reports/worker-plans/issue-<n>-plan.md
reports/worker-runs/issue-<n>-worker-run.md
reports/reviewer-runs/issue-<n>-reviewer-report.md
```

Worker run report must include:

```text
- Result: pass
```

Reviewer report must include:

```text
- Recommendation: pass
```

If reviewer report says either of the following, the script must stop:

```text
- Recommendation: revise
- Recommendation: human_escalation
```

### PR gates

- No existing open PR from the same branch, unless the script is explicitly updating a PR body in a later version.
- PR must be created with `--draft`.
- PR body must include the human gate language.

## PR title

Default title:

```text
<Issue title>
```

For issue #1:

```text
Fix broken README link
```

Future improvement may support conventional prefixes, but v1 should keep issue title unchanged for traceability.

## PR body contract

The generated draft PR body must include:

```markdown
## Summary

[Short description of what changed.]

## Source issue

Refs #[issue]

## Task packet

- Goal:
- Scope:
- Out of scope:
- Allowed actions:
- Forbidden actions:

## Plan

[Plan excerpt or path to plan artifact.]

## Acceptance criteria

- [x] ...

## Verification

Commands run:

- `...` — pass/fail

Worker report:

- `reports/worker-runs/issue-<n>-worker-run.md`

## Reviewer result

Reviewer report:

- `reports/reviewer-runs/issue-<n>-reviewer-report.md`

- Critical issues:
- Warnings:
- Suggestions:
- Recommendation:

## Known limitations / follow-ups

- ...

## Human gate

This PR is draft-only. Human review/merge required.
```

## Issue comment contract

After draft PR creation, post or update an issue comment containing:

```markdown
## Worker Run Report

Worker completed the bounded task and opened a draft PR after separate reviewer pass.

- Worker branch:
- Draft PR:
- Worker plan:
- Worker run report:
- Reviewer report:
- Verification:
- Reviewer recommendation:

Human gate: PR is draft-only. Human review/merge required.
```

The script must upsert this comment rather than creating duplicates. It should find an existing comment on the issue whose body starts with the stable heading and update that comment. If no matching comment exists, it may create one.

Stable heading:

```text
## Worker Run Report
```

## PR creation report contract

Write a local report in the worker branch:

```text
reports/pr-runs/issue-<n>-draft-pr.md
```

The report is written after the draft PR exists, because it must include the PR URL. The script must then commit and push this report to the same worker branch so the audit artifact appears in the draft PR.

Required fields:

```markdown
# Draft PR Creation Report — issue-<n>

## Summary
- Run time:
- Repo:
- Issue:
- Branch:
- Base:
- Draft PR:
- Issue comment:
- PR created as draft: yes
- Merge performed: no

## Gates checked
- Issue eligibility:
- Worker report present:
- Worker verification passed:
- Reviewer report present:
- Reviewer recommendation:
- Existing PR check:
- Worktree cleanliness:

## Artifacts
- Worker plan:
- Worker run report:
- Reviewer report:

## Human gate
This PR is draft-only. Human review/merge required.
```

## Execution sequence

The script should execute in this order:

1. Load GitHub issue state and local worktree state.
2. Validate issue eligibility, artifacts, reviewer result, verification result, branch name, base freshness, and existing PR state.
3. Render PR body and issue comment locally.
4. If `--dry-run`, print/write the rendered artifacts and stop without GitHub mutation.
5. Push the worker branch if needed.
6. Create the PR using `gh pr create --draft`.
7. Write `reports/pr-runs/issue-<n>-draft-pr.md` with the PR URL and all gate results.
8. Commit and push the PR creation report to the worker branch.
9. Upsert the issue run report comment with the PR URL.
10. Stop. Do not merge, mark ready, close issue, or apply completion labels.

## Idempotency behavior

If an open PR already exists for the branch:

V1 acceptable behavior:

- stop with clear error:

```text
Open PR already exists for branch <branch>: <url>
```

Future behavior:

- update PR body,
- update issue comment,
- update PR creation report.

V1 should not create duplicate PRs.

## Failure behavior

### Reviewer result is `revise`

Stop with:

```text
Reviewer requested revise. No PR created. Worker may make one in-scope repair attempt before reviewer rerun.
```

### Reviewer result is `human_escalation`

Stop with:

```text
Reviewer requested human escalation. No PR created. Human decision required.
```

### Missing report artifact

Stop with a specific missing path.

### Verification not passed

Stop and state that worker verification did not pass.

### Issue no longer eligible

Stop and state current labels.

### Existing PR found

Stop and print the existing PR URL.

## Deterministic vs GitHub mutation split

Deterministic local logic:

- validate gates,
- parse report artifacts,
- render PR body,
- render issue comment,
- render PR creation report.

GitHub mutations:

- `gh pr create --draft`,
- `gh issue comment`,
- optional `git push` if branch is not already pushed.

No LLM judgment should be needed in this script.

## Test plan

Add tests for:

1. PR body rendering includes all required sections.
2. Reviewer `pass` allows draft PR action construction.
3. Reviewer `revise` blocks PR creation.
4. Reviewer `human_escalation` blocks PR creation.
5. Missing worker report blocks PR creation.
6. Missing reviewer report blocks PR creation.
7. Failed verification blocks PR creation.
8. Ineligible issue labels block PR creation.
9. Existing PR blocks duplicate creation.
10. Issue comment rendering includes PR link, branch, reports, verification, and human gate.
11. Issue comment upsert updates an existing `## Worker Run Report` comment instead of creating a duplicate.
12. PR creation report is written only after a PR URL exists and is committed/pushed as a follow-up branch commit.
13. Stale branch/base state blocks PR creation or emits an explicit rebase-required error.

Integration/manual verification:

```bash
python -m pytest
python scripts/create_draft_pr.py \
  --repo MichaelAtherton/agent-looop \
  --worktree /tmp/agent-looop-worktrees/issue-1 \
  --issue 1 \
  --base main \
  --dry-run
```

Then, after dry-run output is approved:

```bash
python scripts/create_draft_pr.py \
  --repo MichaelAtherton/agent-looop \
  --worktree /tmp/agent-looop-worktrees/issue-1 \
  --issue 1 \
  --base main
```

## Definition of done

This automation is done when:

- tests pass,
- script refuses `revise` and `human_escalation`,
- script refuses missing/failed verification,
- script refuses ineligible issues,
- script opens draft PR only after reviewer `pass`,
- PR body includes worker and reviewer evidence,
- issue receives an upserted run report / PR link comment,
- PR creation report is written after PR creation, committed, and pushed to the draft PR branch,
- no merge/deploy/publish/repo-settings/secrets action occurs,
- human merge gate remains intact.

## Open decisions

1. Should `agent:in-progress` be introduced before automating the second worker run?
   - Recommended: yes before repeated/scheduled worker runs, but not required for this one-off pilot.
2. Should `agent:complete` be applied when the draft PR opens or only after merge?
   - Recommended: only after merge, or use a separate future `agent:pr-opened` label if needed.
3. Should stale branch handling auto-rebase simple documentation branches, or always stop for human review?
   - Recommended: stop with an explicit rebase-required message for v1; auto-rebase can come after the PR path is proven.
