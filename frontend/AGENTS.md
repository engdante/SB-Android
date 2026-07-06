# AGENTS.md — LLM Wiki Schema for pi_sb

Този файл инструктира LLM агента как да поддържа wiki-то на pi_sb (Second Brain).

## Архитектура (OKF v0.1 + LLM Wiki)

pi_sb следва официалния **OKF v0.1 стандарт на Google**:
https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

Структурата е OKF-conformant bundle с pi_sb extension директории.

```
data/
├── index.md                   # Коренов индекс (OKF §6 — без frontmatter)
├── log.md                     # Хронологичен лог (OKF §7 — ISO 8601 дати)
├── runtime_settings.json      # Runtime настройки — презаписват .env без рестарт
│
├── raw/                       # ⬅️ pi_sb extension — Source документи (immutable)
│   ├── index.md               # (опционално) Индекс на source-ите
│   ├── audio/                 # Аудио файлове (webm, mp3, etc.)
│   └── YYYY/MM/
│       └── YYYY-MM-DD_source_NNN.md   # Оригинален текст от чат/аудио
│
├── YYYY/MM/                   # OKF концепции (OKF §3 — произволни поддиректории)
│   └── YYYY-MM-DD_type_NNN.md        # Връзка към source чрез resource: поле
│
└── wiki/                      # ⬅️ pi_sb extension — Wiki индекси (LLM-генерирани)
    ├── index.md               # Категоризиран индекс по теми (с resource: линкове)
    ├── INDEX_CATEGORIES.md    # Ниво 0: категории
    ├── INDEX_TAGS.md          # Ниво 1: тагове
    ├── INDEX_DATE.md          # Ниво 2: хронологичен
    ├── INDEX_FULL.md          # Ниво 3: пълен списък
    ├── LOG.md                 # Хронологичен лог (синхронизиран с data/log.md)
    └── concepts/              # ⚠️ TODO — все още НЕ се пълни от кода
        └── *.md               # Кодът създава директорията, но не записва страници
```

## Формат на OKF файл (OKF v0.1 + pi_sb extensions)

Всеки файл започва с YAML frontmatter. Следва OKF §4.1:

```yaml
---
okf_version: "0.1"           # OKF §11 — bundle версия (задължително за pi_sb)
type: journal                # OKF §4.1 — ЕДИНСТВЕНОТО REQUIRED поле, свободен текст
title: Заглавие              # OKF §4.1 — Recommended (optional)
description: Кратко описание # OKF §4.1 — Recommended (optional)
tags: [таг1, таг2]           # OKF §4.1 — Optional
resource: raw/...            # OKF §4.1 — Optional, URI или път до source
id: a1b2c3d4                 # ⬅️ pi_sb extension (UUID[0:8])
language: bg                 # ⬅️ pi_sb extension
timestamp: 2026-06-30T10:00:00Z  # OKF §4.1 — Optional
---
```

**OKF §9 Conformance:** Единственото задължително поле е `type`. Всички останали полета са optional. Системата НЕ retry-ва при липсващи полета — само логва warning.

**pi_sb extensions:** `id` и `language` са producer-defined полета, позволени от OKF §4.1 "Extensions". Системата автоматично добавя `id` (UUID[0:8]) и презаписва `language` на `bg`.

**Важно:** Полето `resource:` сочи към оригиналния source текст в `data/raw/`, за да може да се сравни какво е казано в source-а и какво е анализирала концепцията. Може да бъде и външен URI (OKF §4.1).

## Prompts (LLM инструкции)

Системата използва два различни prompt файла:

| Prompt файл | Път | Употреба |
|---|---|---|
| Analysis prompt | `backend/app/config/prompts/analysis_prompt.txt` | При **Ingest** — анализ на текст и генериране на OKF |
| RAG prompt | `backend/app/config/prompts/rag_prompt.txt` | При **Query** — отговаряне на въпроси с контекст от wiki-то |
| Post-process prompt | (вграден в `postprocessor.py`) | При **Audio** — подобряване на транскрипция |

Агентът **не трябва** да променя тези файлове, но трябва да ги познава, защото те определят как LLM-ът обработва текста.

## LLM Manager (два клиента)

Системата поддържа **два отделни LLM клиента** с потенциално различни модели:

- **Ingestion клиент** — за анализ на текст и генериране на OKF. Използва model = `INGESTION_MODEL`.
- **RAG клиент** — за отговаряне на въпроси (Q&A). Използва model = `RAG_MODEL`.

Моделите могат да се сменят в runtime чрез `/api/llm/switch/ingestion` и `/api/llm/switch/rag` endpoints.

