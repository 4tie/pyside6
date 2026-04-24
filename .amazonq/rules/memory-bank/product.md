# Product Overview

## Purpose
A PySide6 desktop GUI platform for running, analyzing, and optimizing Freqtrade trading strategies. Not a CLI wrapper or AI chat — the core value is a structured workflow from execution to decision.

## Core Workflow
**Strategy + Parameters + Runtime Settings → Backtest → Results → Analysis → Candidate Change → Re-test → Comparison → Accept / Rollback**

## Key Features
- **Execution**: Run backtests, download market data, hyperopt optimization, manage paths/settings
- **Results Display**: Profit after fees, wallet stats, trade counts, pair breakdown, trade details
- **Logic Analysis**: Rule-based diagnosis (bad stoploss, low trade count, weak strategy behavior) — no AI required
- **Deep Analysis**: AI-assisted analysis of entry/exit weakness, timeframe fit, pair suitability
- **Optimization**: 4 modes — parameter-only, rule-based fixes, numeric search, AI code optimization
- **Versioning**: Track accepted vs candidate vs historical versions with full traceability
- **Comparison & Decision**: Show diffs, compare results, explicit accept/rollback — user always decides
- **AI Chat Panel**: Integrated AI assistant (OpenRouter/Ollama) for strategy guidance and code suggestions
- **Web Layer**: FastAPI/uvicorn web interface alongside the desktop GUI

## Target Users
Freqtrade users who want:
- Faster workflow than raw CLI
- Clearer results visualization
- Understanding of why a strategy underperforms
- Safe strategy modification without breaking the accepted version

## Core Rules
- Profit always calculated **after fees**
- AI optimization never overwrites accepted strategy directly — always creates a candidate first
- User decision is final — system suggests, never forces
- Core product (backtest/results/versioning) takes priority over AI complexity
