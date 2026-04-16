# Requirements Document

## Introduction

نظام إدارة نسخ الاستراتيجيات (Strategy Versioning System) هو نظام يضمن أن أي تعديل على ملف استراتيجية (`.py`) أو ملف الإعدادات المرتبط به (`.json`) يمر عبر مرحلة **candidate** قبل أن يُقبل أو يُرفض. يحتفظ النظام بـ snapshots كاملة لكلا الملفين عند كل نسخة، ويربط كل backtest run بالنسخة التي شغّلته.

النظام يندمج مع البنية الحالية للتطبيق: يُخزَّن بجانب مجلد `backtest_results` تحت `user_data`، ويستخدم `@dataclass` للـ DTOs الداخلية، ويتبع نفس أنماط `RunStore` و`IndexStore` الموجودة.

---

## Glossary

- **Version**: سجل يمثل حالة محددة لملفَي الاستراتيجية (`.py`) و(`.json`) في لحظة زمنية معينة.
- **VersionStore**: الخدمة المسؤولة عن حفظ وتحميل وتحديث النسخ على القرص.
- **VersionIndex**: فهرس JSON يتتبع جميع النسخ لكل استراتيجية.
- **Snapshot**: نسخة محفوظة من محتوى ملف في لحظة إنشاء النسخة.
- **Candidate**: حالة النسخة الأولية — التعديل مقترح ولم يُقبل بعد.
- **Active**: حالة النسخة المقبولة والمفعّلة حالياً للاستراتيجية.
- **Accepted**: حالة نسخة سبق قبولها (تاريخية، ليست الحالية).
- **Rejected**: حالة نسخة تم رفضها.
- **SourceType**: مصدر إنشاء النسخة — `manual_edit` أو `optimize` أو `ai_candidate_future` أو `rule_based_future`.
- **BacktestRun**: تشغيل backtest واحد مرتبط بنسخة محددة.
- **VersioningService**: طبقة الخدمة التي تنسّق عمليات الإنشاء والقبول والرفض.
- **System**: نظام إدارة نسخ الاستراتيجيات بمجمله.

---

## Requirements

### Requirement 1: نموذج بيانات النسخة

**User Story:** As a strategy developer, I want a clear and complete version data model, so that every version captures all the information needed to reproduce and audit strategy changes.

#### Acceptance Criteria

1. THE `VersionStore` SHALL represent each version with the following fields: `version_id` (UUID string), `strategy_name` (string), `base_version_id` (optional UUID string or None for the first version), `status` (one of: `active`, `candidate`, `accepted`, `rejected`), `strategy_snapshot_path` (string path), `config_snapshot_path` (string path), `source_type` (one of: `manual_edit`, `optimize`, `ai_candidate_future`, `rule_based_future`), `created_at` (ISO-8601 datetime string), and `notes` (optional string).

2. THE `VersionStore` SHALL implement the version model as a `@dataclass` named `StrategyVersion`.

3. WHEN a `StrategyVersion` is serialized to JSON, THE `VersionStore` SHALL produce a dict containing all fields with their exact names as defined in criterion 1.

4. WHEN a `StrategyVersion` is deserialized from JSON, THE `VersionStore` SHALL reconstruct a `StrategyVersion` instance with all fields correctly typed.

5. FOR ALL valid `StrategyVersion` objects, serializing then deserializing SHALL produce an equivalent object (round-trip property).

---

### Requirement 2: حفظ Snapshots للملفين

**User Story:** As a strategy developer, I want both the `.py` and `.json` files to be snapshotted at version creation time, so that I can always recover the exact state of any version.

#### Acceptance Criteria

1. WHEN a new version is created for a strategy, THE `VersionStore` SHALL copy the strategy `.py` file into `{user_data}/strategy_versions/{strategy_name}/{version_id}/strategy.py`.

2. WHEN a new version is created for a strategy, THE `VersionStore` SHALL copy the strategy `.json` config file into `{user_data}/strategy_versions/{strategy_name}/{version_id}/config.json`.

3. IF the strategy `.py` file does not exist at the given path, THEN THE `VersionStore` SHALL raise a `FileNotFoundError` with a descriptive message.

4. IF the strategy `.json` config file does not exist at the given path, THEN THE `VersionStore` SHALL raise a `FileNotFoundError` with a descriptive message.

5. WHEN snapshots are saved, THE `VersionStore` SHALL write a `version.json` metadata file alongside the snapshots in the same version directory.

6. WHEN a version directory is created, THE `VersionStore` SHALL use `mkdir(parents=True, exist_ok=True)` to ensure the path exists before writing files.

---

### Requirement 3: دورة حياة النسخة (Lifecycle)

**User Story:** As a strategy developer, I want to control the lifecycle of each version (candidate → active/rejected), so that only reviewed and approved changes become the active version.

#### Acceptance Criteria

1. WHEN a new version is created, THE `VersioningService` SHALL assign it the status `candidate`.

2. WHEN a `candidate` version is accepted, THE `VersioningService` SHALL change its status to `active` and change the previous `active` version for the same strategy (if any) to `accepted`.

3. WHEN a `candidate` version is rejected, THE `VersioningService` SHALL change its status to `rejected`.

