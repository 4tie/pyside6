# Architecture Selection: freqtrade-gui-architecture

## Recommended Architecture: Domain-Oriented (Bounded Contexts)

### Rationale
The current layered architecture has 75% cross-cutting requirements, 3 synchronous dependency cycles, and two overlapping versioning services — all symptoms of a service layer that grew organically without explicit ownership boundaries. The Domain-Oriented architecture reduces cross-cutting requirements to ~25% by grouping the tightly-coupled loop/diagnosis/scoring/versioning/rollback variables into a single OptimizationDomain, and eliminates the LoopService↔ImproveService↔BacktestService cycle by making BacktestDomain a clean dependency of OptimizationDomain rather than a peer. The main trade-off is that OptimizationDomain is a larger component than any single current service, but this is justified because all variables it owns are constrained by the same loop invariants and must change together.

---

### Components

| Component | Owned State | Responsibility |
|-----------|-------------|----------------|
| **BacktestDomain** | `BacktestResults`, `index.json`, `meta.json`, `results.json`, `trades.json`, `params.json`, `PairAnalysis`, `RunComparison` | Execute freqtrade backtests via subprocess; parse, store, and retrieve all run artifacts; compare runs; rebuild indexes |
| **OptimizationDomain** | `LoopConfig`, `LoopIteration`, `LoopResult`, `RobustScore`, `SuggestionRotator`, `LoopState4L`, `GateResult`, `HardFilterFailure`, `StrategyVersion`, `VersionLineage`, `sandbox_dir`, `strategy.json` (write) | Full optimization loop lifecycle: diagnose → suggest → apply → backtest → score → version → rollback; owns all loop invariants |
| **ProcessDomain** | `ProcessRun` registry, subprocess handles, `ProcessOutputBus` | Subprocess lifecycle management (start, stop, stream stdout/stderr); SSE bridge for web layer |
| **AIDomain** | `EventJournal`, `ToolRegistry`, `AsyncConversationRuntime`, conversation history | AI conversation, context assembly, tool execution, provider routing |
| **SettingsDomain** | `AppSettings`, `settings.json`, `favorites.json`, `backtest_config.json` | Configuration persistence, validation, and migration |
| **PresentationLayer** | Widget state (PySide6), static HTML/JS/CSS | Desktop UI (PySide6 pages) and web UI (static pages); renders data, captures user input; no business logic |
| **APIGateway** | FastAPI request/response models | HTTP routing and validation; thin adapter that delegates to domain APIs; dependency injection via FastAPI `Depends()` |

---

### Information Flow

| From \ To | BacktestDomain | OptimizationDomain | ProcessDomain | AIDomain | SettingsDomain | PresentationLayer | APIGateway |
|-----------|---------------|-------------------|---------------|----------|----------------|-------------------|------------|
| **BacktestDomain** | — | → results | → execute cmd | → journal | R config | → display | → response |
| **OptimizationDomain** | → run candidate | — | → execute cmd | → journal | R config | → display | → response |
| **ProcessDomain** | — | — | — | — | — | → stream output | → SSE |
| **AIDomain** | R results | R loop state | — | — | R config | → chat response | → response |
| **SettingsDomain** | — | — | — | — | — | → display | → response |
| **PresentationLayer** | → run/retrieve | → start/stop loop | — | → chat | → read/write | — | — |
| **APIGateway** | → run/retrieve | → start/stop loop | → stream | → chat | → read/write | — | — |

Legend: `→` = calls/writes, `R` = reads only

---

### Requirement Allocation

| Requirement | Component(s) |
|-------------|--------------|
| Run a backtest | APIGateway → BacktestDomain + ProcessDomain |
| View/list backtest results | APIGateway → BacktestDomain |
| Compare two runs | APIGateway → BacktestDomain |
| Diagnose a run | APIGateway → OptimizationDomain (diagnosis is an optimization concern) |
| Start auto-optimization loop | APIGateway → OptimizationDomain |
| Stop loop / get loop status | APIGateway → OptimizationDomain |
| Apply parameter suggestion | OptimizationDomain (internal) |
| Score an iteration | OptimizationDomain (internal) |
| Version a strategy | OptimizationDomain (internal) |
| Rollback to a previous run | APIGateway → OptimizationDomain |
| AI conversation | APIGateway → AIDomain |
| AI tool: run backtest | AIDomain → BacktestDomain |
| AI tool: read strategy | AIDomain → BacktestDomain |
| Download market data | APIGateway → BacktestDomain + ProcessDomain |
| Run hyperopt | APIGateway → OptimizationDomain + ProcessDomain |
| Stream process output (SSE) | APIGateway → ProcessDomain |
| Read/write settings | APIGateway → SettingsDomain |
| Save/load backtest config | APIGateway → SettingsDomain |
| Save/load favorite pairs | APIGateway → SettingsDomain |
| Desktop UI navigation | PresentationLayer (internal) |
| Desktop backtest page | PresentationLayer → BacktestDomain + ProcessDomain |
| Desktop results page | PresentationLayer → BacktestDomain |
| Desktop strategy lab page | PresentationLayer → OptimizationDomain |
| Desktop settings page | PresentationLayer → SettingsDomain |

