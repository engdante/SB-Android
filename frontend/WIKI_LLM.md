 🧠 pi_sb — Wiki LLM Architecture

## Как работи Wiki LLM системата — от запис до търсене

Този документ описва **как** pi_sb съхранява информация и **как** я търси, както и **какви промени предлагам** за оптимизация.

---

## 1. Общ преглед на компонентите

```
┌─────────────────────────────────────────────────────────────┐
│                     API Endpoints                            │
│  POST /api/input/text          POST /api/search/wiki/ask     │
│  POST /api/input/audio         POST /api/search/ask (RAG)    │
└──────────┬──────────────────────────────────┬────────────────┘
           │                                  │
           ▼                                  ▼
┌──────────────────────┐         ┌──────────────────────────┐
│   ConceptProcessor    │         │      WikiRetriever        │
│   (processor.py)     │         │      (retriever.py)       │
│                      │         │                          │
│  1. save_source()    │         │  1. get_index_summary()   │
│  2. LLM generate     │         │  2. LLM explores indexes  │
│  3. validate OKF     │         │  3. keyword fallback       │
│  4. save_concept()   │         │  4. get_context_for_pages() │
│  5. indexer.regenerate│         │  5. ask_question()        │
└──────────┬───────────┘         └──────────┬───────────────┘
           │                                  │
           ▼                                  ▼
┌──────────────────────┐         ┌──────────────────────────┐
│     OkfStorage        │         │      WikiIndexer          │
│     (storage.py)     │         │      (indexer.py)         │
│                      │         │                          │
│  - save_source()     │         │  - regenerate_all()       │
│  - save_concept()    │         │  - _write_category_index  │
│  - read_concept()    │         │  - _write_tags_index      │
│  - get_all_concepts()│         │  - _write_date_index      │
│  - delete_concept()  │         │  - _write_full_index      │
│  - update_concept()  │         │  - _write_wiki_index      │
│  - update_index()    │         │  - log_event()            │
└──────────┬───────────┘         └──────────┬───────────────┘
           │                                  │
           ▼                                  ▼
    ┌─────────────────────────────────────────────┐
    │              Файлова система                │
    │                                           │
    │  data/                                    │
    │  ├── index.md        ← OKF §6 index       │
    │  ├── log.md          ← OKF §7 log         │
    │  ├── raw/YYYY/MM/    ← Source документи    │
    │  ├── YYYY/MM/        ← OKF концепции      │
    │  └── wiki/           ← Индекси            │
    │      ├── index.md                         │
    │      ├── INDEX_CATEGORIES.md              │
    │      ├── INDEX_TAGS.md                    │
    │      ├── INDEX_DATE.md                    │
    │      ├── INDEX_FULL.md                    │
    │      ├── LOG.md                           │
    │      └── concepts/       ← ⚠️ TODO         │
    └─────────────────────────────────────────────┘
```

---

## 2. Как се записват файлове (Pipeline Ingest)

### 2.1 Текстов Ingest

**Път:** `POST /api/input/text` → `processor.py` → `storage.py` → `indexer.py`

```
Потребителски текст
        │
        ▼
[1] save_source(text)
    └── записва raw текста в data/raw/YYYY/MM/YYYY-MM-DD_source_NNN.md
    └── файлът е само plain текст (без frontmatter)
    └── това е immutable запис — никога не се променя
        │
        ▼
[2] LLM generate (ingestion_client)
    └── prompt = text
    └── system_prompt = analysis_prompt.txt
    └── temperature = 0.3 (детерминиран)
    └── max_tokens = 4096
    └── LLM връща OKF markdown с frontmatter
        │
        ▼
[3] OkfDocument.from_markdown(response)
    └── парсва YAML frontmatter
    └── разделя на metadata + body
        │
        ▼
[4] _validate_conformance()
    └── проверява само type != ""
    └── логва warnings за липсващи title/description/tags
        │
        ▼
[5] Корекции
    └── timestamp = datetime.now(timezone.utc)  (замества LLM-измисленото)
    └── language = "bg"  (презаписва)
        │
        ▼
[6] storage.save_concept(document, source_path)
    └── добавя resource: raw/YYYY/MM/YYYY-MM-DD_source_NNN.md
    └── генерира filename: YYYY-MM-DD_type_NNN.md
    └── записва в data/YYYY/MM/
    └── invalid-ва кеша (_invalidate_cache)
        │
        ▼
[7] indexer.regenerate_all()
    └── вика 6 метода за писане на индекси (вкл. data/index.md)
    └── всеки метод сканира всички концепции отначало
        │
        ▼
[8] indexer.log_event()
    └── записва в wiki/LOG.md и data/log.md
```

