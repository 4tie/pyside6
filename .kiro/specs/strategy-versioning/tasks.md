# Tasks — Strategy Versioning

## Task List

- [ ] 1. إنشاء حزمة `app/core/versioning/` والـ models
  - [ ] 1.1 إنشاء `app/core/versioning/__init__.py` (فارغ)
  - [ ] 1.2 إنشاء `app/core/versioning/version_models.py` — `StrategyVersion` dataclass + `version_to_dict` + `version_from_dict`

- [ ] 2. تنفيذ `VersionStore`
  - [ ] 2.1 إنشاء `app/core/versioning/version_store.py`
  - [ ] 2.2 تنفيذ `VersionStore.save_version` — ينسخ `strategy.py` و`config.json`، يكتب `version.json` ذرياً
  - [ ] 2.3 تنفيذ `VersionStore.load_version` — يقرأ `version.json` ويُعيد `StrategyVersion`
  - [ ] 2.4 تنفيذ `VersionStore.update_status` — يُعيد كتابة `version.json` بالحالة الجديدة ذرياً

- [ ] 3. تنفيذ `VersionIndex`
  - [ ] 3.1 إنشاء `app/core/versioning/version_index.py`
  - [ ] 3.2 تنفيذ `VersionIndex.update` — upsert في `index.json`
  - [ ] 3.3 تنفيذ `VersionIndex.load` — يُرجع `[]` إذا لم يوجد الملف، مرتبة بـ `created_at` تنازلياً
  - [ ] 3.4 تنفيذ `VersionIndex.rebuild` — يمسح مجلدات النسخ ويُعيد بناء الفهرس، يتجاهل الملفات التالفة

- [ ] 4. تنفيذ `VersioningService`
  - [ ] 4.1 إنشاء `app/core/versioning/versioning_service.py`
  - [ ] 4.2 تنفيذ `create_candidate` — ينشئ UUID، يستدعي `VersionStore.save_version`، يُحدّث الفهرس
  - [ ] 4.3 تنفيذ `accept_version` — ينقل الـ active السابق إلى `accepted`، يُحوّل الـ candidate إلى `active`، يضبط `base_version_id`
  - [ ] 4.4 تنفيذ `reject_version` — يُحوّل الـ candidate إلى `rejected`، يرفع `ValueError` إذا لم يكن candidate
  - [ ] 4.5 تنفيذ `get_active_version`، `list_versions`، `get_version`، `get_version_for_run`

- [ ] 5. تعديل `RunStore.save()` لدعم `version_id`
  - [ ] 5.1 إضافة parameter `version_id: Optional[str] = None` لـ `RunStore.save()`
  - [ ] 5.2 تحديث `_write_meta()` لتكتب `"version_id": version_id` (أو `null`)
  - [ ] 5.3 تحديث `IndexStore.update()` و`StrategyIndexStore.update()` لتمرير `version_id` في الـ entry

- [ ] 6. كتابة Unit Tests
  - [ ] 6.1 `tests/core/versioning/test_version_models.py` — serialization، deserialization، حقول مفقودة
  - [ ] 6.2 `tests/core/versioning/test_version_store.py` — save/load/update_status، FileNotFoundError، ValueError للـ duplicate
  - [ ] 6.3 `tests/core/versioning/test_version_index.py` — load على ملف غير موجود، update، rebuild مع ملف تالف
  - [ ] 6.4 `tests/core/versioning/test_versioning_service.py` — دورة الحياة الكاملة، accept/reject errors، get_active_version
  - [ ] 6.5 `tests/core/versioning/test_run_store_version.py` — RunStore.save مع وبدون version_id

- [ ] 7. كتابة Property-Based Tests
  - [ ] 7.1 `tests/core/versioning/test_properties.py` — Property 1: serialization round-trip
  - [ ] 7.2 Property 2: index consistency بعد تسلسل عمليات عشوائية
  - [ ] 7.3 Property 3: at-most-one-active invariant
  - [ ] 7.4 Property 4: unique version IDs