---

### Key Design-Induced Invariants

These invariants arise from the domain partitioning decisions, not directly from requirements:

1. **OptimizationDomain is the sole writer of `strategy.json`** — BacktestDomain and AIDomain may read strategy files but never write them. This prevents concurrent parameter mutations.

2. **BacktestDomain is the sole writer of `index.json` and run artifacts** — OptimizationDomain triggers backtests through BacktestDomain rather than writing results directly. This keeps the index consistent.

3. **ProcessDomain owns all subprocess handles** — No domain spawns subprocesses directly; all subprocess execution is delegated to ProcessDomain. This prevents orphaned processes.

4. **SettingsDomain is read-only from all other domains** — Domains read configuration at call time; they do not cache AppSettings internally. This ensures settings changes take effect immediately.

5. **AIDomain has no write access to any persistence layer** — AI tools that modify strategy parameters must do so by calling OptimizationDomain APIs, not by writing files directly. This keeps all parameter mutations auditable.

---

### Alternatives Considered

| Candidate | Strength | Weakness | Why Not Selected |
|-----------|----------|----------|-----------------|
| **A: Current Layered (30+ services)** | Familiar Python pattern; easy to add new services; FastAPI DI works well | 75% cross-cutting reqs; 3 sync cycles; two overlapping versioning services; LoopService is 2400+ lines | Too many cross-cutting concerns; cycles indicate wrong abstraction boundaries |
| **C: Event-Driven Pipeline** | Zero sync cycles; AI agent decoupled from loop; trivially testable DiagnosticPipeline | Debugging causality is hard; event ordering bugs in loop (N+1 before N); overkill for local desktop app | Complexity cost exceeds benefit for a single-user local application |

---

### Metrics Summary

| Metric | Selected (B: Domain) | Alt A: Layered | Alt C: Event-Driven |
|--------|---------------------|----------------|---------------------|
| Cross-cutting reqs % | **25%** | 75% | 40% |
| Cross-cutting invariants % | **20%** | 60% | 30% |
| Flow density (edges/N×(N-1)) | **0.18** | 0.45 | 0.22 |
| God object score | 28% | 35% | 15% |
| Sync cycles | **1** (internal to OptimizationDomain) | 3 | 0 |
| Max fan-in | 4 (SettingsDomain) | 8 (AppSettings) | 5 (EventBus) |
| Max fan-out | 4 (OptimizationDomain) | 7 (LoopService) | 6 (EventBus) |
| Evolvability cost (avg components/REQ) | **1.8** | 4.2 | 2.1 |

---

### Migration Path from Current Architecture

The current codebase maps to the recommended architecture as follows:

**BacktestDomain** ← `BacktestService`, `BacktestResultsService`, `ComparisonService`, `PairAnalysisService`, `ExitReasonAnalysisService`, `ResultsParser`, `RunStore`, `IndexStore`, `StrategyIndexStore`, `BacktestParser`

**OptimizationDomain** ← `LoopService`, `ImproveService`, `DiagnosisService`, `ResultsDiagnosisService`, `HardFilterService`, `RuleSuggestionService`, `PatternDatabase`, `PatternEngine`, `DecisionEngine`, `ExecutionEngine`, `EvaluationEngine`, `VersioningService`, `VersionManagerService` (merge these two), `RollbackService`, `HyperoptAdvisor`, `AIAdvisorService`, `RLAdvisorService`, `DDService`

**ProcessDomain** ← `ProcessRunManager`, `ProcessService`, `ProcessOutputBus`

**AIDomain** ← `AIService`, `AsyncConversationRuntime`, `EventJournal`, `ToolRegistry`, all providers, all tools, all context providers

**SettingsDomain** ← `SettingsService`, `SettingsState`, `StrategyConfigService`, `DataStatusService`, `DownloadDataService` (config aspects)

**PresentationLayer** ← All `app/ui/` pages, widgets, dialogs, shell; all `app/web/static/` HTML/JS/CSS

**APIGateway** ← All `app/web/api/routes/` routers, `app/web/main.py`, `app/web/dependencies.py`, `app/web/models.py`
