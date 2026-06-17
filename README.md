# Agent Looop

Sandbox repository for proving a bounded Hermes GitHub Issues → draft PR loop.

The point of this repository is not to demonstrate broad agent autonomy. It is to provide a safe fixture where Hermes can prove that it can:

1. read GitHub Issues,
2. classify work by risk/type/routing,
3. refuse vague or sensitive work,
4. select only explicitly authorized low-risk work,
5. produce draft PRs with verification evidence,
6. stop before human merge.

## Current pilot

- Control plane: GitHub Issues
- Runner: Hermes
- Worker output: draft PR only
- Human gate: humans review and merge

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Policy](docs/POLICY.md)
- [Runbook](docs/RUNBOOK.md)
- [Report contracts](docs/REPORT-CONTRACTS.md)
- [Getting started](docs/quickstart.md)

> Intentional fixture note: the getting-started link above is currently wrong. The smoke-test issue "Fix broken README link" should correct it to `docs/getting-started.md`.

## Smoke fixture code

This repo includes a tiny parser module so the `type:test` smoke issue has something real to verify.

```bash
python -m pytest
```
