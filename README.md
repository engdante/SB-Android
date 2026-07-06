<div align="center">
  <h1>🧠 pi_sb — Second Brain</h1>
  <p><strong>A local, privacy-first knowledge capture and retrieval system</strong></p>
  <p>
    <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/react-18%2B-61dafb" alt="React 18+">
    <img src="https://img.shields.io/badge/FastAPI-0.115-009688" alt="FastAPI">
    <img src="https://img.shields.io/badge/PWA-ready-purple" alt="PWA Ready">
    <img src="https://img.shields.io/badge/Android-Termux-brightgreen" alt="Android Termux">
  </p>
</div>

---

**pi_sb** (Second Brain) is a complete system for capturing, organizing, and retrieving your knowledge — all running locally on your machine or Android phone. It accepts text and voice input, processes them with an LLM (Ollama, local or cloud), structures them into **OKF (Open Knowledge Format)** files, and enables powerful RAG (Retrieval-Augmented Generation) search.

## ✨ Features

- **📝 Text Input** — Write notes, ideas, journal entries, tasks, and projects. Everything is analyzed and structured by an LLM.
- **🎤 Audio Input** — Record voice notes or upload audio files. Automatic transcription via **whisper.cpp** (local).
- **🤖 LLM Processing** — Powered by **Ollama** (local or cloud). Supports any Ollama-compatible model.
- **📂 OKF Storage** — All knowledge is saved as structured Markdown files in the **Open Knowledge Format** — human-readable, no lock-in.
- **🔍 RAG Search** — Ask questions and get answers based on your stored knowledge. Semantic search powered by ChromaDB embeddings.
- **📱 PWA Ready** — Installable as a Progressive Web App on your phone's homescreen. Works offline.
- **🤖 Android Support** — Full installation script for **Termux**. Backend + whisper.cpp run natively on ARM64.
- **🔒 100% Private** — Zero telemetry. All data stays on your device. No external API calls (unless you choose cloud models).
- **⚙️ Runtime Settings** — Change models, hosts, and API keys on-the-fly from the UI without server restart.

---

## 📱 Android Setup (Termux)

pi_sb runs natively on Android via **Termux**. All components (backend, whisper.cpp, ffmpeg) execute locally on the phone — no root required. Only the LLM (Ollama) runs on your home PC or uses cloud models.

### Prerequisites

