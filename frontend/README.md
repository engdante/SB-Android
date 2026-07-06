# 🧠 pi_sb — Second Brain

**100% локална, поверителна Second Brain система.**

Приема текст и глас, анализира ги с локален LLM (Ollama), структурира ги в OKF (Open Knowledge Format) и позволява RAG търсене.

---

## 📋 Изисквания

- **Python 3.10+**
- **Node.js 18+**
- **Ollama** — на същата машина или в мрежата (напр. `http://192.168.1.100:11434`)
- **AMD ROCm** (опционално) — за GPU ускорение на Ollama

---

## 🚀 Бърз старт

### 1. Ollama

```bash
# Инсталирай Ollama: https://ollama.com/
# Свали базов модел:
ollama pull llama3
# Или за по-бърз:
ollama pull mistral
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

Редактирай `.env`:
```env
OLLAMA_HOST=http://192.168.1.100:11434   # IP на Ollama сървъра
OLLAMA_MODEL=llama3
OKF_DATA_DIR=./data                       # OKF хранилище
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev    # Dev сървър на localhost:5173
```

### 4. Старт

```bash
# Терминал 1: Backend
cd backend
python -m app.main
# → http://localhost:8000

# Терминал 2: Frontend (dev)
cd frontend
npm run dev
# → http://localhost:5173

# Production: Frontend се serve-ва от Backend
cd frontend && npm run build
# → http://localhost:8000
```

---

## 📂 Структура на проекта

```
pi_sb/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── config/           # Settings, OKF schema, prompts
│   │   ├── api/              # REST endpoints
│   │   ├── core/             # Processor, Storage
│   │   ├── llm/              # Ollama клиент
│   │   ├── audio/            # Whisper транскрипция
│   │   └── rag/              # RAG: embeddings, ChromaDB, retriever
│   ├── .env                  # Конфигурация
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/       # TextInput, AudioRecorder, ConceptList, ChatInterface
│   │   ├── api/client.ts     # API клиент
│   │   ├── App.tsx
│   │   └── styles.css
│   ├── package.json
│   └── vite.config.ts
├── data/                      # OKF хранилище (Second Brain)
├── railway.json               # Railway конфиг
└── README.md
```

---

## 🔌 API Endpoints

| Метод | Път | Описание |
|-------|-----|----------|
| GET | `/` | Основен (app status) |
| GET | `/api/health` | Здравен статус + LLM check |
| POST | `/api/input/text` | Добавяне на текст |
| POST | `/api/input/audio` | Качване на аудио |
| GET | `/api/search/concepts` | Списък концепции (с филтри) |
| GET | `/api/search/concepts/{path}` | Детайли за концепция |
| POST | `/api/search/ask` | RAG Q&A въпрос |

---

## 🧠 OKF (Open Knowledge Format)

OKF файловете се записват в `data/YYYY/MM/` с формат:
```
---
type: idea|note|project|task|journal|...
title: Заглавие
description: Кратко описание
tags: [таг1, таг2]
language: bg|en
timestamp: 2026-06-30T10:00:00Z
---

Съдържание в Markdown...
```

---

## 🚢 Деплой в Railway

```bash
# 1. Инсталирай Railway CLI
# 2. Създай проект в Railway dashboard
# 3. Свържи GitHub репо
# 4. Конфигурирай environment variables:
#    - OLLAMA_HOST (не може локален, трябва да е remote)
#    - OLLAMA_MODEL
```

---

## 🛣️ Пътна карта

- [x] Backend Core (FastAPI + Ollama + OKF Storage)
- [x] RAG система (ChromaDB + Embeddings)
- [x] Аудио обработка (Whisper)
- [x] React Frontend (TextInput, AudioRecorder, ConceptList, Chat)
- [x] Railway конфигурация
- [ ] Автоматично индексиране при старт
- [ ] CLI инструмент
- [ ] Docker контейнеризация
- [ ] Мобилна версия

---

## 🔒 Поверителност

**Zero telemetry. 100% offline възможност.**
- Няма външни API извиквания
- Всички данни са на локалната файлова система
- LLM инференс през локален/локален мрежов Ollama

---

<p align="center">Създадено с 🧠 от инженер за инженери</p>