# 🧠 pi_sb — Android Port Plan

## Цел
Да накараме **pi_sb (Second Brain)** да работи на Android телефон, като **целият софтуер (backend + frontend + whisper.cpp) се изпълнява локално на телефона** чрез Termux. Ollama остава на домашния компютър (или се използват cloud модели).

---

## Архитектура

```
┌──────────────────────────────────────────────────┐
│                  Android Phone                    │
│                                                   │
│  ┌────────────────────────────────────────────┐   │
│  │            Termux (Linux среда)             │   │
│  │                                             │   │
│  │  ┌──────────────────────────────────────┐   │   │
│  │  │         Python Backend (FastAPI)      │   │   │
│  │  │  • app/main.py — сървър              │   │   │
│  │  │  • app/core/ — processor, storage    │   │   │
│  │  │  • app/llm/ — Ollama клиент          │   │   │
│  │  │  • app/audio/ — whisper.cpp клиент   │   │   │
│  │  │  • app/wiki/ — Wiki индекси          │   │   │
│  │  │  • app/api/ — REST endpoints         │   │   │
│  │  └──────────────┬───────────────────────┘   │   │
│  │                 │                            │   │
│  │  ┌──────────────▼───────────────────────┐   │   │
│  │  │    whisper.cpp (ARM64 компилиран)     │   │   │
│  │  │    • whisper-server за Android        │   │   │
│  │  │    • GGUF модел (ggml-medium.en-q5_0) │   │   │
│  │  └──────────────────────────────────────┘   │   │
│  │                                             │   │
│  │  ┌──────────────────────────────────────┐   │   │
│  │  │    ffmpeg (Android ARM64)             │   │   │
│  │  │    • Конвертира WebM → WAV           │   │   │
│  │  └──────────────────────────────────────┘   │   │
│  └────────────────────────────────────────────┘   │
│                                                   │
│  ┌────────────────────────────────────────────┐   │
│  │         Browser (Chrome/Firefox)            │   │
│  │  • PWA инсталиран на homescreen            │   │
│  │  • http://localhost:8000                   │   │
│  │  • React frontend (pre-built статика)      │   │
│  └────────────────────────────────────────────┘   │
│                                                   │
│  ┌────────────────────────────────────────────┐   │
│  │         Ollama (домашен компютър)           │   │
│  │  • http://192.168.1.100:11434              │   │
│  │  • Или cloud модели (Gemma, GPT, Claude)   │   │
│  └────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

---

## Фаза 1: PWA + Responsive UI (промени в текущия код)

### 1.1 PWA (Progressive Web App)
Добавяне на възможност frontend-ът да се "инсталира" на телефона като app.

| # | Файл | Промяна |
|---|------|---------|
| 1.1.1 | `frontend/public/manifest.json` | **Нов файл** — Web App Manifest с икони, име, тема, orientation |
| 1.1.2 | `frontend/public/sw.js` | **Нов файл** — Service Worker за кеширане и офлайн достъп |
| 1.1.3 | `frontend/public/icons/` | **Нова директория** — PWA икони (192x192, 512x512) |
| 1.1.4 | `frontend/index.html` | Добавяне на `<link rel="manifest">`, `<meta name="theme-color">`, iOS meta тагове |
| 1.1.5 | `frontend/vite.config.ts` | Добавяне на `vite-plugin-pwa` за автоматично генериране на service worker |

### 1.2 Responsive CSS
Адаптиране на UI-а за малки екрани (телефони).

| # | Файл | Промяна |
|---|------|---------|
| 1.2.1 | `frontend/src/styles.css` | Media queries за екрани < 768px и < 480px |
| 1.2.2 | `frontend/src/styles.css` | Touch-friendly бутони (min-height: 48px) |
| 1.2.3 | `frontend/src/styles.css` | Адаптивно позициониране на панелите |
| 1.2.4 | `frontend/src/styles.css` | Подобрено scroll поведение за мобилни |

### 1.3 CORS и мрежови настройки

| # | Файл | Промяна |
|---|------|---------|
| 1.3.1 | `backend/app/main.py` | CORS: `allow_origins=["*"]` за мобилни (или динамичен origin) |
| 1.3.2 | `frontend/src/api/client.ts` | Автоматично откриване на backend URL (window.location.host) |

### 1.4 Build конфигурация

| # | Файл | Промяна |
|---|------|---------|
| 1.4.1 | `frontend/build.bat` | Актуализиране за PWA build |
| 1.4.2 | `frontend/package.json` | Добавяне на `vite-plugin-pwa` dependency |

---

## Фаза 2: Termux инсталационен скрипт

### 2.1 Скрипт за автоматична инсталация

| # | Файл | Промяна |
|---|------|---------|
| 2.1.1 | `setup_android.sh` | **Нов файл** — главен инсталационен скрипт за Termux |

Скриптът ще изпълнява:

```
1. Актуализира Termux пакети (pkg update && pkg upgrade)
2. Инсталира базови пакети:
   - python, clang, make, cmake, git
   - ffmpeg
   - wget, curl
