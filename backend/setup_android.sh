#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# pi_sb — Second Brain
# Инсталационен скрипт за Android (Termux)
# ==============================================================================
# Употреба:
#   1. Инсталирай Termux от F-Droid (НЕ от Google Play — стара версия)
#   2. Постави този скрипт в ~/
#   3. pkg install git -y
#   4. git clone https://github.com/... pi_sb   (или копирай проекта)
#   5. cd pi_sb && bash setup_android.sh
# ==============================================================================

set -e

# ─── Цветове ───
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ─── Конфигурация ───
PI_SB_DIR="$HOME/pi_sb"
WHISPER_DIR="$HOME/whisper.cpp"
WHISPER_MODEL="ggml-large-v3-q5_0.bin"
WHISPER_MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin"
PYTHON_VERSION="3.11"

echo ""
echo "=============================================="
echo "  pi_sb — Second Brain Android Setup"
echo "=============================================="
echo ""

# ─── 1. Проверка за Termux ───
if [ ! -d "/data/data/com.termux" ] && [ ! -d "/data/data/com.termux.fdroid" ]; then
    log_warn "Това не изглежда като Termux. Продължавам... (може да сте на Linux)"
fi

# ─── 2. Актуализиране на пакетите ───
log_info "Актуализирам Termux пакети..."
pkg update -y && pkg upgrade -y
log_ok "Пакетите са актуализирани"

# ─── 3. Инсталиране на базови пакети ───
log_info "Инсталирам базови пакети..."
pkg install -y \
    python \
    clang \
    make \
    cmake \
    git \
    ffmpeg \
    wget \
    curl \
    ninja \
    pkg-config \
    which \
    bc \
    rust
log_ok "Базовите пакети са инсталирани"

