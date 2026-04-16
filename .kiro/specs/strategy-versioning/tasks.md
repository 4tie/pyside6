# Tasks — Strategy Versioning

## Task List

- [x] 1. إنشاء حزمة `app/core/versioning/` والـ models
  - [x] 1.1 إنشاء `app/core/versioning/__init__.py` (فارغ)
  - [x] 1.2 إنشاء `app/core/versioning/version_models.py` — `StrategyVersion` dataclass + `version_to_dict` + `version_from_dict`
  - [x] 1.3 إضافة `VersionStatus` و`VersionSource` enums في `version_models.py`

- [x] 2. تنفيذ `VersionStore`
  - [x] 2.1 إنشاء `app/core/versioning/version_store.py`
  - [x] 2.2 تنفيذ `VersionStore.save_version` — ينسخ `strategy.py` و`config.json`، يكتب `version.json` ذرياً
  - [x] 2.3 تنفيذ `VersionStore.load_version` — يقرأ `version.json` ويُعيد `StrategyVersion`
  - [x] 2.4 تنفيذ `VersionStore.update_status` — يُعيد كتابة `version.json` بالحالة الجديدة ذرياً

- [x] 3. تنفيذ `VersionIndex`
  - [x] 3.1 إنشاء `app/core/versioning/version_index.py`
  - [x] 3.2 تنفيذ `VersionIndex.update` — upsert في `index.json`
  - [x] 3.3 تنفيذ `VersionIndex.load` — يُرجع `[]` إذا لم يوجد الملف، مرتبة بـ `created_at` تنازلياً
  - [x] 3.4 تنفيذ `VersionIndex.rebuild` — يمسح مجلدات النسخ ويُعيد بناء الفهرس، يتجاهل الملفات التالفة
  - [x] 3.5 فرض invariant أثناء `rebuild`: إذا وُجد أكثر من `active` لنفس الاستراتيجية، يُبقي الأحدث `active` ويُحوّل الباقين إلى `accepted`، ويُسجّل warning لكل حالة

- [x] 4. تنفيذ `VersioningService`
  - [x] 4.1 إنشاء `app/core/versioning/versioning_service.py`
  - [x] 4.2 تنفيذ `create_candidate` — ينشئ UUID، يستدعي `VersionStore.save_version`، يُحدّث الفهرس
  - [x] 4.3 تنفيذ `accept_version`
    - [x] نسخ `snapshot_strategy_path` → `strategy_file_path` عبر temp file + `Path.replace()` (أولاً)
    - [x] نسخ `snapshot_params_path` → `live_params_path` عبر temp file + `Path.replace()` (أولاً)
    - [x] بعد نجاح النسخ فقط: نقل الـ `active` السابق إلى `accepted` وتحديث `updated_at`
    - [x] تحويل الـ `candidate` إلى `active` وتحديث `updated_at`
    - [x] ضبط `base_version_id` على الـ `active` الجديد ليشير إلى الـ `active` السابق
    - [x] تحديث الفهرس لكلا النسختين
  - [x] 4.4 تنفيذ `reject_version` — يُحوّل الـ `candidate` إلى `rejected`، يرفع `ValueError` إذا لم يكن `candidate`
  - [x] 4.5 تنفيذ `get_active_version`، `list_versions`، `get_version`، `get_version_for_run`
    - [x] `get_version_for_run(run_meta: dict)` يقرأ `version_id` من `meta.json` (source of truth) ثم يُحمّل النسخة من القرص — الفهرس cache فقط
  - [x] 4.6 تنفيذ `build_diff_preview`
    - [x] مقارنة `strategy.py` الحالي في `user_data/strategies/` مع `snapshot_strategy_path` للـ candidate
    - [x] مقارنة `MyStrategy.json` الحالي مع `snapshot_params_path` للـ candidate
    - [x] إعادة dict منظم: `{"strategy_diff": str, "params_diff": str}` للاستخدام لاحقاً في UI

- [x] 5. تعديل `RunStore.save()` لدعم `version_id`
  - [x] 5.1 إضافة parameter `version_id: Optional[str] = None` لـ `RunStore.save()`
  - [x] 5.2 تحديث `_write_meta()` لتكتب `"version_id": version_id` (أو `null`)
  - [x] 5.3 تحديث `IndexStore.update()` و`StrategyIndexStore.update()` لتمرير `version_id` في الـ entry

- [x] 6. إعداد بيئة الاختبار وكتابة Unit Tests
  - [x] 6.0 إضافة dev test dependencies إلى `requirements.txt`
    - [x] إضافة `pytest`
    - [x] إضافة `hypothesis`
  - [x] 6.1 `tests/core/versioning/test_version_models.py` — serialization، deserialization، حقول مفقودة، VersionStatus/VersionSource enums
  - [x] 6.2 `tests/core/versioning/test_version_store.py` — save/load/update_status، FileNotFoundError، ValueError للـ duplicate
  - [x] 6.3 `tests/core/versioning/test_version_index.py` — load على ملف غير موجود، update، rebuild مع ملف تالف، invariant at-most-one-active
  - [x] 6.4 `tests/core/versioning/test_versioning_service.py` — دورة الحياة الكاملة، accept ينسخ الملفات الفعلية، reject errors، get_active_version، build_diff_preview
  - [x] 6.5 `tests/core/versioning/test_run_store_version.py` — RunStore.save مع وبدون version_id، التحقق من meta.json على القرص

- [x] 7. كتابة Property-Based Tests
  - [x] 7.1 `tests/core/versioning/test_properties.py` — Property 1: serialization round-trip لجميع حقول `StrategyVersion` بما فيها الحقول الجديدة
  - [x] 7.2 Property 2: index consistency بعد تسلسل عمليات عشوائية (create/accept/reject)
  - [x] 7.3 Property 3: at-most-one-active invariant بعد أي عدد من accept operations
  - [x] 7.4 Property 4: unique version IDs لأي عدد من استدعاءات `create_candidate`
