# 🧠 pi_sb — Second Brain: Дизайн и Архитектурни Решения

## Какво е pi_sb?

pi_sb е **100% локална, поверителна Second Brain система**. Тя приема текст и глас, анализира ги с локален LLM (Ollama), структурира ги и позволява RAG търсене.

Този документ описва **защо** всяко решение е взето по този начин — за да може в бъдеще да се разбере идеята зад системата.

---

## 1. Формат на данните — OKF (Open Knowledge Format)

### Източник
**Google OKF v0.1 SPEC**: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

### Защо OKF, а не собствен формат?
- OKF е **open standard** — не сме обвързани с един доставчик
- Можем да **импортираме външни OKF bundles** от Google и други организации
- Данните ни са **преносими** — можем да ги споделяме с други OKF-съвместими системи
- Форматът е **минимален** — Markdown + YAML frontmatter, нищо сложно

### Кои части от OKF стандарта следваме?

| OKF § | Изискване | pi_sb имплементация |
|---|---|---|
| §3 | Bundle структура — произволни поддиректории | `data/YYYY/MM/` — организирани по дата |
| §4.1 | Frontmatter: `type` е REQUIRED | `type: str` — задължително |
| §4.1 | `title`, `description`, `resource`, `tags`, `timestamp` са Optional | Всички са Optional в кода, но prompt-ът ги препоръчва |
| §4.1 | Extensions: producer-defined полета | `id:` и `language:` са pi_sb extensions |
| §5 | Cross-linking: `[Title](relative/path.md)` | Използваме OKF §5.2 relative links |
| §6 | `index.md` без frontmatter, `[Title](path) - description` | `data/index.md` следва този формат |
| §7 | `log.md` с ISO 8601 дати, `**Action**: description` | `data/log.md` и `wiki/LOG.md` следват този формат |
| §9 | Conformance: само `type` е задължително | `processor.py` проверява само `type` |
| §11 | Versioning: `okf_version: "0.1"` | Във всеки OKF файл |

### Какво добавяме ние (pi_sb extensions)?

Позволени от OKF §4.1 "Extensions":

| Поле | Описание | Защо го добавяме |
|---|---|---|
| `id` | UUID[0:8] | За уникална идентификация на концепция, независимо от filename |
| `language` | `bg` (по подразбиране) | Цялата wiki е на български — гарантираме консистентност |

### Какво имаме допълнително (извън OKF стандарта)?

Тези структури НЕ нарушават OKF — те са просто допълнителни директории в bundle-а:

| Директория | Описание | Защо |
|---|---|---|
| `data/raw/` | Source документи (immutable) | Да можем да видим какво е казано в оригиналния текст vs какво е анализирал LLM-ът |
| `data/wiki/` | Wiki индекси | LLM-генерирани индекси за по-бързо търсене без embeddings |
| `data/wiki/concepts/` | Концептуални страници | ⚠️ TODO — все още не се пълни от кода |

---

## 2. LLM интеграция

### Два клиента (LLM Manager)

За разлика от типичните RAG системи, pi_sb използва **два отделни LLM клиента**:

| Клиент | Модел (по подразбиране) | Употреба |
|---|---|---|
| **Ingestion** | `gemma4:cloud` | Анализ на текст и генериране на OKF |
| **RAG** | `qwen3.5:9b` | Отговаряне на въпроси с контекст от wiki-то |

**Защо два клиента?**
- Ingestion моделът може да е по-умен (по-бавен), защото се използва веднъж при запис
- RAG моделът може да е по-бърз, защото се използва при всяко запитване
- Могат да са на различни хостове (локален Ollama + cloud)

### Моделите могат да се сменят в runtime

Чрез `/api/llm/switch/ingestion` и `/api/llm/switch/rag` без рестарт на сървъра.

### Prompt файлове

| Файл | Употреба |
|---|---|
| `backend/app/config/prompts/analysis_prompt.txt` | System prompt за Ingestion клиента — инструктира LLM-а как да генерира OKF |
| `backend/app/config/prompts/rag_prompt.txt` | System prompt за RAG клиента — инструктира LLM-а как да отговаря на въпроси |

**Тези файлове НЕ трябва да се променят от LLM агента**, защото определят как LLM-ът обработва текста.

---

## 3. Валидация на OKF

### Първоначален подход (преди OKF v0.1 conformance)

Валидацията беше **строга**:
- 7 проверки (title, description, tags, body, overlap, не-fallback)
- При неуспех — retry с temperature 0.5
- При втори неуспех — fallback

**Проблем:** Това нарушаваше OKF §9, който казва че само `type` е задължително.

