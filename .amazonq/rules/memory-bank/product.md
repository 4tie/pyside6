# product.md — Project Overview

## What This Product Is
A PySide6 desktop GUI for running, analyzing, and optimizing Freqtrade trading strategies. It wraps Freqtrade's CLI into a structured workflow with AI assistance capabilities.

## Core Value Proposition
Moves the user from raw strategy files to an organized loop:
**Strategy → Backtest → Results → Analysis → Candidate Change → Re-test → Compare → Accept / Rollback**

## Key Features
- **Execution**: Run backtests, download market data, hyperopt/optimization via GUI
- **Results Display**: Profit after fees, trade stats, pair breakdown, trade details, metrics
- **Logic Analysis**: Rule-based diagnosis (bad stoploss, low trade count, weak strategy behavior)
- **AI Assistant**: Chat panel with tool-calling AI for deep analysis and strategy suggestions
- **Versioning**: Candidate versions, diff display, accept/rollback, history tracking
- **Strategy Lab**: Iterative improvement loop with scoring and state machine
- **Settings Management**: Paths, venv, freqtrade executable, exchange config

## Target Users
Freqtrade users who want:
- Faster workflow than raw CLI
- Clear results visualization
- Understand why a strategy is underperforming
- Safe strategy modification without breaking the accepted version
- Iterative improvement with full history

## Product Philosophy
- User makes final decisions — AI/system suggests, never forces
- Explicit buttons over hidden behavior
- Every important step is reversible
- AI is optional — core app works without a live AI provider
- Accepted version is never touched directly by AI optimization

## Current Scope
Active: settings, backtest, results, logic analysis, strategy editing, versioning, AI chat panel, optimization loop
Placeholders only: deep AI provider integration as hard dependency