# ─── 4. Проверка на Python версията ───
PYTHON_VER=$(python --version 2>&1 | grep -oP '\d+\.\d+')
PYTHON_MAJOR=$(echo "$PYTHON_VER" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VER" | cut -d. -f2)
log_info "Python версия: $PYTHON_VER"
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    log_warn "Python 3.10+ е препоръчителен. Опитвам да инсталирам python3.11..."
    pkg install -y python3.11 2>/dev/null || log_warn "Ще продължим с текущата версия"
fi

# ─── 5. Създаване на проектна директория ───
log_info "Създавам проектна директория: $PI_SB_DIR"
mkdir -p "$PI_SB_DIR"
mkdir -p "$PI_SB_DIR/data"
mkdir -p "$PI_SB_DIR/data/audio"
mkdir -p "$PI_SB_DIR/data/raw"
mkdir -p "$PI_SB_DIR/data/wiki/concepts"

# Ако скриптът е част от git clone, копираме файловете
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$SCRIPT_DIR" != "$PI_SB_DIR" ]; then
    log_info "Копирам проектните файлове в $PI_SB_DIR..."
    cp -r "$SCRIPT_DIR"/* "$PI_SB_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/.env "$PI_SB_DIR/" 2>/dev/null || true
fi

cd "$PI_SB_DIR"
log_ok "Проектната директория е готова"

# ─── 6. Създаване на виртуална Python среда (venv) ───
VENV_DIR="$PI_SB_DIR/backend/venv"
if [ -d "$VENV_DIR" ]; then
    log_info "Виртуалната среда вече съществува, актуализирам..."
else
    log_info "Създавам виртуална Python среда в $VENV_DIR..."
    python -m venv "$VENV_DIR"
    log_ok "Виртуалната среда е създадена"
fi

# Активираме venv и инсталираме зависимостите
log_info "Инсталирам Python зависимости във venv..."
source "$VENV_DIR/bin/activate"

# Python 3.14+ нуждае от PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
# за компилиране на pydantic-core (PyO3 все още не поддържа 3.14 официално)
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1

pip install --upgrade pip
pip install -r backend/requirements.txt
deactivate
log_ok "Python зависимостите са инсталирани във venv"

# ─── 7. Създаване на .env файл ───
if [ ! -f ".env" ]; then
    log_info "Създавам .env файл..."
    cat > .env << 'EOF'
# pi_sb — Second Brain (Android)
# Редактирай този файл за да конфигурираш Ollama host и модели

# Ollama сървър (на домашен компютър или cloud)
OLLAMA_HOST=http://192.168.1.100:11434
# OLLAMA_API_KEY=your-api-key-here

# Cloud модели (JSON масив)
CLOUD_MODELS=[]

# Модели за ingest и RAG
INGESTION_MODEL=gemma4:cloud
RAG_MODEL=qwen3.5:9b

# Аудио модел за whisper.cpp
AUDIO_MODEL=ggml-large-v3-q5_0.bin

# Debug
DEBUG_ENABLED=true
DEBUG=true

# OKF хранилище
OKF_DATA_DIR=./data
APP_NAME=pi_sb
APP_VERSION=1.0.0
AUDIO_UPLOAD_DIR=./data/audio
BACKEND_URL=http://localhost:8000
EOF
    log_ok ".env файлът е създаден"
    log_warn "❗ Редактирай .env и задай правилния OLLAMA_HOST (IP на твоя компютър)"
    log_warn "   Пример: OLLAMA_HOST=http://192.168.1.100:11434"
else
    log_info ".env файлът вече съществува"
fi

# ─── 8. Компилиране на whisper.cpp за ARM64 ───
if [ ! -f "$WHISPER_DIR/build/bin/whisper-server" ]; then
    log_info "Компилирам whisper.cpp за ARM64..."
    
    if [ ! -d "$WHISPER_DIR" ]; then
        git clone https://github.com/ggerganov/whisper.cpp.git "$WHISPER_DIR"
    fi
    
    cd "$WHISPER_DIR"
    
    # Компилиране с ARM64 оптимизации
    mkdir -p build && cd build
    cmake .. \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_FLAGS="-march=armv8-a+crypto -O3" \
        -DCMAKE_CXX_FLAGS="-march=armv8-a+crypto -O3" \
        -DWHISPER_NO_AVX2=ON \
        -DWHISPER_NO_AVX=ON \
        -DWHISPER_NO_FMA=ON \
        -DWHISPER_NO_F16C=ON
    
    make -j$(nproc) whisper-server
    
    # Сваляне на GGUF модела
    if [ ! -f "$WHISPER_DIR/models/$WHISPER_MODEL" ]; then
        log_info "Свалям whisper модел ($WHISPER_MODEL)..."
        cd "$WHISPER_DIR/models"
        wget -q --show-progress "$WHISPER_MODEL_URL"
        log_ok "Whisper моделът е свален"
    fi
    
    cd "$PI_SB_DIR"
    log_ok "whisper.cpp е компилиран за ARM64"
else
    log_info "whisper.cpp вече е компилиран"
fi

# ─── 9. Създаване на симлинк за whisper.cpp ───
log_info "Създавам symlink за whisper.cpp..."
ln -sf "$WHISPER_DIR" "$PI_SB_DIR/whisper.cpp" 2>/dev/null || true

# ─── 10. Build-ване на frontend (ако има Node.js) ───
if command -v node &> /dev/null; then
    log_info "Node.js е намерен, build-вам frontend..."
    if [ -d "frontend" ]; then
        cd frontend
        npm install && npm run build
        cd "$PI_SB_DIR"
        log_ok "Frontend е build-нат"
    fi
else
    log_warn "Node.js не е намерен. Frontend-ът трябва да се build-не на компютър."
    log_warn "  Команда: cd frontend && npm install && npm run build"
    log_warn "  След това копирай frontend/dist/ в телефона"
fi

# ─── 11. Създаване на стартиращ скрипт ───
log_info "Създавам стартиращ скрипт..."
cat > start_pi_sb.sh << 'STARTEOF'
#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# pi_sb — Start script за Android (Termux)
# ==============================================================================

set -e

PI_SB_DIR="$HOME/pi_sb"
WHISPER_DIR="$HOME/whisper.cpp"
WHISPER_MODEL="ggml-large-v3-q5_0.bin"

echo "=============================================="
echo "  pi_sb — Second Brain (Android)"
echo "=============================================="
echo ""

# Проверка за termux-wake-lock (предотвратява заспиване)
if command -v termux-wake-lock &> /dev/null; then
    termux-wake-lock
    echo "[WAKE] Задържам телефона буден"
fi

# Cleanup функция при спиране
cleanup() {
    echo ""
    echo "[STOP] Спирам pi_sb..."
    
    # Спираме whisper.cpp
    if [ -f "$PI_SB_DIR/whisper.pid" ]; then
        kill $(cat "$PI_SB_DIR/whisper.pid") 2>/dev/null || true
        rm -f "$PI_SB_DIR/whisper.pid"
    fi
    
    # Спираме backend
    if [ -f "$PI_SB_DIR/backend.pid" ]; then
        kill $(cat "$PI_SB_DIR/backend.pid") 2>/dev/null || true
        rm -f "$PI_SB_DIR/backend.pid"
    fi
    
    # Освобождаваме wake lock
    if command -v termux-wake-unlock &> /dev/null; then
        termux-wake-unlock
    fi
    
    echo "[STOP] pi_sb е спрян"
    exit 0
}

trap cleanup SIGINT SIGTERM

cd "$PI_SB_DIR"

# 1. Стартираме whisper.cpp
WHISPER_SERVER="$WHISPER_DIR/build/bin/whisper-server"
WHISPER_MODEL_PATH="$WHISPER_DIR/models/$WHISPER_MODEL"

if [ -f "$WHISPER_SERVER" ] && [ -f "$WHISPER_MODEL_PATH" ]; then
    echo "[WHISPER] Стартирам whisper.cpp на порт 8080..."
    
    # Termux-specific: няма CREATE_NO_WINDOW, просто пускаме процеса
    $WHISPER_SERVER \
        --model "$WHISPER_MODEL_PATH" \
        --host 127.0.0.1 \
        --port 8080 \
        -t 4 \
        -l bg \
        -bo 2 \
        -et 2.40 \
        -lpt -1.00 \
        -nth 0.60 \
        -ml 100 \
        > /dev/null 2>&1 &
    
    WHISPER_PID=$!
    echo $WHISPER_PID > "$PI_SB_DIR/whisper.pid"
    echo "[WHISPER] Стартиран (PID: $WHISPER_PID)"
    
    # Изчакваме да се стартира
    sleep 2
fi

# 2. Стартираме Python backend
echo "[BACKEND] Стартирам FastAPI на порт 8000..."
cd backend

# Активираме виртуална среда ако съществува
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info &
BACKEND_PID=$!
echo $BACKEND_PID > "$PI_SB_DIR/backend.pid"
echo "[BACKEND] Стартиран (PID: $BACKEND_PID)"

cd "$PI_SB_DIR"

# 3. Изчакваме backend-а да стартира
sleep 2

echo ""
echo "=============================================="
echo "  ✅ pi_sb работи!"
echo "=============================================="
echo ""
echo "  📱 Отвори в браузъра: http://localhost:8000"
echo "  🧠 Инсталирай като PWA app от менюто на браузъра"
echo ""
echo "  ⚙️  Ollama: $OLLAMA_HOST (конфигурирай в .env)"
echo ""
echo "  Натисни Ctrl+C за да спреш pi_sb"
echo "=============================================="

# Изчакваме backend процеса
wait $BACKEND_PID
STARTEOF

chmod +x start_pi_sb.sh
log_ok "Стартиращият скрипт е създаден: ./start_pi_sb.sh"

# ─── 12. Финални стъпки ───
echo ""
echo "=============================================="
echo "  🎉 Инсталацията завърши!"
echo "=============================================="
echo ""
echo "  📁 Проект: $PI_SB_DIR"
echo "  🎤 whisper.cpp: $WHISPER_DIR"
echo "  🔧 .env: $PI_SB_DIR/.env"
echo ""
echo "  Следващи стъпки:"
echo "    1. Редактирай .env: nano $PI_SB_DIR/.env"
echo "       (задай OLLAMA_HOST = IP на твоя компютър)"
echo ""
echo "    2а. Ако нямаш Node.js на телефона:"
echo "        - Build-ни frontend на компютър: cd frontend && npm run build"
echo "        - Копирай frontend/dist/ в $PI_SB_DIR/frontend/dist/"
echo ""
echo "    2б. Ако имаш Node.js:"
echo "        cd $PI_SB_DIR/frontend && npm install && npm run build"
echo ""
echo "    3. Стартирай: cd $PI_SB_DIR && bash start_pi_sb.sh"
echo "    4. Отвори http://localhost:8000 в браузъра"
echo "    5. Инсталирай като PWA app (Меню → Add to Home Screen)"
echo ""
echo "=============================================="