---

## Runtime Settings

`data/runtime_settings.json` съдържа настройки, които презаписват `.env` в runtime **без рестарт на сървъра**.

Поддържани полета: `ollama_host`, `ollama_model`, `ingestion_model`, `rag_model`, `audio_engine`, `audio_model`, `audio_host`, `debug_enabled`, `backend_url`.

Настройките се четат на живо (live), не изискват рестарт. Записват се от frontend-а през `/api/settings` endpoints.

---

## Debug Система

Debug системата (`backend/app/core/debug_logger.py`) записва структурирани JSON логове в `debug/` директорията (gitignored).

| Лог файл | Съдържание |
|---|---|
| `requests.log` | Всички HTTP заявки/отговори |
| `llm.log` | Всяка LLM заявка (prompt, response, duration) |
| `ingest.log` | Всички ingest операции |
| `queries.log` | Всички Query операции |
| `errors.log` | Грешки с пълен stack trace |
| `frontend.log` | Логове от frontend-а |
| `events.log` | Произволни събития |

**Как LLM агентът използва debug системата:**
- Логва грешки към `debug_logger.log_error()` при проблеми
- Логва LLM заявки (автоматично от `OllamaClient`)
- Може да чете логове през `/api/debug/logs/{filename}` за диагностика

---

## Работни потоци

### Ingest (добавяне на нова информация — текст)

1. **Запиши source-а** — оригиналният текст се записва в `data/raw/YYYY/MM/` (като `YYYY-MM-DD_source_NNN.md`)
2. **Прочети source документа** — LLM анализира source-а, използва `analysis_prompt.txt` като system prompt
3. **Генерирай OKF** — LLM връща анализ с `type`, `title`, `description`, `tags` и body
4. **Валидирай OKF §9 conformance** — кодът проверява само че `type` не е празно. Всички останали полета са optional — липсата им НЕ е грешка, само soft warning.
5. **Презапиши timestamp и language** — системата винаги презаписва `timestamp` с реално време и `language` на `bg`
6. **Запиши OKF файл** в `data/YYYY/MM/` с `resource:` поле сочещо към source-а
7. **Обнови wiki индексите** — `indexer.regenerate_all()` и `indexer.log_event()`

### Ingest (добавяне на нова информация — аудио)

1. **Качи аудио файла** — записва се в `data/audio/`
2. **Транскрибирай** — Whisper (faster-whisper, whisper.cpp server или Ollama multimodal)
3. **Пост-процесинг** — два етапа:
   - **Regex** — бързо слепване на разкъсани думи, пунктуация (напр. "инструмент ите" → "инструментите")
   - **LLM** — подобряване на пунктуацията и слепване (чрез Ollama, temperature 0.1)
