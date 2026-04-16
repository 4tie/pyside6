# AGENTS.md — قواعد التنفيذ للـ AI

## قبل أي شيء

1. اقرأ `WORKFLOW.md` — كل تغيير يمر بخطواته
2. اقرأ `ARCHITECTURE.md` — افهم أين تقع الملفات
3. اقرأ `data/rules/guidelines.md` — قواعد الكود
4. استدعِ `get_workflow_rules()` من MCP لتحميل القواعد المحفوظة

---

## قواعد التنفيذ المباشرة

### لا تنشئ duplicate logic
- قبل كتابة دالة جديدة، ابحث إذا كانت موجودة
- `CommandRunner` يبني الأوامر — لا تبني أوامر في الـ UI
- `ProcessService` ينفّذ الأوامر — لا تستخدم `subprocess` في الـ UI
- `RunStore` يحفظ الـ runs — لا تكتب JSON مباشرة من الـ UI

### عدّل الملفات الموجودة أولاً
- لا تنشئ ملفاً جديداً إذا كان التغيير يناسب ملفاً موجوداً
- لا تنشئ service جديد إذا كان يمكن إضافة method لـ service موجود

### لا تغيّر structure بدون داع
- لا تعيد تنظيم imports
- لا تغير اسم دالة موجودة تعمل
- لا تحول `@staticmethod` لـ instance method بدون سبب
- لا تغير Pydantic model fields بدون تحديث migration plan

### Process execution — قاعدة صارمة
```python
# صح دائماً
process_service.execute_command([cmd.program] + cmd.args, ...)

# خطأ دائماً — يكسر المسارات التي تحتوي spaces
command_string = f"{cmd.program} {' '.join(cmd.args)}"
command_list = command_string.split()
process_service.execute_command(command_list, ...)
```

### Freqtrade zip location
- freqtrade يكتب الـ zip في `backtest_results/*.zip` دائماً
- `--export-filename` يُتجاهل من freqtrade
- `_try_load_results` تبحث بـ timestamp filter — لا تغير هذا

### لا تسوّي commit
- انتظر تأكيد المستخدم دائماً قبل commit
- اعرض ما تغيّر أولاً

---

## أي تغيير يجب أن يمر على الاختبارات

```bash
# بعد أي تغيير في app/core/
pytest tests/ --tb=short

# بعد تغيير في app/ui/ — تحقق يدوياً
python main.py
```

---

## MCP Startup Sequence

```python
get_workflow_rules()          # قواعد محفوظة
get_paths()                   # مسارات المشروع
read_rule("guidelines.md")    # coding standards
read_rule("structure.md")     # project layout
list_ui_files()               # اكتشاف الملفات قبل التعديل
```

---

## Logging Pattern

```python
from app.core.utils.app_logger import get_logger
_log = get_logger("module_name")

_log.debug("...")    # تفاصيل البيانات
_log.info("...")     # lifecycle events
_log.cmd("...")      # command execution — يظهر أخضر في console
_log.warning("...")  # مشاكل قابلة للتعافي
_log.error("...")    # فشل
```

---

## Section → Log File

| Logger name | ملف الـ log |
|-------------|------------|
| `ui.*` | `data/log/ui.log` |
| `services.*`, `backtest`, `settings`, `download` | `data/log/services.log` |
| `process` | `data/log/process.log` |
| الكل | `data/log/app.log` |

---

## ما لا تفعله أبداً

- لا تستورد UI code من service layer
- لا تستخدم hardcoded paths مثل `T:/ae/pyside6`
- لا تستخدم `sys.path.insert` في أي ملف من الـ app
- لا تضع `import json` داخل دالة — ضعه في أعلى الملف
- لا تبني command كـ string ثم تعمل `split()`
- لا تحذف أو تعيد كتابة test cases موجودة
