# Runbook — Manager and Worker Loop

## Phase 0 — Fixture setup

Create managed labels and smoke-test issues. Do not apply triage labels to smoke issues during fixture setup; the manager dry-run should classify them.

## Phase 1 — Manager dry-run

Goal: inspect GitHub Issues and produce a non-mutating report.

Run:

```bash
python scripts/manager_dry_run.py \
  --repo MichaelAtherton/agent-looop \
  --output reports/manager-dry-run-$(date -u +%Y-%m-%d).md
```

This command reads GitHub issues/labels via `gh`, writes a local Markdown report, and performs no GitHub mutations.

Dry-run report must include:

- repo and run time,
- issues inspected,
- missing labels,
- issue classifications,
- recommended agent-ready count,
- recommended needs-human count,
- exact apply-mode actions proposed,
- specific human questions for blocked issues,
- self-critique.

Hard fail if:

- auth/billing/security/vague architecture work is recommended as `agent:ready`,
- missing acceptance criteria are invented by the agent,
- `needs:human` has no specific question.

## Phase 2 — Manager apply mode

Only after dry-run approval, apply labels and Agent Assessment comments exactly as proposed.

Run:

```bash
python scripts/manager_apply.py \
  --repo MichaelAtherton/agent-looop \
  --output reports/manager-apply-$(date -u +%Y-%m-%d).md
```

This command mutates GitHub issue metadata/comments only. It does not write code, create branches, open PRs, close issues, merge, deploy, or change repo settings/secrets.

Allowed actions:

- create missing managed labels,
- apply risk/type/routing labels,
- post/update Agent Assessment comments.

Forbidden actions:

- code edits,
- branch creation,
- PR creation,
- issue closure,
- auto-merge,
- deployment.

## Phase 3 — Worker prototype

Run only after manager apply mode is approved.

```bash
python scripts/worker_prototype.py \
  --repo MichaelAtherton/agent-looop \
  --repo-root .
```

This creates a local branch/worktree, writes a plan before editing, implements one deterministic docs/test smoke task, runs verification, writes a worker report, and stops before reviewer/PR/merge.

Select exactly one oldest eligible issue with:

```text
risk:low
agent:ready
```

Worker steps:

1. Confirm issue labels and latest issue state.
2. Create task packet.
3. Create branch/worktree.
4. Write implementation plan before editing.
5. Make the smallest complete change.
6. Run relevant verification.
7. Run separate reviewer pass.
8. Fix valid in-scope reviewer findings once.
9. Open draft PR.
10. Comment run report on issue.
11. Stop.

## Verification commands

Baseline fixture check:

```bash
python -m pytest
```

## Human gate

Humans review and merge. Hermes never merges.
