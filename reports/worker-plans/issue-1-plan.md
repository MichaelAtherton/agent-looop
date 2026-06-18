# Worker Plan — issue-1

Objective:
Fix broken README link

Scope:
Edit documentation files only

Out of scope:
- No code changes
- No unrelated cleanup
- No merge/deploy/publish/repo settings/secrets/permissions changes

Files expected to touch:
- README.md

Steps:
1. Re-read task packet and stop conditions.
2. Make the smallest complete change.
3. Run the stated verification.
4. Write a worker run report.
5. Stop before reviewer/PR/merge.

Verification command:
Inspect README diff and confirm docs/getting-started.md exists

Stop conditions:
- Stop if docs/getting-started.md does not exist
- Stop if requested change requires code edits
