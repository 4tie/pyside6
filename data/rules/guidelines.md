# Development Guidelines

## General
- Prefer small, safe, incremental changes.
- Do not mix large refactors with product behavior changes.
- Reuse existing services and pages before adding new parallel systems.

## Product-first guideline
If the choice is between:
- building core backtest/results/versioning behavior, or
- building AI/provider complexity,
choose the core product behavior first.

## Safety
- Never let AI optimization overwrite the accepted strategy directly.
- Show diffs before candidate application and before re-test.
- Keep user decisions explicit.
