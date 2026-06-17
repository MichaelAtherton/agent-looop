# Policy — Labels as Permissions

## Core rule

`agent:ready` is a permission grant, not casual metadata.

A worker may select an issue only if it has both labels:

```text
risk:low
agent:ready
```

A worker must skip any issue with any of these labels:

```text
needs:human
agent:blocked
risk:medium
risk:high
```

## Managed labels

### Risk

- `risk:low`
- `risk:medium`
- `risk:high`

### Type

- `type:bug`
- `type:feature`
- `type:docs`
- `type:test`
- `type:refactor`
- `type:chore`

### Agent routing

- `agent:ready`
- `agent:blocked`
- `agent:complete`

### Human routing

- `needs:human`

### Later hardening

- `agent:in-progress`

## Blocked scopes by default

The v1 worker must not handle issues touching:

- auth
- billing
- permissions
- security policy
- data migrations
- production deployment
- broad architecture changes
- AI Navigator AIR scoring
- AIR assessment behavior
- AIR coaching behavior
- AIR privacy controls
- employer visibility
- role-data surfaces

## Stop conditions

Stop and ask for human input if:

- acceptance criteria are missing,
- the requested behavior is vague,
- the issue touches blocked scopes,
- verification cannot be identified,
- implementation would require unrelated file changes,
- repo state is dirty or stale.
