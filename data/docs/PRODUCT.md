# PRODUCT.md — Freqtrade GUI

## الهدف الحقيقي

واجهة رسومية لـ Freqtrade تُلغي الحاجة للـ CLI في المهام اليومية:
- تشغيل backtests وعرض نتائجها
- تحميل بيانات OHLCV
- إدارة الإعدادات والمسارات
- تصفح تاريخ الـ runs وتحميلها

المستخدم المستهدف: متداول يستخدم Freqtrade ويريد workflow أسرع بدون terminal.

---

## ما يُعتبر Feature صحيح

- أي شيء يختصر خطوة CLI يقوم بها المستخدم يدوياً
- عرض نتائج backtest بشكل مقروء (summary + trades)
- حفظ تاريخ الـ runs وإمكانية مقارنتها
- إعدادات تُحفظ وتُستعاد بين الجلسات
- terminal output حي أثناء تشغيل الأوامر
- pair selector مع favorites

---

## ما هو خارج النطاق

- live trading أو dry-run management
- تعديل strategy code من داخل التطبيق
- charting أو رسم equity curves
- hyperopt runner (ثقيل جداً للـ GUI)
- multi-strategy comparison charts
- أي شيء يتطلب freqtrade API أو REST
- AI strategy generation (placeholder فقط حالياً)