### 2.2 Аудио Ingest

**Път:** `POST /api/input/audio` → `transcriber.py` → `postprocessor.py` → `processor.py`

```
Аудио файл (.webm, .mp3, .wav)
        │
        ▼
[1] Записва се в data/audio/{filename}
        │
        ▼
[2] AudioTranscriber.transcribe()
    └── избира engine според settings.audio_engine:
        ├── "local"  → faster-whisper (CTranslate2)
        ├── "remote" → whisper.cpp HTTP server
        └── "ollama" → Gemma 4 multimodal
    └── връща {"text": "...", "language": "bg", "segments": [...], "duration": 12.5}
        │
        ▼
[3] Regex пост-процесинг (postprocessor.py)
    └── _fix_split_words() — слепва разкъсани думи
        напр. "инструмент ите" → "инструментите"
    └── _fix_punctuation() — точки, запетаи, главни букви
        │
        ▼
[4] LLM пост-процесинг (postprocessor.py)
    └── изпраща текста на Ollama с temperature 0.1
    └── за подобряване на пунктуацията и слепване
    └── ако LLM не е наличен, продължава с regex резултата
        │
        ▼
[5] Продължава като Текстов Ingest (стъпки 1-8 отгоре)
```

### 2.3 Изтриване (Delete)

**Път:** `DELETE /api/search/concepts/{path}` → `storage.py` → `indexer.py`

```
[1] Прочети metadata (за log-ване)
[2] storage.delete_concept(path)
    └── filepath.unlink() — изтрива файла
    └── invalid-ва кеша (_invalidate_cache)
[3] indexer.regenerate_all()
    └── регенерира 6 индекса (вкл. data/index.md)
[4] indexer.log_event(event_type="delete")

⚠️ Source файловете в data/raw/ НЕ се изтриват
```

### 2.4 Обновяване (Update)

**Път:** `PUT /api/search/concepts/{path}` → `storage.py` → `indexer.py`

```
[1] Прочети съществуващия файл
[2] Презапиши с нови metadata и body (invalid-ва кеша)
[3] indexer.regenerate_all()
    └── регенерира 6 индекса (вкл. data/index.md)
[4] indexer.log_event(event_type="update")
```

---

## 3. Как се търси (Query Pipeline)

### 3.1 Index-based Q&A (основният метод)

**Път:** `POST /api/search/wiki/ask` → `retriever.py` → `processor.py`