3. Създава проектна директория (~/pi_sb)
4. Клонира/копира проекта
5. Създава Python виртуална среда
6. Инсталира Python зависимости (pip install -r requirements.txt)
7. Компилира whisper.cpp за ARM64:
   - git clone https://github.com/ggerganov/whisper.cpp
   - make -j4 (ARM64 оптимизации)
   - Сваля GGUF модел (ggml-medium.en-q5_0.bin)
8. Създава .env файл с конфигурация
9. Създава start.sh скрипт за лесно стартиране
```

### 2.2 Стартиращ скрипт

| # | Файл | Промяна |
|---|------|---------|
| 2.2.1 | `start_android.sh` | **Нов файл** — скрипт за стартиране на всички компоненти |

```
1. Стартира whisper.cpp server (background)
2. Стартира FastAPI backend (uvicorn)
3. Показва URL за достъп
```

---

## Фаза 3: Адаптации на backend кода за Android

### 3.1 Audio Transcoder (whisper.cpp за Android)

| # | Файл | Промяна |
|---|------|---------|
| 3.1.1 | `backend/app/audio/transcriber.py` | Добавяне на `WhisperCppEngineAndroid` клас (или параметър за OS) |
| 3.1.2 | `backend/app/audio/transcriber.py` | Различен път до whisper-server (Termux: `~/whisper.cpp/build/bin/whisper-server`) |
| 3.1.3 | `backend/app/audio/transcriber.py` | Различни флагове за Android (без `CREATE_NO_WINDOW`) |
| 3.1.4 | `backend/app/audio/transcriber.py` | ffmpeg път за Android (`/data/data/com.termux/files/usr/bin/ffmpeg`) |

### 3.2 Path resolution

| # | Файл | Промяна |
|---|------|---------|
| 3.2.1 | `backend/app/config/settings.py` | Добавяне на `is_android` проверка |
| 3.2.2 | `backend/app/config/settings.py` | Android base path: `~/pi_sb/` |
| 3.2.3 | `backend/app/config/settings.py` | Data директория: `~/pi_sb/data/` |

### 3.3 OS-специфични проверки

| # | Файл | Промяна |
|---|------|---------|
| 3.3.1 | `backend/app/audio/transcriber.py` | Замяна на `subprocess.CREATE_NO_WINDOW` (Windows-specific) |
| 3.3.2 | `backend/app/audio/transcriber.py` | Проверка за `sys.platform` при избор на executable |

---

## Фаза 4: Тестване

### 4.1 Компонентни тестове

| # | Тест | Описание |
|---|------|----------|
| 4.1.1 | Backend стартиране | `uvicorn app.main:app` — без грешки |
| 4.1.2 | whisper.cpp стартиране | `whisper-server` — без грешки |
| 4.1.3 | ffmpeg конвертиране | `ffmpeg -i test.webm test.wav` — без грешки |
| 4.1.4 | PWA инсталация | Добавяне на homescreen |

### 4.2 Функционални тестове

| # | Тест | Описание |
|---|------|----------|
| 4.2.1 | Текстов вход | Въвеждане на текст → OKF запис |
| 4.2.2 | Аудио запис | Запис от микрофон → транскрипция → OKF |
| 4.2.3 | Аудио файл | Качване на файл → транскрипция → OKF |
| 4.2.4 | RAG чат | Въпрос → отговор от wiki |
| 4.2.5 | Настройки | Промяна на Ollama host, модел |
| 4.2.6 | Експорт/Импорт | ZIP експорт и импорт на данни |

---

## Файлове, които НЕ се променят

Тези файлове работят без промяна на Android (чист Python, без OS-специфични зависимости):

- `backend/app/core/processor.py` — LLM pipeline
- `backend/app/core/storage.py` — файлово хранилище
- `backend/app/core/debug_logger.py` — debug система
- `backend/app/llm/ollama_client.py` — HTTP клиент за Ollama
- `backend/app/llm/llm_manager.py` — мениджър на модели
- `backend/app/wiki/indexer.py` — Wiki индекси
- `backend/app/wiki/retriever.py` — Wiki търсене
- `backend/app/config/concept_types.py` — типове концепции
- `backend/app/config/okf_schema.py` — OKF схема
- `backend/app/api/*.py` — API endpoints (всички)
- `frontend/src/components/*.tsx` — React компоненти (само CSS промени)
- `frontend/src/App.tsx` — главен компонент
- `frontend/src/main.tsx` — entry point

---

## Зависимости за Android (Termux)

### Python пакети (от requirements.txt)
- fastapi, uvicorn, python-multipart
- pydantic, pydantic-settings, python-dotenv
- httpx
- loguru, pyyaml

### Системни пакети (pkg install)
- `python` (3.10+)
- `clang` — за компилиране
- `make`, `cmake` — за компилиране
- `git` — за клониране на whisper.cpp
- `ffmpeg` — за аудио конвертиране
- `wget` — за сваляне на модели

### Компилирани компоненти
- `whisper.cpp` (ARM64) — от изходен код
- GGUF модел (ggml-medium.en-q5_0.bin) — ~539MB

---

## Очаквани предизвикателства

| # | Проблем | Решение |
|---|---------|---------|
| 1 | whisper.cpp компилация за ARM64 | `make -j4` с ARM64 флагове (Termux поддържа) |
| 2 | Памет за whisper модел (~3GB) | Използване на Q5_0 квантизация (по-малък модел) |
| 3 | Батерия при продължителна употреба | Оптимизации, background service |
| 4 | Termux заспиване в background | `termux-wake-lock` |
| 5 | Ollama не е на телефона | Използване на cloud модели или домашен сървър |
| 6 | Файлова система (Android storage) | Termux има собствена ~/ директория |

---

## Времева оценка

| Фаза | Описание | Очаквано време |
|------|----------|----------------|
| 1 | PWA + Responsive UI | 2-3 часа |
| 2 | Termux скрипт | 2-3 часа |
| 3 | Backend адаптации | 1-2 часа |
| 4 | Тестване | 1-2 часа |
| **Общо** | | **6-10 часа** |

---

## Как да тестваме без телефон

Докато подготвяме всичко, можем да тестваме PWA промените на Windows:
1. `cd frontend && npm install && npm run build`
2. `cd backend && python -m app.main`
3. Отваряме `http://localhost:8000` в Chrome
4. Chrome DevTools → Toggle Device Toolbar → избираме телефон
5. Тестваме responsive дизайн и PWA функционалност

---

## Следващи стъпки

1. ✅ Избран вариант: **Вариант A (Python + React, Termux)**
2. ⬜ Създаден план: **ANDROID_PLAN.md** ✅
3. ⬜ Преминаване към ACT MODE за имплементация
4. ⬜ Фаза 1: PWA + Responsive UI
5. ⬜ Фаза 2: Termux скрипт
6. ⬜ Фаза 3: Backend адаптации
7. ⬜ Фаза 4: Тестване