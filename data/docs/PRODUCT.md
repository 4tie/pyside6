# PRODUCT.md — Product Definition

## 1) What this product is
هذا التطبيق هو **منصة تشغيل وتحليل وتحسين لاستراتيجيات Freqtrade** داخل واجهة PySide6.

هو ليس مجرد شاشة لتشغيل الأوامر، وليس مجرد شات AI.
المنتج الحقيقي هو:
- تشغيل backtest
- قراءة النتائج بوضوح
- استخراج المشاكل المعروفة منطقيًا
- دعم تحليل أعمق لاحقًا
- إنشاء تعديلات آمنة على الاستراتيجية
- إعادة الاختبار
- مقارنة النسخ
- قبول أو رفض أو rollback بشكل واضح

---

## 2) الهدف النهائي
نقل المستخدم من:

**Strategy + Parameters + Runtime Settings**

إلى:

**Backtest + Organized Results + Analysis + Candidate Change + Re-test + Comparison + Accept / Rollback**

بشكل آمن ومنظم وقابل للتتبع.

---

## 3) المستخدم المستهدف
المستخدم هو شخص يعمل على Freqtrade ويريد:
- تشغيل أسرع من CLI
- رؤية أوضح للنتائج
- فهم سبب الضعف أو الخسارة
- تعديل الاستراتيجية وملف الإعدادات بسهولة
- تجربة التحسينات بدون تخريب النسخة الأساسية

---

## 4) الأعمدة الرئيسية للمنتج

### A. Execution
تشغيل:
- backtest
- download data
- optimization غير المعتمد على AI
- إدارة المسارات والإعدادات

### B. Results
عرض:
- الربح بعد الرسوم
- start wallet / end wallet
- profit absolute / percent
- عدد الصفقات
- trade frequency
- pair breakdown
- trade details
- metrics المهمة

### C. Logic Analysis
تحليل منطقي مباشر لا يحتاج AI، مثل:
- stoploss غير منطقي
- عدد صفقات منخفض جدًا
- strategy behavior واضح الضعف
- مشاكل إعدادات أو بيانات

### D. Deep Analysis
طبقة أعلى لاحقة تستخدم AI لفهم أعمق:
- سبب الخسارة
- ضعف الدخول أو الخروج
- ملاءمة timeframe
- ملاءمة pairs
- اقتراح اتجاه التحسين

### E. Optimization
التحسين له 4 أوضاع:
1. Parameter-only
2. Rule-based fixes
3. Hyperopt-like / numeric search
4. AI code optimization

### F. Versioning
أي نتيجة مهمة أو تعديل مهم يجب أن تكون قابلة للتتبع والمقارنة.

### G. Comparison and Decision
المستخدم لا يستلم مجرد “اقتراح”.
المستخدم يرى:
- ما الذي تغيّر
- هل النتيجة تحسنت
- ما الذي يجب قبوله أو رفضه

---

## 5) تعريف النتيجة

### قواعد ثابتة
- الربح دائمًا يُحسب **بعد الرسوم**.
- الثبات عبر أكثر من فترة مهم جدًا.
- الربح مهم جدًا.

### قواعد نسبية
النتيجة الجيدة تختلف حسب:
- نوع الاستراتيجية
- أسلوبها
- عدد الصفقات المناسب لها
- هل المشكلة من stoploss
- هل الأفضل زيادة trades أو تقليل المخاطرة

لذلك لا يجوز استخدام حكم جامد واحد على كل الاستراتيجيات.

---

## 6) نسخة المنتج الحالية مقابل المستهدفة

### ما يجب أن يعمل أولًا
- settings
- paths and validation
- download data
- backtest
- results parsing and display
- logic analysis
- strategy/config editing
- candidate versions
- compare / accept / rollback / history

### ما يمكن وضعه الآن كـ placeholder فقط
- chat panel
- AI provider settings
- AI assistant shell
- deep analysis entry points
- future provider connectors

### ما لا يجب أن يصبح أولوية الآن
- provider integration complexity
- agent orchestration complexity
- live AI coding as a required dependency for the app to be useful

---

## 7) قاعدة النسخ المعتمدة

### AI optimization
أي تعديل ناتج عن AI optimization يجب أن:
- ينشئ candidate version
- يعرض diff قبل apply
- يعرض diff قبل backtest الجديد
- يشغل backtest على candidate فقط
- ينتظر user accept قبل الترقية

### Manual user edit
تعديل المستخدم اليدوي يمكن دعمه داخل المحرر، لكن يجب أن يبقى واضحًا للمستخدم ما إذا كان:
- تعديلًا مباشرًا على الملف الحالي
- أو تعديلًا على نسخة عمل / candidate

أما AI optimization فلا يلمس النسخة الأساسية مباشرة.

---

## 8) فلسفة القرارات داخل المنتج
- القرار النهائي عند المستخدم.
- AI أو النظام يقترح، لا يفرض.
- الأزرار الواضحة أهم من السلوك الخفي.
- كل خطوة مهمة يجب أن تكون مفهومة وقابلة للرجوع.

---

## 9) غير داخل النطاق حاليًا
- جعل AI شرطًا لاستخدام التطبيق
- auto-promote silent changes
- إخفاء version history
- تعديل النسخة الأساسية تلقائيًا من AI بدون قبول صريح