4. **Продължи с Text Ingest (#2-7)** — транскрибираният текст се обработва като текстов вход

### Query (задаване на въпрос — RAG pipeline)

Системата поддържа **два паралелни Q&A метода**:

#### Метод 1: Index-based (без embeddings)
1. **Вземи резюме на индексите** — INDEX_CATEGORIES.md, INDEX_TAGS.md, INDEX_DATE.md
2. **LLM навигира индексите** — `exploration_prompt` кара LLM-а да избере кои страници са релевантни
3. **LLM връща JSON** — масив от пътища на релевантни страници
4. **Keyword fallback** — ако LLM не избере нищо, търси по ключови думи (заглавие, описание, тагове)
5. **Вземи контекст** — чете пълното съдържание на избраните страници (max 8000 символа)
6. **Генерирай отговор** — използва `rag_prompt.txt` с контекста
7. **Логвай** — всяка заявка се записва в LOG.md

#### Метод 2: Vector RAG (ChromaDB + embeddings)
Използва се чрез `/api/search/ask` endpoint с embeddings от Ollama. (Документация — в бъдеща версия.)

### Delete (изтриване на концепция)

1. **Прочети metadata** преди изтриване (за log-ване на заглавието)
2. **Изтрий файла** — `storage.delete_concept()`, премахва от файловата система
3. **Обнови wiki индексите** — `indexer.regenerate_all()`
4. **Логвай** — `indexer.log_event(event_type="delete", ...)`

**ВАЖНО:** Изтриването е необратимо. Source файловете в `data/raw/` НЕ се изтриват — те остават като immutable записи.

### Update (обновяване на концепция)

1. **Прочети съществуващия файл**
2. **Презапиши с нови metadata и body** — `storage.update_concept()`
3. **Обнови wiki индексите** — `indexer.regenerate_all()`
4. **Логвай** — `indexer.log_event(event_type="update", ...)`

### Export / Import / Clear (управление на данни)

- **Export** — `/api/data/export` — изтегля всички OKF .md файлове като ZIP
- **Import** — `/api/data/import` — качва ZIP, добавя нови файлове (не презаписва съществуващи)
- **Clear** — `/api/data/clear?confirm=true` — изтрива всички концепции, запазва LOG.md история

---

## Lint (периодична поддръжка)

Кодът поддържа следните lint проверки (чрез `/api/search/wiki/lint`):

- **Orphan pages** — страници без incoming links (без други страници, които линкват към тях)
- **Untagged pages** — страници без тагове
- **No description pages** — страници без описание

> [!info] AGENTS.md споменава също **stale claims**, **missing cross-references** и **липсващи concept страници**, но те все още **не са имплементирани в кода**. Това са TODO за бъдеща версия.

**Как да поддържаш качество:**
- След всеки ingest, провери дали новият OKF файл има **линкове към съществуващи концепции**: `[Име](path/to/file.md)`
- Ако забележиш концепция, която се споменава в 3+ OKF файла, **създай/обнови страница в `data/wiki/concepts/`** (ръчно, докато кодът не го прави автоматично)
- При съмнение за противоречие между източници, отбележи го с `> [!warning]`

---

## API Endpoints (които LLM агентът може да използва)

| Endpoint | Метод | Описание |
|---|---|---|
| `/api/input/text` | POST | Текстов ingest |
| `/api/input/audio` | POST | Аудио ingest |
| `/api/search/concepts` | GET | Списък концепции |
| `/api/search/concepts/{path}` | GET | Детайли за концепция |
| `/api/search/concepts/{path}` | DELETE | Изтриване |
| `/api/search/concepts/{path}` | PUT | Обновяване |
| `/api/search/wiki/ask` | POST | Index-based Q&A |
| `/api/search/wiki/reindex` | POST | Ръчно реиндексиране |
| `/api/search/wiki/lint` | POST | Lint проверка |
| `/api/search/wiki/log` | GET | Последни LOG.md entries |
| `/api/settings` | GET/POST | Runtime настройки |
| `/api/llm/models` | GET | Налични модели |
| `/api/llm/switch/ingestion` | POST | Смяна на ingest модел |
| `/api/llm/switch/rag` | POST | Смяна на RAG модел |
| `/api/llm/switch/audio` | POST | Смяна на audio engine |
| `/api/debug/logs/{file}` | GET | Четене на debug логове |
| `/api/data/export` | POST | Export ZIP |
| `/api/data/import` | POST | Import ZIP |

---

## Конвенции

- Използвай `[Title](relative/path.md)` за cross-references
- Добавяй минимум 2-3 тага на страница (препоръчително, не задължително)
- **Всичко (заглавие, описание, тагове, съдържание) е на български** без изключение. Дори source документът да е на английски, OKF файлът се създава на български.
- `language: bg` винаги — системата презаписва ако LLM върне друго
- Описанието трябва да е 1-2 изречения (препоръчително)
- `resource:` полето сочи към `data/raw/...` или външен URI — относителен път от `data/`
- `id:` полето се генерира автоматично от storage.py (UUID[0:8])
- `okf_version: "0.1"` се добавя автоматично от системата
- При съмнение за противоречие, отбележи го с `> [!warning]`
- Запиши добрите Q&A отговори като нови wiki страници
- Source файловете в `data/raw/` са immutable — LLM никога не ги променя, само чете
- Концептуалните страници в `data/wiki/concepts/` **е TODO** — кодът създава директорията, но не поддържа страниците автоматично

## Error Handling

**Какво прави системата при грешки:**

| Ситуация | Действие |
|---|---|
| LLM върне невалиден OKF (без `type`) | Fallback (note тип, без retry) |
| LLM върне OKF без title/description/tags | OK — всичко освен `type` е optional (OKF §9) |
| LLM timeout | Automatic retry (3 опита, exponential backoff) |
| LLM HTTP 5xx грешка | Automatic retry (3 опита с изчакване) |
| Невалиден YAML frontmatter | Fallback (note тип) |
| Празно wiki при Q&A | Насочващо съобщение "нямаш създадени бележки" |
| Няма релевантни страници при Q&A | Съобщение "нямам информация за това" |
| LLM върне празен RAG отговор | Fallback съобщение с брой открити страници |

**Викай `debug_logger.log_error()` винаги когато нещо неочаквано се случи.**