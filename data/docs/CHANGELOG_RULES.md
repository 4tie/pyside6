# CHANGELOG_RULES.md

## كيف تسجّل أي تعديل

كل تعديل يُسجَّل في `data/docs/CHANGELOG.md` بهذا الـ format:

```
## [YYYY-MM-DD] — عنوان قصير

**نوع:** fix | feat | refactor | docs | chore

**ماذا تغيّر:**
وصف واضح لما تغيّر في السلوك أو الكود.

**لماذا:**
السبب — bug، طلب مستخدم، تحسين، إلخ.

**الملفات المعدّلة:**
- `app/ui/pages/backtest_page.py` — وصف التغيير
- `app/core/freqtrade/command_runner.py` — وصف التغيير

**كيف تم التحقق:**
- pytest passed / manual test / log review

**Breaking change:** نعم / لا
إذا نعم: ما الذي يتأثر وكيف يتعامل معه المستخدم.
```

---

## متى تسجّل

- أي تغيير في `app/core/` → **إلزامي**
- أي تغيير في `app/ui/` يغيّر behavior → **إلزامي**
- تغيير في `data/docs/` فقط → **اختياري**
- تغيير في `user_data/strategies/*.json` → **إلزامي** (breaking potential)

---

## Breaking Changes

تغيير يُعتبر breaking إذا:
- غيّر format ملف JSON محفوظ (`settings.json`, `index.json`, `meta.json`)
- غيّر signature دالة في service layer
- غيّر اسم signal في `SettingsState`
- حذف أو غيّر اسم field في Pydantic model

---

## ما لا يحتاج تسجيل

- تغييرات في `data/log/`
- تغييرات في `.gitignore`
- تحديث `requirements.txt` بدون تغيير behavior
