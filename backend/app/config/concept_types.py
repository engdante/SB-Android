"""
Централизиран модул за всички типове концепции и съобщения в pi_sb.

ЕДИНСТВЕН източник на истина: config/concept_types.json
Ако добавяш нов тип, промени само JSON файла — този модул го чете автоматично.

Употреба:
    from app.config.concept_types import CONCEPT_TYPES, CONCEPT_TYPE_DESCRIPTIONS, NOTIFICATION_TYPES
"""

import json
from pathlib import Path
from typing import Optional

from app.config.settings import get_app_internal_dir

# ═══════════════════════════════════════════════════════════════
# Зареждане от JSON конфиг
# ═══════════════════════════════════════════════════════════════

_CONFIG_PATH = get_app_internal_dir() / "config" / "concept_types.json"


def _load_config() -> dict:
    """Зарежда конфигурацията от JSON файла."""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Конфигурационният файл не е намерен: {_CONFIG_PATH}\n"
            f"Създай config/concept_types.json с валидни типове."
        )
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_config = _load_config()

# ═══════════════════════════════════════════════════════════════
# OKF концепции (type поле)
# ═══════════════════════════════════════════════════════════════

CONCEPT_TYPES: list[str] = list(_config["types"].keys())

# Default тип за нови концепции (използва се при fallback/невалиден LLM отговор)
DEFAULT_CONCEPT_TYPE: str = _config.get("default_type", CONCEPT_TYPES[2])

# ═══════════════════════════════════════════════════════════════
# Български описания за всеки тип (за индексите и UI)
# ═══════════════════════════════════════════════════════════════

CONCEPT_TYPE_DESCRIPTIONS: dict[str, str] = dict(_config["types"])

# ═══════════════════════════════════════════════════════════════
# Фронтенд нотификации (типове съобщения за UI)
# ═══════════════════════════════════════════════════════════════

NOTIFICATION_TYPES: list[str] = list(_config.get("notifications", []))

# ═══════════════════════════════════════════════════════════════
# API response статуси
# ═══════════════════════════════════════════════════════════════

API_STATUS_TYPES: list[str] = list(_config.get("api_statuses", []))
