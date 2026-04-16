# WORKFLOW.md — Build and Change Workflow

## 1) Product-first workflow
أي عمل على هذا المشروع يجب أن يمر بهذا السؤال أولًا:

**هل هذا يخدم المنتج الأساسي الآن، أم أنه يقدم طبقة AI قبل أوانها؟**

إذا كان العمل يخص:
- execution stability
- results clarity
- logic analysis
- candidate versions
- compare / accept / rollback

فهو داخل الأولوية.

إذا كان العمل يخص:
- provider complexity
- agent orchestration complexity
- deep AI integration مبكرًا

فهو مؤجل إلا إذا طلبه المستخدم صراحة.

---

## 2) Mandatory change sequence

1. Analyze request and current code
2. Identify the smallest correct file set
3. Patch incrementally
4. Validate
5. Summarize
6. Wait for approval if the change is substantial
7. Commit only after approval

---

## 3) Implementation order for this product

### Phase 1 — Core execution
- settings
- path validation
- freqtrade execution readiness
- download data
- run backtest

### Phase 2 — Core reading
- parse results
- display results cleanly
- expose pair/trade details
- normalize important metrics

### Phase 3 — Core diagnosis
- rule-based analysis
- deterministic suggestions
- actionable UI buttons

### Phase 4 — Controlled modification
- strategy/config editing
- diff presentation
- candidate version creation
- candidate re-test flow

### Phase 5 — Controlled decision
- compare current vs candidate
- accept
- rollback
- history view

### Phase 6 — AI shell only
- chat panel placeholder
- provider settings placeholder
- AI integration entry points

### Phase 7 — Full AI later
- deep analysis
- AI recommendation engine
- AI code changes
- natural-language control

---

## 4) Rule for AI-related tasks
إذا كان المطلوب متعلقًا بالـ AI، اتبع هذه القاعدة:

### Allowed now
- create placeholders
- create settings shell
- create architecture hooks
- define interfaces/contracts
- define disabled UI sections

### Not default priority now
- shipping provider integration as core work
- making backtest/results depend on AI
- designing the whole app around the chat panel

---

## 5) Rule for optimization work
أي optimization meaningful يجب أن يمر بهذا المسار:

1. understand current result
2. create suggestion/fix
3. create candidate version
4. show diff
5. let user apply candidate
6. run backtest on candidate
7. compare
8. accept / reject / rollback / continue

---

## 6) Rule for direct edits
### User direct edits
يمكن دعمها مباشرة في editor، لكن يجب أن تكون واضحة ومفهومة.

### AI edits
لا تُطبَّق مباشرة على accepted version.
دائمًا candidate first.

---

## 7) Definition of done for a feature
الميزة تعتبر مكتملة فقط إذا:
- تعمل داخل المسار الحقيقي للمنتج
- لا تكسر flows الحالية
- واجهتها واضحة للمستخدم
- لا تعتمد على AI بلا ضرورة
- لها place واضح في accepted/candidate/history logic إذا كانت تمس الاستراتيجية
