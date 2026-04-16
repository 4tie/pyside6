# PRODUCT_FLOW.md — Official Product Flow

## Flow 0 — Open App
1. المستخدم يفتح التطبيق.
2. التطبيق يحمّل settings الحالية.
3. التطبيق يتحقق من المسارات الأساسية:
   - Python executable
   - Freqtrade executable / module mode
   - `user_data`
   - `config.json`
4. إذا وجدت مشكلة:
   - تظهر بوضوح في الواجهة
   - مع اقتراحات إصلاح
   - بدون منع كامل لباقي الواجهة إن أمكن

---

## Flow 1 — Settings and Environment Readiness
1. المستخدم يدخل تبويب Settings.
2. يحدد أو يراجع المسارات.
3. التطبيق يتحقق من readiness.
4. المستخدم يستطيع تجربة أوامر check الأساسية.
5. إذا كانت البيئة جاهزة، ينتقل إلى download/backtest.

---

## Flow 2 — Download Data
1. المستخدم يفتح تبويب Download Data.
2. يحدد pairs + timeframe + range.
3. يشغل download data.
4. يعرض التطبيق terminal output + status.
5. بعد النجاح، تصبح البيانات جاهزة للـ backtest.

---

## Flow 3 — Run Backtest
1. المستخدم يفتح تبويب Backtest.
2. يختار:
   - strategy
   - timeframe
   - pairs
   - timerange
   - runtime settings اللازمة
3. يشغل backtest.
4. التطبيق يعرض terminal output المباشر.
5. عند النجاح:
   - يقرأ النتائج
   - يحفظ run history
   - يعرض results بشكل منظم

---

## Flow 4 — Results Display
بعد انتهاء backtest، يجب أن تعرض النتائج على طبقات:

### Summary
- start wallet
- end wallet
- after-fee profit absolute
- after-fee profit percent
- total trades
- trades/day أو equivalent rate
- win rate
- drawdown المهم

### Pair and Trade Views
- pair-level performance
- all trades list
- breakdowns المهمة

### Run Metadata
- strategy name
- timeframe
- pairs used
- timerange
- run timestamp
- source version if known

---

## Flow 5 — Logic Analysis
بعد عرض النتائج، يقدّم التطبيق تحليلًا منطقيًا أساسيًا لا يحتاج AI.

أمثلة:
- عدد trades منخفض جدًا
- stoploss واسع جدًا
- strategy produces weak frequency for the chosen timeframe
- البيانات أو الإعدادات لا تخدم النمط المطلوب
- الربح ضعيف بالنسبة للمخاطرة

الناتج هنا يكون:
- مشكلة مكتشفة
- تفسير مختصر
- suggestion واضح إن أمكن
- زر `Apply Suggestion` عندما يكون الاقتراح deterministic وآمن

---

## Flow 6 — Deep Analysis (Later Layer)
هذه طبقة أعلى تستخدم AI لاحقًا.

المطلوب منها:
- تحليل أعمق للنتائج
- تفسير أسباب الضعف
- اقتراح اتجاه التحسين
- دعم الشات بأسئلة من المستخدم

**لكن هذه الطبقة ليست أولوية التنفيذ الأولى.**
في المرحلة الحالية يكفي:
- placeholders
- disabled states
- provider settings shell

---

## Flow 7 — Choose Optimization Path
بعد النتائج والتحليل، المستخدم يختار أحد المسارات:

1. **No action** — يكتفي بالنتيجة
2. **Apply logic suggestion** — اقتراح deterministic معروف
3. **Parameter optimization**
4. **Rule-based fixes**
5. **Hyperopt-like optimization**
6. **AI code optimization** (later full implementation)

---

## Flow 8 — Candidate Version Creation
أي optimization مهم يجب أن ينشئ candidate version.

المحتوى المتوقع للنسخة المرشحة:
- strategy code candidate
- parameter JSON candidate
- metadata describing source and reason

قبل أي backtest جديد على candidate:
1. يظهر diff للتغييرات
2. يراجع المستخدم التعديلات
3. يضغط Apply إذا أراد المتابعة

`Apply` هنا لا يعني اعتماد نهائي.
هو يعني فقط: تجهيز candidate وتجربته.

---

## Flow 9 — Backtest Candidate Version
1. بعد Apply على candidate، يشغل التطبيق backtest جديد.
2. يربط run الجديد بالـ candidate version.
3. يعرض نتائج candidate run بشكل كامل.

---

## Flow 10 — Comparison
بعد انتهاء candidate backtest، يظهر compare واضح بين:
- current accepted state
- candidate state

يشمل:
- wallet start/end
- after-fee profit
- trade count
- win rate
- drawdown
- other important metrics
- version/source information

---

## Flow 11 — Decision
بعد المقارنة، للمستخدم قرارات واضحة:

### Accept
- ترقية candidate إلى النسخة المعتمدة
- تحديث history
- حفظ العلاقة بين code + json + result

### Reject
- رفض candidate
- الإبقاء على النسخة المعتمدة

### Rollback
- الرجوع إلى نسخة تاريخية سابقة
- استرجاع strategy code + matching parameter JSON

### Continue Optimization
- استخدام النسخة الحالية أو candidate كنقطة انطلاق لجولة جديدة

---

## Flow 12 — Strategy Config Editing
يوجد تبويب مخصص يعرض:
- ملف الاستراتيجية `.py`
- ملف الإعدادات `.json`

المستخدم يستطيع:
- القراءة
- التعديل
- حفظ التغيير
- تشغيل backtest مباشرة بعده
- رؤية diff عند الحاجة

هذا المسار يجب أن يعمل حتى بدون AI.

---

## Flow 13 — Versions and History
يوجد تبويب أو view للتاريخ يعرض بشكل مبسط:
- all runs
- versions
- linked strategy/config state if known
- key summary metrics
- rollback entry points

الهدف أن يصبح التاريخ قابلًا للفهم السريع، لا مجرد ملفات مبعثرة.

---

## Flow 14 — Chat Panel (Placeholder First)
على المدى القريب:
- shell / placeholder
- UI container
- provider settings placeholders
- empty or disabled states

على المدى الأبعد:
- natural-language control over backtest / analysis / suggestions
- product help and troubleshooting
- strategy creation guidance
- AI-assisted optimization

لكن التطبيق يجب أن يبقى مفيدًا حتى قبل اكتمال هذه الطبقة.
