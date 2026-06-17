# Report Contracts

## Manager dry-run report

```markdown
# Manager Dry-Run Report

## Summary
- Repo:
- Run time:
- Issues inspected:
- Recommended agent-ready count:
- Recommended needs-human count:
- False-ready risks:

## Issue classifications
| Issue | Recommended risk | Recommended type | Agent-ready? | Confidence | Reason | Human question | Apply-mode labels |
|---|---|---|---|---:|---|---|---|

## Missing labels
- ...

## Apply-mode actions proposed
- ...

## Blockers / human questions
- ...

## Self-critique
- Where this classification may be wrong:
- What needs Michael/Calvin review:
```

## Agent Assessment comment

```markdown
## Agent Assessment

Risk:
Type:
Agent-ready:
Confidence:

Reason:

Required verification:

Allowed worker action:

Forbidden:

Human question, if blocked:
```

## Worker draft PR body

```markdown
## Summary

## Source issue
Refs #[issue]

## Task packet
- Goal:
- Scope:
- Out of scope:
- Allowed actions:
- Forbidden actions:

## Plan

## Acceptance criteria
- [ ] ...

## Verification
Commands run:
- `...` — pass/fail

## Reviewer result
- Critical issues:
- Warnings:
- Suggestions:
- Recommendation:

## Known limitations / follow-ups

## Human gate
This PR is draft-only. Human review/merge required.
```