1. **Install Termux** from [F-Droid](https://f-droid.org/en/packages/com.termux/) (NOT Google Play — it's outdated)
2. **Install git** in Termux:
   ```bash
   pkg install git -y
   ```
3. **Clone the project**:
   ```bash
   git clone https://github.com/yourusername/pi_sb.git
   cd pi_sb
   ```

### Automated Installation (setup_android.sh)

The main installation script `backend/setup_android.sh` handles everything automatically:

```bash
# Run from the project root
bash backend/setup_android.sh
```

#### What the script does:

| Step | Description |
|------|-------------|
| **1. System packages** | Installs python, clang, make, cmake, git, ffmpeg, wget, curl, ninja, rust |
| **2. Python version check** | Detects Python version — if 3.14+ (common on Termux ARM64), falls back to python3.12/3.11 or uses unpinned pydantic workaround |
| **3. Project directory** | Creates `~/pi_sb/` with data subdirectories (`data/`, `data/audio/`, `data/raw/`, `data/wiki/concepts/`) |
| **4. Python virtual environment** | Creates a venv at `backend/venv/` and installs all Python dependencies (FastAPI, uvicorn, httpx, loguru, etc.) |
| **5. `.env` file** | Creates a default `.env` with Android-friendly settings. **You must edit OLLAMA_HOST** to point to your PC |
| **6. whisper.cpp compilation** | Clones whisper.cpp from GitHub, compiles it for **ARM64** with architecture optimizations (`-march=armv8-a+crypto -O3`), disables x86-specific flags |
| **7. Whisper model download** | Downloads `ggml-large-v3-q5_0.bin` (~3GB) from HuggingFace — the audio transcription model |
| **8. Frontend build** | If Node.js is available on the phone, it runs `npm install && npm run build` in the frontend directory |
| **9. Start script** | Creates `start_pi_sb.sh` — a convenient launcher for all components |

> **Note:** If Node.js is not available on your phone, build the frontend on a PC:
> ```bash
> cd frontend && npm install && npm run build
> ```
> Then copy the `frontend/dist/` folder to `~/pi_sb/frontend/dist/` on your phone.

### Starting pi_sb on Android

After the setup script completes, start the system:

```bash
cd ~/pi_sb
bash start_pi_sb.sh
```

The start script:
1. Acquires a **wake lock** (`termux-wake-lock`) to prevent the phone from sleeping
2. Starts **whisper.cpp server** on port 8080 (background)
3. Starts **FastAPI backend** on port 8000
4. Shows the URL: **http://localhost:8000**
5. Press **Ctrl+C** to stop everything gracefully

#### Start script features:
- **PID tracking** — saves process IDs to `whisper.pid` and `backend.pid` for clean shutdown
- **Signal handling** — catches `SIGINT`/`SIGTERM` to kill all processes and release wake lock
- **Termux-specific** — no Windows `CREATE_NO_WINDOW` flag, proper Android executable paths

### First Run Configuration

1. **Edit `.env`** to set your Ollama host:
   ```bash
   nano ~/pi_sb/.env
   ```
   Set `OLLAMA_HOST` to your PC's local IP (e.g., `http://192.168.1.100:11434`)

2. **Open the app** in your browser: `http://localhost:8000`

3. **Install as PWA** — from the browser menu, select "Add to Home Screen" for an app-like experience

### Architecture (Android)

```
┌─────────────────────────────────────────────┐
│              Android Phone                   │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │          Termux (Linux)              │   │
│  │  • Python Backend (FastAPI)         │   │
│  │  • whisper.cpp (ARM64)              │   │
│  │  • ffmpeg (audio conversion)        │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  Browser (PWA)                      │   │
│  │  • http://localhost:8000            │   │
│  │  • Installable on homescreen       │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  Ollama (on home PC or cloud)       │   │
│  │  • http://192.168.1.100:11434       │   │
│  │  • Or cloud models (Gemma, etc.)    │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

## 🏗️ Architecture (Desktop)

```
┌───────────────────────────────────────────────────────┐
│                     Browser (PWA)                      │
│  ┌─────────────────────────────────────────────────┐  │
│  │              React Frontend                      │  │
│  │  • Text Input        • Audio Recorder           │  │
│  │  • Concept List      • Chat/RAG Interface        │  │
│  │  • Settings Panel    • Debug Console             │  │
│  └──────────────────────┬──────────────────────────┘  │
│                         │ HTTP (REST API)              │
└─────────────────────────┼──────────────────────────────┘
                          │
┌─────────────────────────▼──────────────────────────────┐
│                 FastAPI Backend (Python)                │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Input Pipeline                                   │  │
│  │  • /api/input/text  → LLM processing → OKF save  │  │
│  │  • /api/input/audio → whisper.cpp → LLM → OKF    │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  RAG Pipeline                                     │  │
│  │  • ChromaDB embeddings → Semantic search          │  │
│  │  • Wiki indexer → Full-text + tag search          │  │
│  │  • LLM answer generation (context + question)     │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Audio Engine (whisper.cpp)                       │  │
│  │  • Local transcription (GGUF model)               │  │
│  │  • WebM → WAV via ffmpeg                          │  │
│  └──────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (Ollama API)
┌──────────────────────▼──────────────────────────────────┐
│           Ollama (Local or Cloud)                        │
│  • Local: http://192.168.1.100:11434                    │
│  • Cloud: https://api.ollama.com                        │
│  • Any Ollama-compatible model (Gemma, Llama, Qwen...)  │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start (Desktop)

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for frontend development)
- **Ollama** — [Install Ollama](https://ollama.com/)

### 1. Clone & Setup

```bash
git clone https://github.com/yourusername/pi_sb.git
cd pi_sb

# Backend
cd backend
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows
pip install -r requirements.txt
cd ..
```

### 2. Configure .env

Copy the example file and edit it:

```bash
cp .env.example .env
```

At minimum, set your Ollama host and ingestion model:

```env
OLLAMA_HOST=http://192.168.1.100:11434
INGESTION_MODEL=llama3
```

### 3. Start the Backend

```bash
cd backend
python -m app.main
# → http://localhost:8000
```

### 4. Start the Frontend (Development)

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

For production, build the frontend and it will be served by the backend:

```bash
cd frontend && npm run build
# → http://localhost:8000 (backend serves the built frontend)
```

## ⚙️ Configuration

All configuration is managed through the `.env` file in the project root. The backend reads it at startup and applies runtime overrides from `data/runtime_settings.json`.

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://192.168.1.100:11434` | Ollama server URL (local or cloud) |
| `OLLAMA_API_KEY` | `""` | API key for Ollama cloud (sent as Bearer token) |
| `BACKEND_URL` | `http://localhost:8000` | Backend URL (for frontend to connect) |
| `CLOUD_MODELS` | `[]` | JSON array of cloud model names (e.g., `["gemma4:cloud"]`) |
| `INGESTION_MODEL` | `gemma4:cloud` | Model used for processing and saving notes |
| `RAG_MODEL` | `gemma4:cloud` | Model used for answering RAG questions |
| `AUDIO_MODEL` | `ggml-large-v3-q5_0.bin` | Whisper.cpp GGUF model for audio transcription |
| `AUDIO_UPLOAD_DIR` | `./data/audio` | Directory for uploaded audio files |
| `OKF_DATA_DIR` | `./data` | Directory for OKF knowledge storage |
| `DEBUG_ENABLED` | `true` | Enable debug request/response logging |
| `DEBUG` | `true` | Enable uvicorn auto-reload (requires restart) |
| `APP_NAME` | `pi_sb` | Application name |
| `APP_VERSION` | `1.0.0` | Application version |

> Some settings can be changed at runtime from the Settings panel in the UI (no server restart needed). Others (like `CLOUD_MODELS`, `DEBUG`, `OKF_DATA_DIR`) require a restart.

## 📡 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | System health check + LLM connectivity status |
| POST | `/api/input/text` | Submit text input (processed by LLM, saved as OKF) |
| POST | `/api/input/audio` | Upload audio file (transcribed + processed) |
| GET | `/api/search/concepts` | List all concepts with optional filters (type, tag, date) |
| GET | `/api/search/concepts/{path}` | Get details of a specific concept |
| POST | `/api/search/ask` | RAG question answering (search + LLM answer) |
| GET | `/api/settings` | Get current settings |
| PUT | `/api/settings` | Update runtime settings |
| GET | `/api/debug/logs` | Get debug logs |
| DELETE | `/api/debug/logs` | Clear debug logs |
| GET | `/api/data/export` | Export all data as ZIP |
| POST | `/api/data/import` | Import data from ZIP |
| POST | `/api/llm/chat` | Direct LLM chat (no context) |
| POST | `/api/llm/models` | List available models from Ollama |

## 📂 OKF (Open Knowledge Format)

All knowledge is stored as Markdown files with YAML front matter in the `data/YYYY/MM/` directory structure.

```yaml
---
type: idea          # one of: idea, note, project, task, journal, concept, reference, quote
title: My Note Title
description: A brief summary of the note
tags: [tag1, tag2]
language: en        # or bg, etc.
timestamp: 2026-06-30T10:00:00Z
---

# My Note Title

Content in full Markdown...

- Bullet points
- Code blocks
- Links and references
```

### Concept Types

| Type | Description |
|------|-------------|
| `idea` | Creative ideas and inspirations |
| `note` | General notes |
| `project` | Project documentation |
| `task` | Tasks and todos |
| `journal` | Daily journal entries |
| `concept` | Definitions and explanations |
| `reference` | Reference materials |
| `quote` | Quotes and citations |

## 📁 Project Structure

```
pi_sb/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── config/
│   │   │   ├── settings.py         # .env configuration manager
│   │   │   ├── concept_types.py    # OKF concept type definitions
│   │   │   └── okf_schema.py       # OKF YAML schema
│   │   ├── api/
│   │   │   ├── input.py            # Text & audio input endpoints
│   │   │   ├── search.py           # Concept search & RAG endpoints
│   │   │   ├── settings.py         # Settings management endpoints
│   │   │   ├── debug.py            # Debug log endpoints
│   │   │   ├── data.py             # Export/import endpoints
│   │   │   └── llm_router.py       # LLM chat & model listing
│   │   ├── core/
│   │   │   ├── processor.py        # LLM processing pipeline
│   │   │   ├── storage.py          # OKF file storage
│   │   │   └── debug_logger.py     # Request/response logging
│   │   ├── llm/
│   │   │   ├── ollama_client.py    # Ollama HTTP client
│   │   │   └── llm_manager.py      # Model management
│   │   ├── audio/
│   │   │   └── transcriber.py      # Whisper.cpp audio transcription
│   │   ├── wiki/
│   │   │   ├── indexer.py          # Wiki index (full-text + tags)
│   │   │   └── retriever.py        # Search and retrieval
│   │   └── rag/
│   │       ├── embeddings.py       # ChromaDB embedding generation
│   │       └── retriever.py        # Semantic search
│   ├── requirements.txt
│   ├── run.py
│   ├── build_exe.bat
│   ├── setup_android.sh
│   └── pyinstaller_hooks/
├── frontend/
│   ├── public/
│   │   ├── manifest.json           # PWA manifest
│   │   ├── sw.js                   # Service Worker
│   │   └── icons/                  # PWA icons
│   ├── src/
│   │   ├── main.tsx                # React entry point
│   │   ├── App.tsx                 # Main application component
│   │   ├── styles.css              # Responsive styles (mobile-friendly)
│   │   ├── api/
│   │   │   └── client.ts           # API client
│   │   └── components/
│   │       ├── TextInput.tsx        # Text input component
│   │       ├── AudioRecorder.tsx    # Audio recording component
│   │       ├── ConceptList.tsx     # Concept list view
│   │       └── ChatInterface.tsx   # RAG chat interface
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── config/
│   └── concept_types.json
├── data/                            # OKF knowledge storage (gitignored)
├── .env                             # Configuration (gitignored)
├── .env.example                     # Example configuration (for GitHub)
├── .gitignore
├── ANDROID_PLAN.md                  # Android port planning document
└── README.md
```

## 🛣️ Roadmap

- [x] Backend core (FastAPI + Ollama + OKF Storage)
- [x] RAG system (ChromaDB + Embeddings)
- [x] Audio processing (Whisper.cpp)
- [x] React frontend (TextInput, AudioRecorder, ConceptList, Chat)
- [x] PWA support (installable, offline-capable)
- [x] Android Termux support
- [ ] CLI tool
- [ ] Docker containerization
- [ ] End-to-end encryption
- [ ] Multi-user support
- [ ] Browser extension for web clipping

## 🔒 Privacy

**Zero telemetry. 100% offline capable.**

- No external API calls (unless you configure cloud models)
- All data stays on your local filesystem
- LLM inference through local or local-network Ollama
- Audio transcription runs locally via whisper.cpp

## 🧪 Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend Framework | FastAPI (Python) |
| Frontend | React 18 + TypeScript |
| Build Tool | Vite |
| LLM Backend | Ollama (local or cloud) |
| Audio Transcription | whisper.cpp (local) |
| Vector Database | ChromaDB |
| Knowledge Format | Markdown + YAML (OKF) |
| Mobile | PWA + Termux |

## 📄 License

MIT

---

<div align="center">
  <p>Built with 🧠 by an engineer, for engineers</p>
</div>