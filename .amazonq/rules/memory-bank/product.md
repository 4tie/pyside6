# product.md — Project Overview

## Purpose
A PySide6 desktop GUI for running, analyzing, and optimizing Freqtrade trading strategies. The app guides users through a structured workflow: Run → Read → Analyze → Suggest → Candidate → Re-test → Compare → Accept / Rollback.

## Value Proposition
- Faster than CLI for Freqtrade operations
- Clear, organized backtest result visualization
- Safe strategy optimization with versioning and rollback
- AI-assisted analysis (optional, not a hard dependency)

## Key Features
- **Execution**: Run backtests, download data, hyperopt, manage paths/settings
- **Results**: Display profit (after fees), wallet stats, trade breakdown, pair metrics
- **Logic Analysis**: Rule-based diagnosis (stoploss issues, low trade count, config problems)
- **Deep Analysis**: AI-powered analysis of entry/exit weakness, timeframe fit, pair suitability
- **Optimization**: 4 modes — parameter-only, rule-based fixes, numeric search, AI code optimization
- **Versioning**: Track accepted vs. candidate vs. historical versions
- **Comparison & Decision**: Show diffs, compare results, explicit accept/rollback by user

## Target Users
Freqtrade users who want:
- Faster iteration than raw CLI
- Clear result visualization
- Safe strategy modification without breaking the base version
- Traceable history of changes and results

## Core Principles
- User makes final decisions — AI/system suggests, never forces
- No silent auto-promotion of AI changes to accepted version
- Every important step is visible and reversible
- Core app must work without any live AI provider
