# Manager Dry-Run Report

## Summary
- Repo: `MichaelAtherton/agent-looop`
- Run time: 2026-06-17T21:40:52.236137+00:00
- Issues inspected: 5
- Recommended agent-ready count: 2
- Recommended needs-human count: 3
- False-ready risks: none detected
- Mutation status: No GitHub mutations were performed. This report is read-only.

## Issue classifications
| Issue | Current labels | Recommended risk | Recommended type | Agent-ready? | Confidence | Reason | Human question | Apply-mode labels |
|---|---|---|---|---|---:|---|---|---|
| #1 Fix broken README link | none | risk:low | type:docs | yes | 0.95 | Documentation-only work with clear scope and acceptance criteria. | — | risk:low, type:docs, agent:ready |
| #2 Redesign our auth architecture to be more scalable | none | risk:high | type:feature | no | 0.98 | Authentication architecture is a blocked v1 scope and the requested change requires human technical/product judgment. | What specific auth behavior, constraint, or failure mode should be addressed first? | risk:high, type:feature, needs:human, agent:blocked |
| #3 Update payment permission logic | none | risk:high | type:feature | no | 0.98 | Payment/billing/permission logic is a blocked v1 scope and may affect security-sensitive behavior. | What exact payment permission behavior should change, and what tests define correctness? | risk:high, type:feature, needs:human, agent:blocked |
| #4 Add missing test for parser error on empty input | none | risk:low | type:test | yes | 0.94 | Test-only task with explicit expected behavior and verification command. | — | risk:low, type:test, agent:ready |
| #5 Improve onboarding | none | risk:medium | type:feature | no | 0.88 | The onboarding request is too broad; it does not identify a specific document, behavior, or acceptance criteria. | What specific onboarding behavior or document should be changed? | risk:medium, type:feature, needs:human, agent:blocked |

## Missing labels
- none

## Unexpected managed-prefix labels
- none

## Apply-mode actions proposed
- Issue #1: apply labels `risk:low, type:docs, agent:ready` and post/update an Agent Assessment comment.
- Issue #2: apply labels `risk:high, type:feature, needs:human, agent:blocked` and post/update an Agent Assessment comment.
- Issue #3: apply labels `risk:high, type:feature, needs:human, agent:blocked` and post/update an Agent Assessment comment.
- Issue #4: apply labels `risk:low, type:test, agent:ready` and post/update an Agent Assessment comment.
- Issue #5: apply labels `risk:medium, type:feature, needs:human, agent:blocked` and post/update an Agent Assessment comment.

## Proposed Agent Assessment comments
### Issue #1 — Fix broken README link

```markdown
## Agent Assessment

Risk: low
Type: docs
Agent-ready: yes
Confidence: 0.95

Reason:
Documentation-only work with clear scope and acceptance criteria.

Required verification:
Inspect documentation diff and confirm referenced file/link target exists.

Allowed worker action:
- Documentation-only edit within the issue scope.

Forbidden:
- No merge, deploy, publish, repo settings, permissions, secrets, or unrelated cleanup.
- No work outside the issue and Agent Assessment scope.
```

### Issue #2 — Redesign our auth architecture to be more scalable

```markdown
## Agent Assessment

Risk: high
Type: feature
Agent-ready: no
Confidence: 0.98

Reason:
Authentication architecture is a blocked v1 scope and the requested change requires human technical/product judgment.

Required verification:
Human-defined architecture decision and verification plan required before any agent work.

Allowed worker action:
- None. Worker must not select this issue until human input resolves the blocker.

Forbidden:
- No merge, deploy, publish, repo settings, permissions, secrets, or unrelated cleanup.
- No work outside the issue and Agent Assessment scope.

Human question:
What specific auth behavior, constraint, or failure mode should be addressed first?
```

### Issue #3 — Update payment permission logic

```markdown
## Agent Assessment

Risk: high
Type: feature
Agent-ready: no
Confidence: 0.98

Reason:
Payment/billing/permission logic is a blocked v1 scope and may affect security-sensitive behavior.

Required verification:
Human-defined payment/permissions test plan required before any agent work.

Allowed worker action:
- None. Worker must not select this issue until human input resolves the blocker.

Forbidden:
- No merge, deploy, publish, repo settings, permissions, secrets, or unrelated cleanup.
- No work outside the issue and Agent Assessment scope.

Human question:
What exact payment permission behavior should change, and what tests define correctness?
```

### Issue #4 — Add missing test for parser error on empty input

```markdown
## Agent Assessment

Risk: low
Type: test
Agent-ready: yes
Confidence: 0.94

Reason:
Test-only task with explicit expected behavior and verification command.

Required verification:
Run `python -m pytest` and record pass/fail output.

Allowed worker action:
- Test-only edit within the issue scope; production behavior changes only if required to satisfy documented behavior.

Forbidden:
- No merge, deploy, publish, repo settings, permissions, secrets, or unrelated cleanup.
- No work outside the issue and Agent Assessment scope.
```

### Issue #5 — Improve onboarding

```markdown
## Agent Assessment

Risk: medium
Type: feature
Agent-ready: no
Confidence: 0.88

Reason:
The onboarding request is too broad; it does not identify a specific document, behavior, or acceptance criteria.

Required verification:
Human must define the target artifact and expected outcome.

Allowed worker action:
- None. Worker must not select this issue until human input resolves the blocker.

Forbidden:
- No merge, deploy, publish, repo settings, permissions, secrets, or unrelated cleanup.
- No work outside the issue and Agent Assessment scope.

Human question:
What specific onboarding behavior or document should be changed?
```

## Blockers / human questions
- #2: What specific auth behavior, constraint, or failure mode should be addressed first?
- #3: What exact payment permission behavior should change, and what tests define correctness?
- #5: What specific onboarding behavior or document should be changed?

## Self-critique
- This dry-run uses deterministic v1 policy heuristics rather than a general engineering judgment model.
- It is intentionally conservative: unclear or non-docs/test work is blocked until a human narrows scope.
- Michael/Calvin should verify that the two recommended `agent:ready` issues are truly safe before apply mode.
- Auth, payment, permissions, security, migration, deployment, broad architecture, and AI Navigator product-critical surfaces remain blocked even if future issues include more detail.
