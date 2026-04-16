# AGENTS.md — Project Rules for AI Coders

## Primary Product Rule
This application is a **Freqtrade strategy workstation**.
Its core job is to let the user:
- run backtests,
- inspect results,
- understand weaknesses,
- create candidate changes,
- compare versions,
- accept or roll back safely.

**Do not treat AI as the main product yet.**
AI is a later layer.
For now, build and stabilize the product so it works **without requiring an AI provider**.

---

## Current Priority Order
Build in this order unless the user explicitly changes it:

1. Settings, paths, validation, execution reliability
2. Download data flow
3. Backtest flow
4. Results parsing and display
5. Logic-based analysis and suggestions
6. Strategy/config editing and diff display
7. Candidate version flow
8. Compare / accept / rollback / history
9. Chat panel placeholder and AI placeholders
10. AI provider integration and deep AI assistance

---

## Non-Negotiable Product Rules

### Rule 1 — AI optimization never edits the accepted strategy directly
Any AI-generated change must:
1. create a **candidate version**,
2. show a **diff** before apply,
3. show the diff **before** the next backtest,
4. run backtest on the candidate only,
5. require explicit **user accept** before promotion.

### Rule 2 — Candidate first, accept later
- `Apply` means: apply to the candidate version only.
- `Accept` means: promote the candidate to the accepted version.
- `Rollback` means: restore the previously accepted strategy code + matching parameter JSON.

### Rule 3 — Profit is always after fees
Do not present profit as if fees do not exist.
All product wording and metrics must assume **after-fee profitability**.

### Rule 4 — Results are not only profit
Good results are judged by a combination of:
- after-fee profitability,
- stability across more than one period,
- drawdown/risk,
- number of trades when relevant,
- fit with the strategy style.

### Rule 5 — Logic analysis comes before AI analysis
When possible, first provide:
- rule-based issues,
- obvious known fixes,
- deterministic suggestions.

Deep AI analysis is an additional layer, not a replacement.

### Rule 6 — Core product before AI provider work
You may add:
- AI placeholders,
- chat panel shell,
- provider settings placeholders,
- disabled buttons / empty states.

Do **not** make provider integrations the center of the implementation unless the user explicitly asks.

---

## Required Reading Before Major Changes
Read these files before changing architecture or workflow behavior:

1. `data/docs/PRODUCT.md`
2. `data/docs/PRODUCT_FLOW.md`
3. `data/docs/ARCHITECTURE.md`
4. `data/docs/WORKFLOW.md`
5. `data/docs/STRUCTURE.md`
6. `data/rules/guidelines.md`
7. `data/rules/product.md`
8. `data/rules/structure.md`
9. `data/rules/tech.md`

---

## Mandatory Change Workflow
Follow this order for any meaningful code change:

1. **Analyze** the request and current code
2. **Identify** the smallest set of files to change
3. **Apply** the smallest correct patch
4. **Validate** behavior and structure
5. **Summarize** what changed
6. **Wait** for user confirmation if the change is substantial
7. **Commit** only after approval

---

## Scope Control Rules

### Do
- Extend the existing flow.
- Reuse existing services and widgets.
- Keep execution logic in `app/core/**`.
- Keep UI orchestration in `app/ui/**`.
- Preserve current working features.
- Prefer safe incremental steps.

### Do Not
- Turn the app into an AI-first chatbot.
- Skip versioning for AI optimization.
- Write directly over accepted strategies from AI flows.
- Mix unrelated refactors into feature work.
- Add a provider dependency just because a placeholder exists.
- Hide important user decisions behind automation.

---

## UI Behavior Rules
- The user must be able to understand what happened.
- Important actions should expose state clearly:
  - current strategy,
  - current accepted version,
  - candidate version,
  - changed files,
  - diff,
  - result comparison.
- `Accept`, `Rollback`, and `Continue Optimization` must remain explicit.

---

## Backtest and Optimization Rules
- Backtests must be runnable without AI.
- Optimize tab must support non-AI optimization modes first.
- Strategy/config editing must work without AI.
- Suggestions generated from logic should be actionable from the UI.
- If data is missing, the product may guide the user to download data first.

---

## Chat Panel Rule
The chat panel is a future control layer over the product.
For now it may exist as:
- layout placeholder,
- disabled shell,
- command routing stub,
- provider configuration placeholder.

It should not block building the main product.
