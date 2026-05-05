# uniqdiff Engine Report

## Назначение Документа

Этот документ фиксирует текущее состояние `uniqdiff` и его целевую роль в
экосистеме UniqTools.

`uniqdiff` должен развиваться как стабильный comparison engine: компактный,
предсказуемый и хорошо документированный слой сравнения данных, поверх которого
могут безопасно строиться другие инструменты:

- `uniqprofile`;
- `uniqschema`;
- `uniqcheck`;
- `uniqreport`;
- `uniqrowdiff`;
- `uniqtools-cli`.

Главная идея: `uniqdiff` отвечает за точное сравнение, backend-и, источники данных,
результаты и стабильный API. Он не должен превращаться в продуктовую платформу,
систему отчетности, UI, rule engine или SaaS-слой.

## Роль В Экосистеме UniqTools

`uniqdiff` является нижним engine layer.

Он предоставляет:

- единые exact comparison semantics;
- стабильное извлечение comparison token;
- backend-и для memory и out-of-core сценариев;
- стандартные result objects;
- lazy-чтение больших результатов;
- connector protocol для источников данных;
- базовый CLI для локального и CI/CD использования.

Другие инструменты должны использовать `uniqdiff` как библиотеку, а не копировать
логику сравнения.

Пример распределения ответственности:

- `uniqdiff`: сравнить два набора данных и вернуть различия;
- `uniqrowdiff`: показать изменения полей внутри совпавших по ключу строк;
- `uniqschema`: анализировать и валидировать схему;
- `uniqprofile`: строить профили данных;
- `uniqcheck`: запускать data quality checks;
- `uniqreport`: формировать HTML/PDF/Excel отчеты;
- `uniqtools-cli`: объединять инструменты в общий CLI.

## Что Сейчас Умеет uniqdiff

### 1. Exact Comparison Semantics

`uniqdiff` выполняет точное сравнение двух наборов данных.

Основные секции результата:

- элементы только в первом наборе;
- элементы только во втором наборе;
- объединенные уникальные различия;
- пересечение;
- дубликаты внутри каждого набора;
- статистика сравнения;
- metadata и warnings.

Сравнение строится вокруг comparison token. Token получается из исходного элемента
через `key`, `normalizer` и внутреннюю canonicalization-логику.

### 2. Token Extraction

Token extraction поддерживает:

- сравнение элемента целиком;
- сравнение по одному ключу;
- сравнение по нескольким ключам;
- callable key-функции;
- normalizer-функции;
- canonicalization вложенных и неhashable-структур.

Поддерживаемые типы данных:

- `dict`;
- `dataclass`;
- объекты с атрибутами;
- `list`;
- `tuple`;
- `str`;
- `int`;
- `float`;
- вложенные структуры.

Ошибки извлечения ключа и нормализации оформлены через понятные исключения.

### 3. Core Comparison Helpers

Публичные функции ядра:

- `compare`;
- `diff`;
- `unique`;
- `intersection`;
- `duplicates`.

Назначение:

- `compare`: основной entry point;
- `diff`: различия без обязательного пересечения;
- `unique`: только объединенный список отличий;
- `intersection`: только общие элементы;
- `duplicates`: дубликаты внутри одного набора.

Эти функции являются частью стабильного engine API.

### 4. Structured Comparison

Поддерживаются специализированные helpers:

- `compare_by_key`;
- `compare_by_hash`.

`compare_by_key` предназначен для структурированных строк, словарей, объектов и
dataclass-экземпляров.

`compare_by_hash` строит стабильный hash от canonical representation значения и
позволяет сравнивать сложные элементы по digest.

### 5. Source And File Comparison

Поддерживаются источники данных:

- обычные iterable;
- generators;
- streams;
- локальные файлы;
- connector-backed sources.

Публичные функции:

- `compare_iter`;
- `compare_streams`;
- `compare_files`;
- `compare_sources`;
- `duplicates_source`.

`compare_sources` является главным расширяемым entry point для экосистемы
UniqTools, потому что позволяет подключать новые источники через connector protocol.

### 6. Backends

`uniqdiff` поддерживает несколько backend-ов.

#### Memory Backend

Режим:

- `mode="memory"`.

Назначение:

- быстрые сравнения малых и средних наборов;
- простые скрипты;
- тесты;
- интерактивное использование.

Ограничение:

- входные данные и результат должны помещаться в RAM.

#### SQLite Backend

Режим:

- `mode="disk"`;
- `disk_strategy="sqlite"`.

Назначение:

- disk-backed exact comparison;
- генераторы и unsized iterables;
- снижение пикового использования RAM;
- большие результаты в `result_mode="file"`.

Ограничение:

- медленнее memory backend;
- зависит от дискового I/O.

#### Hash Partition Backend

Status: stable 1.0 backend, documented as an advanced mode.

Режим:

- `mode="disk"`;
- `disk_strategy="hash_partition"`.

Назначение:

- очень большие наборы данных;
- сравнение по партициям;
- ограничение пикового использования памяти.

