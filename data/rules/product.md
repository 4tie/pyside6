# Product Rules

## Core definition
This app is a Freqtrade strategy workstation, not an AI-first chat app.

## Core user journey
Run backtest → read results → analyze → create candidate change → re-test → compare → accept / rollback.

## Priority
Core product behavior comes before AI integration.

## AI rule
AI optimization never edits the accepted version directly.
It must create a candidate version first.

## Metrics rule
Profit must be treated as after-fee profit.
Stability across more than one period matters.