```
Потребителски въпрос (напр. "Какво знам за ОВК?")
        │
        ▼
[0] Има ли концепции?
    └── storage.get_all_concepts() — сканира всички .md файлове
    └── Ако е празно → "нямаш създадени бележки"
        │
        ▼
[1] get_index_summary()
    └── чете INDEX_CATEGORIES.md, INDEX_TAGS.md, INDEX_DATE.md, INDEX_FULL.md
    └── връща preview (first 15 lines of each)
        │
        ▼
[2] LLM Exploration Prompt
    └── prompt: "Разгледай wiki индексите по-долу. На базата на въпроса
                 на потребителя, избери кои wiki страници трябва да се
                 прочетат за да се отговори."
    └── system prompt: "Ти си wiki навигатор. Връщаш само JSON масив."
    └── temperature: 0.1
    └── LLM връща: ["2026/06/2026-06-30_journal_001.md", ...]
        │
        ▼
[3] Парсване на JSON
    └── regex: \[.*?\]  → json.loads()
        │
        ▼
[4] LLM не избра нищо?
    └── Keyword Fallback
    └── взима първите 5 думи от въпроса
    └── търси ги в title, description, tags на всяка концепция
    └── (текстов match, не семантичен)
        │
        ▼
[5] Все още нищо?
    └── "Нямам информация за това в твоите бележки."
        │
        ▼
[6] get_context_for_pages(selected_paths, max_chars=8000)
    └── за всяка избрана страница:
        ├── чете пълния OKF файл от диска
        ├── добавя header с type, title, тагове
        └── добавя body-то
    └── спира при 8000 символа
        │
        ▼
[7] processor.ask_question(question, context)
    └── system_prompt = rag_prompt.txt с {context}
    └── prompt = question
    └── temperature = 0.3
    └── LLM връща отговор
        │
        ▼
[8] Ако отговорът е празен?
    └── Fallback: "Открих N страници, но не успях да генерирам отговор"
        │
        ▼
[9] Логване в LOG.md
```

### 3.2 Vector RAG (алтернативен метод)

**Път:** `POST /api/search/ask`

Използва ChromaDB + embeddings от Ollama (`generate_embedding()`). 
Не е напълно документиран в кода — съществува като endpoint, но логиката не е видима в `search.py`.

---

## 4. Структура на индексите

### Wiki Indexer генерира 5 файла:

| Индекс | Ниво | Съдържание | Примерен ред |
|---|---|---|---|
| `INDEX_CATEGORIES.md` | 0 | Таблица с категории и брой страници | `\| journal \| 5 \| Дневник \|` |
| `INDEX_TAGS.md` | 1 | За всеки таг, списък страници | `## #hvac (3 страници)`<br>`- [Title](path) \`type\`` |
| `INDEX_DATE.md` | 2 | Концепции групирани по дата | `## 2026-06-30 (2 страници)`<br>`- [Title](path) \`type\` #tag` |
| `INDEX_FULL.md` | 3 | Пълна таблица | `\| 1 \| [Title](path) \| type \| tags \| date \| path \|` |
| `index.md` | wiki | Категоризиран с resource линкове | `## journal (5 страници)`<br>`- [Title](path) #tag — [Source](raw/...)` |

---

## 5. Констатирани проблеми

### 5.1 Производителност

| Проблем | Описание | Тежест |
|---|---|---|
| **Пълно регенериране при всяка ingest** | `regenerate_all()` се вика при всяко добавяне/изтриване/обновяване. Пише 5 файла наново. | ⚠️ Високо |
| **get_all_concepts() сканира всички .md файлове** | Използва `data_dir.rglob("*.md")` всеки път. С 1000+ концепции ще стане бавно. | ⚠️ Средно |
| **get_all_documents() дублира логиката** | Има два метода с почти същата функционалност | 🔷 Ниско |
| **LLM exploration изпраща цели индекси** | `get_index_summary()` връща preview, но ако индексите са големи (100+ страници), LLM може да не ги обработи правилно | ⚠️ Средно |

### 5.2 Логически проблеми

| Проблем | Описание | Тежест |
|---|---|---|
| **get_context_for_pages() не проверява дали страниците съществуват** | Ако LLM върне несъществуващ път, `read_concept()` ще хвърли грешка, но тя се игнорира с `continue` | 🔷 Ниско |

### 5.3 Indexer проблеми

| Проблем | Описание | Тежест |
|---|---|---|
| **Няма incremental indexing** | Само пълно регенериране. Няма начин да добавиш само 1 нова концепция към индексите. | ⚠️ Високо |
| **Няма индекс за body съдържание** | Търсенето по ключови думи не покрива body-то на концепциите. | ⚠️ Средно |
| **Няма концептуални страници** | `data/wiki/concepts/` се създава, но не се пълни. | 🔷 Ниско (вестът е TODO) |