Особенность:

- materialized result sections are restored by original input ordinal for that side;
- ordering should not be treated as the primary cross-backend semantic contract.

#### External Sort Backend

Status: stable 1.0 backend, documented as an advanced mode.

Режим:

- `mode="disk"`;
- `disk_strategy="external_sort"`.

Назначение:

- out-of-core сравнение через сортировку чанков и merge pass;
- большие последовательные workloads.

Особенность:

- materialized result sections are restored by original input ordinal for that side;
- ordering should not be treated as the primary cross-backend semantic contract.

#### Auto Mode

Status: stable 1.0 mode, documented as an advanced selection mode.

Режим:

- `mode="auto"`.

Назначение:

- выбор между memory и disk backend на основе documented heuristics.

Auto mode учитывает:

- `result_mode="file"`;
- наличие `temp_dir`;
- `memory_limit`;
- sized/unsized input;
- safety factor;
- оценку bytes-per-item.

Решение сохраняется в:

- `result.metadata["auto_decision"]`.

### 7. Result Modes

Поддерживаются два режима результата.

#### Memory Result Mode

Режим:

- `result_mode="memory"`.

Поведение:

- результат материализуется в `CompareResult`;
- подходит для малых и средних outputs.

#### File Result Mode

Режим:

- `result_mode="file"`.

Требования:

- `mode="disk"` или `mode="auto"`;
- обязательный `output`.

Поддерживаемые форматы:

- JSONL;
- CSV.

Поведение:

- строки результата пишутся напрямую в файл;
- большие outputs не загружаются полностью в память;
- `CompareResult` содержит stats и metadata.

### 8. Stable Result Objects

Публичные result objects:

- `CompareResult`;
- `CompareStats`.

`CompareResult` содержит:

- `only_in_first`;
- `only_in_second`;
- `common`;
- `unique`;
- `duplicates_first`;
- `duplicates_second`;
- `stats`;
- `metadata`;
- `warnings`.

`CompareStats` содержит счетчики:

- количество элементов в первом наборе;
- количество элементов во втором наборе;
- количество уникальных token-ов;
- количество элементов only-in-first;
- количество элементов only-in-second;
- количество common;
- количество duplicate entries;
- режим;
- strategy.

Эти объекты должны оставаться стабильной частью API после 1.0.

### 9. Lazy Result Readers

Поддерживаются lazy readers:

- `iter_result_rows`;
- `iter_result_values`;
- `CompareResult.iter_unique`;
- `CompareResult.iter_section`.

Назначение:

- читать большие JSONL/CSV result-файлы без полной загрузки в память;
- обрабатывать только нужные секции результата;
- давать downstream-инструментам потоковый доступ к diff output.

Это важно для:

- `uniqreport`;
- `uniqtools-cli`;
- batch pipelines;
- CI/CD;
- больших data exports.

### 10. Connector Protocol

Connector protocol состоит из:

- `name`;
- `open()`;
- `describe()`.

Контракт:

- `open()` возвращает iterator по элементам источника;
- `describe()` возвращает metadata источника;
- `name` задает имя connector-а.

Этот protocol должен оставаться простым, чтобы другие инструменты могли быстро
добавлять собственные источники.

### 11. Built-In Local Connectors

Сейчас доступны встроенные connector-ы:

- `iterable`;
- `file`;
- `csv`;
- `tsv`;
- `tab`;
- `jsonl`;
- `parquet`;
- `pq`;
- `txt`;
- `text`.

Локальные файлы поддерживают:

- CSV;
- TSV;
- JSONL;
- TXT;
- gzip variants:
  - `.csv.gz`;
  - `.tsv.gz`;
  - `.jsonl.gz`;
  - `.txt.gz`;
- Parquet через optional dependency `pyarrow`.

CSV/TSV options:

- `delimiter`;
- `quotechar`;
- `has_header`;
- `fieldnames`.

Parquet options:

- `columns`;
- `batch_size`.

Parquet intentionally optional:

- устанавливается через `uniqdiff[parquet]`;
- при отсутствии `pyarrow` выбрасывается понятная optional dependency error.

### 12. CLI

Текущий CLI:

- `uniqdiff compare`;
- `uniqdiff diff`;
- `uniqdiff intersection`;
- `uniqdiff duplicates`.

CLI поддерживает:

- `--format`;
- `--encoding`;
- `--key`;
- `--mode`;
- `--disk-strategy`;
- `--chunk-size`;
- `--memory-limit`;
- `--temp-dir`;
- `--disk-limit`;
- `--partition-count`;
- `--result-mode`;
- `--output`;
- `--summary`;
- `--fail-on-diff`;
- нормализацию строк;
- CSV/TSV dialect flags;
- Parquet column selection.

Exit code contract:

- `0`: команда успешно завершилась;
- `1`: найдены различия или дубликаты при `--fail-on-diff`;
- `2`: ошибка входных данных, формата, файла или параметров.

