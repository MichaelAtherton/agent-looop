# Draft PR Creation Automation — Fresh Session Handoff

Use this document to begin implementing the draft PR creation automation in a fresh Hermes session.

## One-sentence goal

Implement the repo-local automation that turns a passed worker/reviewer run into a **draft PR only**, posts/updates the issue run report comment, writes a PR creation report, and stops at the human merge gate.

## Repository

GitHub:

```text
https://github.com/MichaelAtherton/agent-looop
```

Local working copy used in the previous session:

```text
/tmp/agent-looop
```

If starting fresh, clone or inspect the repo first:

```bash
cd /tmp/agent-looop
 git status --short --branch
 python -m pytest
```

Expected baseline at handoff time:

```text
main is clean and tracking origin/main
23 tests pass
latest main commit: 43daf2e docs: tighten draft PR automation spec
```

## Required reading before implementation

Read these files first:

```text
docs/DRAFT-PR-CREATION-SPEC.md
docs/RUNBOOK.md
docs/REPORT-CONTRACTS.md
src/agent_looop/worker_prototype.py
src/agent_looop/reviewer.py
tests/test_reviewer.py
tests/test_worker_prototype.py
```

The authoritative implementation spec is:

```text
docs/DRAFT-PR-CREATION-SPEC.md
```

Do not implement from memory. Implement from that spec.

## Current loop state

The pilot loop currently supports:

1. manager dry-run,
2. manager apply mode,
3. worker prototype for one eligible docs/test issue,
4. separate reviewer/checker pass,
5. manual draft PR creation.

The missing piece is automating step 5.

Existing modules:

```text
src/agent_looop/manager_dry_run.py
src/agent_looop/manager_apply.py
src/agent_looop/worker_prototype.py
src/agent_looop/reviewer.py
```

Existing CLI wrappers:

```text
scripts/manager_dry_run.py
scripts/manager_apply.py
scripts/worker_prototype.py
scripts/reviewer.py
```

## Current pilot PR

There is an existing draft PR created manually during the pilot:

```text
PR #6: https://github.com/MichaelAtherton/agent-looop/pull/6
Branch: agent/issue-1-fix-broken-readme-link
Base: main
State: open draft
CI: passing
```

Important: do **not** merge PR #6. It is a human-gated artifact.

Because PR #6 already exists, the new automation's duplicate-PR guard can be tested against this branch: it should detect the existing PR and stop rather than creating a duplicate.

## New implementation files

Create:

```text
src/agent_looop/draft_pr.py
scripts/create_draft_pr.py
tests/test_draft_pr.py
```

Generated report path:

```text
reports/pr-runs/issue-<number>-draft-pr.md
```

## CLI target

The intended CLI is:

```bash
python scripts/create_draft_pr.py \
  --repo MichaelAtherton/agent-looop \
  --worktree /tmp/agent-looop-worktrees/issue-1 \
  --issue 1 \
  --base main
```

Also support dry-run:

```bash
python scripts/create_draft_pr.py \
  --repo MichaelAtherton/agent-looop \
  --worktree /tmp/agent-looop-worktrees/issue-1 \
  --issue 1 \
  --base main \
  --dry-run
```

## Critical behavior

The script must:

1. validate all gates before GitHub mutation,
2. refuse reviewer results other than `pass`,
3. refuse missing/failed worker verification,
4. refuse ineligible issue labels,
5. refuse existing open PRs from the same branch,
6. render the PR body from worker/reviewer artifacts,
7. create the PR with `--draft`,
8. write `reports/pr-runs/issue-<n>-draft-pr.md` after the PR URL exists,
9. commit and push that PR creation report to the same worker branch,
10. upsert the issue comment headed `## Worker Run Report`,
11. stop without merging, marking ready, closing issue, deploying, or changing repo settings.

## Hard safety rules

The script must not:

- merge PRs,
- mark PRs ready for review,
- deploy,
- publish,
- close issues,
- change repo settings,
- change permissions,
- edit secrets,
- repair worker output,
- override reviewer findings,
- create PRs for `revise` or `human_escalation` reviewer results.

## Recommended implementation sequence

Use TDD. Keep commits small.

### Task 1 — Add deterministic model/render tests

Create `tests/test_draft_pr.py` with tests for:

- PR body rendering includes required sections,
- issue comment rendering includes PR URL, branch, reports, verification, reviewer result, and human gate,
- PR creation report rendering includes gate results and PR/comment URLs.

Run:

