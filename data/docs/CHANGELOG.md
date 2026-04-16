# CHANGELOG.md

## [2026-04-16] — Fix: command string/split bug + backtest zip path alignment

**نوع:** fix

**ماذا تغيّر:**
- `backtest_page.py` و `dd_page.py` كانا يحولان الـ command لـ string ثم `split()` قبل التنفيذ
- `command_runner.py` كان يمرر `--export-filename` لـ freqtrade الذي يتجاهله
- `_try_load_results` كانت تحمّل أي zip موجود بدل الـ zip الجديد فقط

**لماذا:**
- `string.split()` يكسر المسارات التي تحتوي spaces على Windows
- `--export-filename` يُتجاهل من freqtrade — يسبب confusion في الـ export_dir
- تحميل أقدم zip يعطي نتائج خاطئة إذا كان عندك runs قديمة

**الملفات المعدّلة:**
- `app/ui/pages/backtest_page.py` — `[cmd.program] + cmd.args` مباشرة، timestamp filter للـ zip
- `app/ui/pages/dd_page.py` — `[cmd.program] + cmd.args` مباشرة
- `app/core/freqtrade/command_runner.py` — حذف `--export-filename`، `export_dir` يشير للجذر

**كيف تم التحقق:**
- code review manual

**Breaking change:** لا

---

## [2026-04-16] — Refactor: logging → data/log/ with per-section files + colors

**نوع:** refactor

**ماذا تغيّر:**
- Log files تُكتب في `data/log/` بدل `user_data/logs/`
- كل section له ملف خاص: `ui.log`, `services.log`, `process.log`, `app.log`
- Console output ملوّن: أخضر للـ CMD، أحمر للـ ERROR، أصفر للـ WARNING
- Custom level `CMD` (25) لتسجيل تنفيذ الأوامر

**لماذا:**
- `user_data/` مخصص لـ freqtrade، الـ app logs تنتمي لـ `data/`
- تسهيل debugging بفصل الـ logs حسب القسم

**الملفات المعدّلة:**
- `app/core/utils/app_logger.py` — إعادة كتابة كاملة
- `main.py` — تمرير `data/log/` بدل `user_data_path`

**كيف تم التحقق:**
- code review manual

**Breaking change:** لا — لكن الـ log path تغيّر

---

## [2026-04-16] — Fix: freqtrade parameter JSON format

**نوع:** fix

**ماذا تغيّر:**
- كل ملفات `*.json` في `user_data/strategies/` أُعيد كتابتها بالـ format الصحيح

**لماذا:**
- freqtrade يرفض الملف بـ "Invalid parameter file" إذا لم يحتوِ `strategy_name` و `params` wrapper
- تم التحقق من `freqtrade/strategy/hyper.py` source مباشرة

**الملفات المعدّلة:**
- `user_data/strategies/MultiMeee.json`
- `user_data/strategies/MultiMa.json`
- `user_data/strategies/MultiMa_v2.json`
- `user_data/strategies/MultiMa_v3.json`
- `user_data/strategies/MohsBaseline_v2.json`

**كيف تم التحقق:**
- قراءة freqtrade source: `params.get("strategy_name") != self.__class__.__name__`

**Breaking change:** نعم — الـ JSON القديم لا يعمل مع freqtrade الجديد

---

## [2026-04-16] — Chore: repo cleanup

**نوع:** chore

**ماذا تغيّر:**
- نقل `test_*.py` إلى `tests/core/`
- حذف `validate_*.py` (6 ملفات)
- حذف `a.py`, `rebuild_strategy_indexes.py`, `mcp_pyside6.py` (root)
- حذف `docs/`, `logs/`, `tools/` من الـ root (انتقلت لـ `data/`)
- حذف `.md` القديمة من الـ root

**لماذا:**
- تنظيف الـ root من الملفات المؤقتة والمكررة

**الملفات المعدّلة:**
- root directory

**Breaking change:** لا
