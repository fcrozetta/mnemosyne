# Claim 0056: .ai Excludes User-Local Agent State

## Statement

The `.ai` directory stores public project memory only. User-local agent state
and workstation-specific metadata do not belong under `.ai`.

## Rules

- `.ai` may store claims, public-safe agent directives, and repo-local project
  metadata.
- `.ai` must not store references whose meaning depends on a specific user
  environment or workstation.
- Repository memory should stay portable across machines and users.

## Acceptance Checks

- `.ai` contains no user-local agent-state files.
- `.ai` contains no workstation-specific references.
- AGENTS.md states that `.ai` is public project memory only.