### 5.4 Lint проблеми

| Проблем | Описание | Тежест |
|---|---|---|
| **Lint проверява само 3 неща** | Орфан страници, untagged, no description. Липсват stale claims, missing cross-references. | 🔷 Ниско (вестът е TODO) |
| **Orphan detection зависи от markdown links** | Ако концепция линква към друга, но с абсолютен път или URL, няма да я отчете. | 🔷 Ниско |

---

## 6. Предложения за промени

### 6.1 Incremental Indexing (висок приоритет)

**Проблем:** `regenerate_all()` се вика при всяка ingest и регенерира 5 файла наново.

**Решение:** Добавяне на `add_concept_to_indexes(concept_path)`:

```python
# Текущо:
def regenerate_all(self):
    concepts = self.storage.get_all_concepts()  # сканира всички файлове
    self._write_category_index(concepts)
    self._write_tags_index(concepts)
    self._write_date_index(concepts)
    self._write_full_index(concepts)
    self._write_wiki_index(concepts)

# Предложение:
def regenerate_all(self):
    concepts = self.storage.get_all_concepts()
    self._write_category_index(concepts)
    self._write_tags_index(concepts)
    self._write_date_index(concepts)
    self._write_full_index(concepts)
    self._write_wiki_index(concepts)

def add_to_indexes(self, concept: dict):
    """Добавя 1 концепция към индексите без пълно регенериране."""
    # Чете съществуващите индекси и добавя новия entry
    # По-бързо от пълно регенериране
    pass

def remove_from_indexes(self, concept_path: str):
    """Премахва 1 концепция от индексите."""
    pass
```

**Полза:** При ingest само 1 запис се добавя вместо 5 файла да се пишат наново.

### 6.2 Lint подобрения (нисък приоритет, TODO)

**Проблем:** Lint проверява само 3 неща. Липсват stale claims, missing cross-references.

**Решение:** Добавяне на:
- **Stale claims** — сравняване на timestamp-ове в линкнати концепции. Ако концепция A реферира концепция B, но B е обновена след A, маркирай за преглед.
- **Broken links** — проверка дали всички `[text](path.md)` линкове сочат към съществуващи файлове.
- **Missing concept pages** — когато дадена концепция се споменава в 3+ OKF файла, предложи създаване на страница в `data/wiki/concepts/`.

### 6.7 LLM Exploration Prompt — подобрение (нисък приоритет)

**Проблем:** Index summary може да е твърде голям за малкия контекст на LLM-а.

**Решение:** Трънкиране на индексите до 10 реда всеки вместо 15, или превключване към стъпково exploration (първо категории, после тагове, после конкретни страници):

```
Стъпка 1: "Кои категории са релевантни?" → ["journal", "idea"]
Стъпка 2: "В тези категории, кои тагове?" → ["медитация", "спорт"]
Стъпка 3: "Кои страници?" → ["path/to/page1.md", ...]
```

---

## 7. Пътна карта за имплементация

| Приоритет | Промяна | Очаквано време |
|---|---|---|
| 🥇 Висок | Incremental indexing (6.1) | 2-3 часа |
| 🥉 Нисък | Lint подобрения (6.2) | 2-3 часа |
| 🥉 Нисък | LLM Exploration Prompt подобрение (6.7) | 1 час |

---

## 8. Текуща версия на Wiki LLM

| Компонент | Версия | Забележка |
|---|---|---|
| OKF формат | v0.1 (Google OKF) | OKF §1-11 |
| Indexer | v1.0 (multi-level) | 5 индекса, пълно регенериране |
| Retriever | v1.1 (index-based) | LLM exploration + keyword fallback с body търсене |
| Storage | v1.1 (file-based + cache) | In-memory кеш с invalidate при write |
| Vector RAG | v0.5 (ChromaDB) | Съществува, но не е напълно документиран |