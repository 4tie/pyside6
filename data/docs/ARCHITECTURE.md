# ARCHITECTURE.md — Current + Target Architecture

## 1) Architecture principle
المعمارية يجب أن تخدم المنتج التالي:

**Run → Read → Analyze → Suggest → Candidate → Re-test → Compare → Accept / Rollback**

ولا يجوز أن تصبح المعمارية مجرد طبقة أوامر CLI داخل UI.

---

## 2) Current real structure in this repo
الريبو الحالي يحتوي بالفعل على الأساس التالي:

### Entry and app state
- `main.py`
- `app/app_state/settings_state.py`

### Core execution and parsing
- `app/core/freqtrade/**`
- `app/core/services/backtest_service.py`
- `app/core/services/download_data_service.py`
- `app/core/services/optimize_service.py`
- `app/core/services/process_service.py`
- `app/core/services/backtest_results_service.py`
- `app/core/services/run_store.py`
- `app/core/services/strategy_config_service.py`
- `app/core/backtests/**`

### UI pages already present
- `app/ui/pages/backtest_page.py`
- `app/ui/pages/download_data_page.py`
- `app/ui/pages/optimize_page.py`
- `app/ui/pages/strategy_config_page.py`
- `app/ui/pages/settings_page.py`

### UI widgets already present
- `app/ui/widgets/terminal_widget.py`
- `app/ui/widgets/backtest_results_widget.py`
- `app/ui/widgets/backtest_summary_widget.py`
- `app/ui/widgets/backtest_stats_widget.py`
- `app/ui/widgets/backtest_trades_widget.py`
- `app/ui/widgets/data_status_widget.py`

### AI placeholders already present
- `app/core/ai/models/`
- `app/core/ai/prompts/`

هذا يعني أن المشروع عنده قاعدة جيدة، لكن الوثائق القديمة ما زالت تصف نسخة أبسط من الواقع الحالي والمنتج المستهدف.

---

## 3) Canonical layers

### Layer A — UI Layer
المسؤوليات:
- tabs
- forms
- buttons
- tables
- widgets
- diff display
- compare display
- explicit user actions

UI يجب أن ينسق ويعرض، لا أن يحتوي business logic ثقيل.

### Layer B — App State Layer
المسؤوليات:
- current settings
- shared state/signals
- active selections
- page coordination

### Layer C — Service Layer
المسؤوليات:
- بناء أوامر التشغيل
- قراءة/كتابة الملفات
- parsing النتائج
- candidate version orchestration
- compare preparation
- history handling

### Layer D — Backtest / Results Domain Layer
المسؤوليات:
- result models
- result parsing
- result indexing
- result storage
- normalized metrics

### Layer E — Freqtrade Integration Layer
المسؤوليات:
- command construction
- strategy/config/runtime resolution
- isolated freqtrade execution contracts

### Layer F — Future AI Layer
المسؤوليات لاحقًا:
- deep analysis
- AI suggestions
- AI code edits
- provider abstraction
- prompt/context building

**لكن هذه الطبقة لا يجب أن تهيمن على التطبيق الآن.**

---

## 4) Required target modules

### Already real / should be extended
- `backtest_service.py`
- `backtest_results_service.py`
- `optimize_service.py`
- `strategy_config_service.py`
- `run_store.py`

### Expected additions later
- candidate version service
- diff service / compare prep service
- history summary service
- logic analysis service
- AI analysis service
- version promotion / rollback service

هذه الإضافات ليست شرطًا أن تُبنى كلها دفعة واحدة، لكنها هي الاتجاه الصحيح للمعمارية.

---

## 5) Core architecture flows

### Backtest flow
UI → backtest service → freqtrade runner → process service → results parser/store → results widgets

### Download flow
UI → download service → freqtrade runner → process service → status refresh

### Strategy config flow
UI → strategy config service → JSON read/write → optional backtest trigger

### Optimization flow (non-AI first)
UI → optimize service / logic service → candidate creation → diff display → apply → backtest → compare

### AI optimization flow (later)
UI / chat placeholder → AI analysis service → candidate creation → diff display → apply → backtest → compare → accept

---

## 6) Versioning rule in architecture
المعمارية يجب أن تفرق بوضوح بين:

### Accepted version
النسخة المعتمدة الحالية التي يعتمد عليها المنتج

### Candidate version
نسخة مرشحة ناتجة عن optimization أو AI change

### Historical versions/runs
كل التاريخ الذي يمكن عرضه أو الرجوع له

أي طبقة تخلط بين accepted وcandidate ستؤدي إلى سلوك خطير وغير واضح.

---

## 7) Chat and AI architecture rule
في المرحلة الحالية:
- يسمح بوجود placeholders
- يسمح بوجود tab/container
- يسمح بوجود provider settings shell
- يسمح بوجود wiring points في المعمارية

لكن لا يجب ربط نجاح المنتج الأساسي بوجود provider حي أو نموذج AI فعلي.

---

## 8) Safety rules
- لا UI imports داخل `app/core/**`
- لا subprocess logic معقد داخل UI
- لا كتابة مباشرة على النسخة المعتمدة من AI flow
- لا command building مكرر بين عدة ملفات
- لا path handling عشوائي أو absolute paths hardcoded