### Текущ подход (след OKF v0.1 conformance)

Валидацията е **мека** (OKF §9):
- Само `type` не е празно
- Липсващите полета (title, description, tags) се логват като warnings, не грешки
- Няма retry при липсващи полета

**Защо?** Защото OKF стандарта казва:
> Consumers MUST NOT reject a bundle because of:
> - Missing optional frontmatter fields
> - Unknown `type` values
> - Unknown additional frontmatter keys

---

## 4. Работни потоци

### Ingest (текст)
1. Source текстът се записва в `data/raw/` — **преди** LLM анализа
2. LLM анализира source-а и генерира OKF
3. OKF се валидира (само `type`)
4. OKF се записва в `data/YYYY/MM/` с `resource:` поле към source-а

**Защо source-ът се записва преди анализа?** За да можем да сравним оригиналния текст с анализираната концепция.

### Ingest (аудио)
1. Аудио файлът се записва в `data/audio/`
2. Whisper транскрибира (faster-whisper, whisper.cpp server или Ollama multimodal)
3. Пост-процесинг:
   - Regex: слепване на разкъсани думи ("инструмент ите" → "инструментите")
   - LLM: подобряване на пунктуацията (temperature 0.1)
4. Продължава като текстов ingest

**Защо два етапа на пост-процесинг?** Regex е бърз и покрива 90% от случаите. LLM покрива останалите 10% (смислови корекции).

### Query (Q&A)
- **Метод 1: Index-based** — LLM навигира индексите (без embeddings). По-бърз, но по-ограничен.
- **Метод 2: Vector RAG** — ChromaDB + embeddings. По-точен, но изисква повече ресурси.

**Защо два метода?** Index-based работи веднага (без embeddings), Vector RAG е по-точен за complex queries.

---

## 5. Runtime настройки

`data/runtime_settings.json` презаписва `.env` в runtime **без рестарт на сървъра**.

**Защо?** За да може frontend-ът да сменя настройките (Ollama host, модел, audio engine) без да рестартира backend-а.

Поддържани полета: `ollama_host`, `ollama_model`, `ingestion_model`, `rag_model`, `audio_engine`, `audio_model`, `audio_host`, `debug_enabled`, `backend_url`.

---

## 6. Debug система

`backend/app/core/debug_logger.py` записва структурирани JSON логове в `debug/` директорията (gitignored).

**Защо отделна debug система, а не само loguru?**
- Можем да четем логовете през `/api/debug/logs/{filename}` от frontend-а
- Логовете са структурирани (JSON), а не plain text
- Може да се включва/изключва runtime
- Всеки тип лог е в отделен файл (requests, llm, ingest, queries, errors, frontend, events)

---

## 7. Изтриване (Delete)

**Правила:**
- Изтриването е **необратимо**
- Source файловете в `data/raw/` **НЕ се изтриват** — те са immutable
- Wiki индексите се регенерират
- Събитието се логва в LOG.md

**Защо source-ът не се изтрива?** Защото source файловете са "източник на истината" — дори да изтрием концепцията, оригиналният текст остава за исторически справки.

---

## 8. TODO (бъдещи имплементации)

### В кода

| Функционалност | Статус | Описание |
|---|---|---|
| `concepts/` страници | ⚠️ Неимплементирано | Когато концепция се среща в 3+ OKF файла, трябва да има постоянна страница в `data/wiki/concepts/` |
| Stale claims lint | ⚠️ Неимплементирано | Проверка за информация, която по-нови източници опровергават |
| Missing cross-references lint | ⚠️ Неимплементирано | Концепции, които се споменават но не са линкнати |
| Bi-directional backlinks | ⚠️ Неимплементирано | `Backlinks:` секция в концепциите |

### В AGENTS.md

Тези липсващи функционалности са документирани в AGENTS.md с `> [!info]` бележка, за да не объркват LLM агента.

---

## 9. Ключови източници

| Източник | Какво дава |
|---|---|
| https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md | OKF v0.1 стандарт — формат на данните |
| https://ollama.com/ | Локален LLM за анализ и RAG |
| https://github.com/openai/whisper (faster-whisper) | Аудио транскрипция |
| https://github.com/ggerganov/whisper.cpp | Алтернативен whisper engine (по-бърз) |
| https://www.trychroma.com/ | Vector DB за embedding-based RAG |

---

## 10. Версия

Текуща OKF версия: **0.1** (следва Google OKF v0.1)

Предишна версия (до 2026-07-02): "OKF with enum types" — несъвместима с Google OKF.