```bash
python -m pytest tests/test_draft_pr.py -q
```

Expected first result: failure because `agent_looop.draft_pr` does not exist.

### Task 2 — Implement pure rendering/data functions

Create `src/agent_looop/draft_pr.py` with dataclasses and pure functions first.

Suggested objects:

```python
DraftPrInput
DraftPrGateResult
DraftPrArtifacts
DraftPrResult
```

Suggested pure functions:

```python
render_pr_body(...)
render_issue_comment(...)
render_pr_creation_report(...)
parse_worker_report(...)
parse_reviewer_report(...)
```

No GitHub mutation in this task.

Run:

```bash
python -m pytest tests/test_draft_pr.py -q
python -m pytest
```

### Task 3 — Add gate validation tests

Add tests for:

- reviewer `revise` blocks PR creation,
- reviewer `human_escalation` blocks PR creation,
- missing worker report blocks,
- missing reviewer report blocks,
- failed verification blocks,
- ineligible issue labels block,
- existing PR blocks duplicate creation,
- stale base branch returns explicit rebase-required result or error.

### Task 4 — Implement gate validation

Implement deterministic validation in `draft_pr.py`.

Prefer returning structured results/errors over relying on printed strings.

No `gh pr create` yet.

### Task 5 — Add CLI wrapper

Create:

```text
scripts/create_draft_pr.py
```

Pattern should match existing wrappers:

```python
#!/usr/bin/env python
from agent_looop.draft_pr import main

if __name__ == "__main__":
    raise SystemExit(main())
```

### Task 6 — Implement dry-run mode

Dry-run must:

- validate gates,
- render PR body,
- render issue comment,
- render planned PR creation report,
- perform no GitHub mutations.

Run dry-run against the existing PR #6 branch if available, but expect the existing PR gate to block unless the test fixture uses a branch without an existing PR.

### Task 7 — Implement GitHub mutation path

Only after tests pass:

- push branch if needed,
- create draft PR with `gh pr create --draft`,
- write PR creation report after PR URL exists,
- commit and push report,
- upsert issue comment.

Use subprocess calls to `gh` and `git`, consistent with the rest of the repo.

### Task 8 — Update docs if behavior differs

If implementation requires changing the spec, update `docs/DRAFT-PR-CREATION-SPEC.md` first or in the same commit with a clear explanation.

## Acceptance criteria

Implementation is acceptable when:

- `python -m pytest` passes,
- `scripts/create_draft_pr.py --dry-run` works without GitHub mutation,
- existing PR branch is detected and duplicate PR creation is refused,
- reviewer `revise` and `human_escalation` are refused,
- missing report artifacts are refused with exact paths,
- PR body includes worker and reviewer evidence,
- issue comment is upserted, not duplicated,
- PR creation report is written after PR URL exists,
- no merge/deploy/close/ready-for-review action occurs.

## Smoke test commands

Baseline:

```bash
cd /tmp/agent-looop
python -m pytest
```

Dry-run, after implementation:

```bash
python scripts/create_draft_pr.py \
  --repo MichaelAtherton/agent-looop \
  --worktree /tmp/agent-looop-worktrees/issue-1 \
  --issue 1 \
  --base main \
  --dry-run
```

Duplicate PR guard, using existing PR #6 branch:

```bash
python scripts/create_draft_pr.py \
  --repo MichaelAtherton/agent-looop \
  --worktree /tmp/agent-looop-worktrees/issue-1 \
  --issue 1 \
  --base main
```

Expected result if PR #6 still exists:

```text
Open PR already exists for branch agent/issue-1-fix-broken-readme-link: https://github.com/MichaelAtherton/agent-looop/pull/6
```

## Stop rule

After implementing the draft PR creation automation and passing the tests/smoke checks, stop and report.

Do not expand into:

- scheduled runs,
- `agent:in-progress` locking,
- generalized issue types,
- auto-rebase,
- merge automation,
- closing issues,
- production Hermes plugin packaging.

Those are later phases.

## Suggested first message in a fresh session

Paste this:

```text
We are in /tmp/agent-looop. Please implement docs/DRAFT-PR-CREATION-SPEC.md. Start by reading docs/DRAFT-PR-AUTOMATION-HANDOFF.md and the spec. Use TDD. Create src/agent_looop/draft_pr.py, scripts/create_draft_pr.py, and tests/test_draft_pr.py. Stop after tests and dry-run/duplicate-PR guard verification pass. Do not merge PR #6 or change its draft status.
```
