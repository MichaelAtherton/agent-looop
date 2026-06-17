# Architecture — GitHub Issues to Draft PR Loop

## Purpose

This repository is the sandbox control plane for a bounded loop-engineering pilot. GitHub Issues hold work items and permissions. Hermes acts as manager and, later, worker. Humans retain merge authority.

## V1 flow

```text
GitHub Issues
  → manager dry-run/apply triage
  → risk/type/routing labels + Agent Assessment
  → safe queue: risk:low + agent:ready
  → worker selects one eligible issue
  → branch/worktree
  → implementation
  → verification
  → separate reviewer pass
  → draft PR
  → human merge gate
  → run report / learning
```

## Components

| Component | Responsibility | Mutation allowed in first milestone? |
|---|---|---:|
| Manager dry-run | Read issues, classify, propose actions, produce report | No |
| Manager apply | Create labels, apply labels, post/update Agent Assessment comments after approval | Yes, issue metadata/comments only |
| Eligibility engine | Deterministically select only `risk:low` + `agent:ready` issues | No code mutation |
| Worker | Implement one bounded task in an isolated branch/worktree | Yes, only after Gates A/B |
| Reviewer | Separate checker pass before draft PR | No direct merge authority |
| Human gate | Review/merge/deploy decisions | Yes, human only |

## Promotion gates

1. Dry-run must classify smoke issues correctly before apply mode.
2. Apply mode must mirror approved dry-run actions.
3. Worker must only select `risk:low` + `agent:ready` issues.
4. Draft PRs require real verification and separate reviewer output.

## Non-goals

- Auto-merge
- Production deployment
- Parallel worker runs
- High-risk work
- Auth, billing, permissions, security, migrations, broad architecture changes