4. WHILE a strategy has an `active` version, THE `VersioningService` SHALL ensure exactly one version per strategy holds the `active` status at any time.

5. IF an attempt is made to accept a version whose status is not `candidate`, THEN THE `VersioningService` SHALL raise a `ValueError` with a descriptive message.

6. IF an attempt is made to reject a version whose status is not `candidate`, THEN THE `VersioningService` SHALL raise a `ValueError` with a descriptive message.

7. WHEN a version is accepted, THE `VersioningService` SHALL set `base_version_id` on the new `active` version to the `version_id` of the previously `active` version (or None if no prior active version exists).

---

### Requirement 4: الفهرس (Version Index)

**User Story:** As a strategy developer, I want a fast index of all versions per strategy, so that I can list and navigate version history without reading every snapshot file.

#### Acceptance Criteria

1. THE `VersionIndex` SHALL maintain a JSON file at `{user_data}/strategy_versions/{strategy_name}/index.json` containing all versions for that strategy.

2. WHEN a version is created or its status changes, THE `VersionIndex` SHALL update the index file to reflect the new state.

3. WHEN the index file is loaded, THE `VersionIndex` SHALL return a list of `StrategyVersion` objects sorted by `created_at` descending (newest first).

4. IF the index file does not exist, THEN THE `VersionIndex` SHALL return an empty list without raising an error.

5. WHEN `VersionIndex.rebuild` is called for a strategy, THE `VersionIndex` SHALL scan all version directories under `{user_data}/strategy_versions/{strategy_name}/` and reconstruct the index from `version.json` files.

6. FOR ALL sequences of create/accept/reject operations, THE `VersionIndex` SHALL reflect the final status of every version accurately after each operation (consistency property).

---

### Requirement 5: ربط Backtest Run بالنسخة

**User Story:** As a strategy developer, I want every backtest run to be linked to the version that was active when it ran, so that I can trace which code produced which results.

#### Acceptance Criteria

1. WHEN a backtest run is saved via `RunStore.save()`, THE `RunStore` SHALL accept an optional `version_id` parameter and write it into `meta.json` under the key `"version_id"`.

2. WHEN `meta.json` is written without a `version_id`, THE `RunStore` SHALL write `"version_id": null` to preserve schema consistency.

3. WHEN a run's `meta.json` is loaded, THE `VersioningService` SHALL be able to retrieve the associated `StrategyVersion` by reading the `version_id` field from `meta.json`.

4. IF the `version_id` stored in a run's `meta.json` does not correspond to any known version, THEN THE `VersioningService` SHALL return `None` without raising an error.

5. WHEN the global `IndexStore` or `StrategyIndexStore` index entry is written for a run, THE `VersionStore` SHALL include the `version_id` field in the index entry alongside existing fields.

---

### Requirement 6: إنشاء نسخة من تعديل يدوي

**User Story:** As a strategy developer, I want to create a candidate version from a manual edit of the strategy files, so that my changes are tracked before being applied.

#### Acceptance Criteria

1. WHEN `VersioningService.create_candidate` is called with a `strategy_name`, `strategy_py_path`, `config_json_path`, and `source_type=manual_edit`, THE `VersioningService` SHALL create a new `StrategyVersion` with status `candidate`, snapshot both files, persist the version, and return the new `StrategyVersion`.

2. WHEN `VersioningService.create_candidate` is called with `source_type=optimize`, THE `VersioningService` SHALL accept an optional `notes` string and store it in the version metadata.

3. THE `VersioningService` SHALL generate a unique `version_id` using `uuid.uuid4()` for every new version.

4. WHEN two candidates are created for the same strategy in sequence, THE `VersioningService` SHALL assign each a distinct `version_id`.

---

### Requirement 7: استرجاع النسخة النشطة

**User Story:** As a strategy developer, I want to retrieve the currently active version for a strategy, so that I know which version is in use before running a backtest.

#### Acceptance Criteria

1. WHEN `VersioningService.get_active_version` is called with a `strategy_name`, THE `VersioningService` SHALL return the single `StrategyVersion` with status `active` for that strategy, or `None` if no active version exists.

2. WHEN `VersioningService.list_versions` is called with a `strategy_name`, THE `VersioningService` SHALL return all versions for that strategy sorted by `created_at` descending.

3. WHEN `VersioningService.get_version` is called with a `version_id`, THE `VersioningService` SHALL return the corresponding `StrategyVersion` or `None` if not found.

---

### Requirement 8: متانة التخزين (Storage Robustness)

**User Story:** As a strategy developer, I want the versioning storage to be resilient to partial failures, so that a crash during a write does not corrupt the version index.

#### Acceptance Criteria

1. WHEN writing a `version.json` file, THE `VersionStore` SHALL write to a temporary file in the same directory and then atomically rename it to the final path.

2. IF a `version.json` file is malformed or unreadable during index rebuild, THEN THE `VersionIndex` SHALL skip that entry, log a warning, and continue processing remaining entries.

3. IF the version directory for a given `version_id` already exists when creating a new version, THEN THE `VersionStore` SHALL raise a `ValueError` indicating a duplicate version ID.