CLI является удобным entry point, но не должен превращаться в workflow runner или
общий orchestration layer. Это зона `uniqtools-cli`.

### 13. Stats, Metadata And Backend Decision Metadata

`uniqdiff` возвращает не только данные результата, но и operational metadata.

Metadata может включать:

- выбранный backend;
- disk strategy;
- chunk size;
- temp dir;
- disk limit;
- result mode;
- output path;
- connector descriptions;
- auto-mode decision;
- backend-specific counters.

Auto decision metadata включает:

- `estimated_items`;
- `estimated_bytes`;
- `bytes_per_item_estimate`;
- `memory_safety_factor`;
- `memory_limit_bytes`;
- `effective_memory_limit_bytes`;
- `selected_backend`;
- `reason`;
- `use_disk`.

Эти данные нужны для observability, debugging, CI/CD и будущих инструментов
экосистемы.

## Что Не Должно Входить В uniqdiff

`uniqdiff` не должен содержать продуктовую или enterprise-логику.

Не добавлять в `uniqdiff`:

- HTML/PDF/Excel reports;
- business reports;
- data cleaning;
- schema validation;
- workflow YAML runner;
- full data quality rule engine;
- dashboards;
- SaaS logic;
- enterprise/cloud connector management;
- complex UI/report templates;
- payment/licensing logic;
- user/team/project management;
- heavy database/cloud dependencies in core.

Причина:

`uniqdiff` должен оставаться легким, стабильным engine layer. Все перечисленное
должно жить в соседних инструментах UniqTools.

## Границы Ответственности По Инструментам

### uniqdiff

Отвечает за:

- exact comparison;
- token extraction;
- source reading;
- connector protocol;
- local file connectors;
- memory/disk backends;
- result objects;
- lazy result readers;
- CLI для сравнения.

### uniqrowdiff

Должен отвечать за:

- row-level diff;
- сравнение полей внутри записей с одинаковым ключом;
- changed fields;
- before/after values.

`uniqdiff` может предоставить базовые common rows, но не должен становиться полным
row-diff engine.

### uniqschema

Должен отвечать за:

- schema inference;
- schema validation;
- типы колонок;
- совместимость схем;
- schema drift.

### uniqprofile

Должен отвечать за:

- profiling данных;
- count/null/unique stats;
- distribution summaries;
- lightweight data exploration.

### uniqcheck

Должен отвечать за:

- data quality rules;
- validation checks;
- thresholds;
- rule execution.

### uniqreport

Должен отвечать за:

- HTML/PDF/Excel reports;
- визуальные summary;
- human-readable reports;
- templates.

### uniqtools-cli

Должен отвечать за:

- общий CLI;
- orchestration нескольких инструментов;
- workflow-level команды;
- unified UX.

## Стабильный Контракт После 1.0

После 1.0 `uniqdiff` должен следовать semantic versioning.

Стабильными считаются:

- публичные функции сравнения;
- `CompareResult`;
- `CompareStats`;
- documented metadata fields;
- connector protocol;
- built-in connector names;
- CLI commands and documented flags;
- CLI exit codes;
- file result row schema.

Minor releases могут добавлять:

- новые optional connectors;
- новые metadata fields;
- новые backend strategies;
- новые CLI flags;
- новые output formats;
- performance improvements.

Breaking changes должны идти только в major releases, кроме критических случаев
безопасности или исправления data corruption.

## Текущее Состояние Готовности

На текущий момент `uniqdiff` уже имеет:

- memory backend;
- SQLite disk backend;
- hash partition backend;
- external sort backend;
- auto mode;
- file result mode;
- lazy result readers;
- connector registry;
- local file connectors;
- TSV/gzip support;
- optional Parquet connector;
- CLI;
- documentation recipes;
- backend behavior docs;
- migration guide;
- backward compatibility policy;
- release 1.0 checklist;
- tests;
- type checking;
- linting;
- package build checks.

Текущий статус можно описать как stable 1.0 exact comparison engine foundation.

## Рекомендации Перед 1.0

Перед объявлением 1.0 стоит:

- провести финальный audit публичного API;
- явно отделить public modules от internal modules;
- проверить, что docs покрывают все documented flags;
- проверить CLI examples на реальных fixture-файлах;
- расширить backend equivalence tests;
- проверить file result schema на backward compatibility;
- добавить release notes для 1.0;
- сформировать список known limitations;
- определить поддержку Python versions;
- решить, какие optional extras официально поддерживаются в 1.0.

## Краткий Итог

`uniqdiff` уже сформирован как comparison engine для UniqTools.

Его сильная сторона:

- стабильное exact comparison ядро;
- понятный API;
- несколько backend-ов;
- out-of-core режимы;
- connector layer;
- lazy result reading;
- CLI для базовых сценариев;
- clear compatibility direction.

Главное архитектурное правило:

`uniqdiff` должен оставаться engine layer. Все продуктовые сценарии, отчеты, UI,
schema validation, profiling, data quality rules и orchestration должны строиться
поверх него в отдельных инструментах экосистемы UniqTools.
