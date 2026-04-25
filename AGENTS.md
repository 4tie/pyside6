# AGENTS.md Contract

This file defines the agent contract and serves as the index to project guidance. It applies repo-wide unless overridden by a nested AGENTS.md.

## Steering Documents

- Treat Steering as the first-party source for product, technical, and structural guidance.
- Use `.codex/steering/product.md`, `.codex/steering/tech.md`, and `.codex/steering/structure.md`.
- Resolve paths through repository-provided helpers; avoid hardcoded absolutes.
- Treat Steering as read-only; follow the established change-management flow instead of ad-hoc edits.
- Summarize applicable Steering points in outputs; cite the specific file/section without restating details.

## Decision Precedence

1) Steering documents under ".codex/steering/*.md"
2) This AGENTS.md contract (general repository conventions)
3) Generic assumptions (avoid unless explicitly allowed)

## Agent Behavior Contract

- Prefer project-provided abstractions for CLI operations; avoid ad-hoc process spawning when wrappers exist.
- Respect feature flags and configuration gating documented in Steering or related code references.
- Use shared logging utilities; record key lifecycle and error paths without excess noise.
- Route failures through centralized services/utilities rather than ad-hoc try/catch loops.
- Honor project guidelines for long-running work so the host environment remains responsive.
- Reference Steering for specifics such as naming, boundaries, and directory layout rather than restating them here.

## Paths & I/O

- Prefer project-sanctioned file system helpers for workspace read/write/create operations.
- Use repository-approved path utilities for `.codex/steering` and related directories; avoid absolute paths.
- Only modify files within approved workspace areas defined by project rules.
- Do not overwrite files under `.codex/steering` directly; rely on the sanctioned update flow.

## CLI Integration

- Build CLI commands through officially supported builders/wrappers before execution.
- Reference approval-mode and model-flag definition sites/tests without duplicating values.
- Verify required tooling availability before invocation; surface setup guidance if unavailable.

## Submission Checklist (For Agents)

- Verify decisions against `.codex/steering/*.md`; cite files/sections without duplication.
- Resolve steering paths via approved utilities; avoid absolute paths.
- Respect feature flags and constraints documented by the project.
- Use project-sanctioned wrappers for CLI interactions.
- Avoid restating Steering or code constants; keep AGENTS.md concise and index-like.

## Non-Goals / Anti-Patterns

- Do not bypass official wrappers/utilities for CLI calls when they exist.
- Do not store state in globals beyond established singletons.
- Do not write outside approved directories or overwrite Steering directly.
- Do not re-enable disabled features unless explicitly requested.
